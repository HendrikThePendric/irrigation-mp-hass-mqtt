from machine import Timer
from umqtt.robust import MQTTClient
from config import Config
from logger import Logger
from station import IrrigationStation
from hass_entities import SensorMessager, ValveMessager, MessagerParams
from health_monitor import HealthMonitor
from machine import reset
from ssl import SSLContext, PROTOCOL_TLS_CLIENT
from time import sleep, ticks_ms

MAX_RETRY_TIME = 30
RETRY_DELAY = 2
CA_PATH = "./ca_crt.der"
CERT_PATH = "./irrigationbackyard_crt.der"
KEY_PATH = "./irrigationbackyard_key.der"
PORT = 8883
KEEPALIVE = 60
# PUBLISH_INTERVAL = 240_000  # milliseconds (4 minutes)
PUBLISH_INTERVAL = 60_000  # every minute
CONNECTION_HEALTH_CHECK_INTERVAL = 300_000  # 5 minutes in milliseconds


def create_ssl_context() -> SSLContext:
    ssl_context = SSLContext(PROTOCOL_TLS_CLIENT)
    ssl_context.load_verify_locations(cafile=CA_PATH)
    ssl_context.load_cert_chain(certfile=CERT_PATH, keyfile=KEY_PATH)
    return ssl_context


class HassMqttClient:
    def __init__(
        self,
        config: Config,
        logger: Logger,
        station: IrrigationStation,
    ) -> None:
        self._config = config
        self._logger = logger
        self._station = station
        self._timer = Timer(-1)
        self._pending_publish = False
        self._sensor_messagers = []
        self._valve_messagers = []
        self._command_topic_to_valve = {}
        self._availability_topic = f"irrigation/{self._config.station_id}/availability"
        self._device_info = {
            "identifiers": [self._config.station_id],
            "name": self._config.station_name,
            "manufacturer": "HenkNet IoT",
            "model": "Raspberry Pi Pico 2 W",
            "sw_version": "0.1",
        }
        self._client = MQTTClient(
            client_id=self._config.station_mqtt_id,
            server=self._config.network.mqtt_broker_ip,
            port=PORT,
            keepalive=KEEPALIVE,
            ssl=create_ssl_context(),
        )
        self._last_successful_operation = 0  # Track last successful MQTT operation
        self._health_monitor = HealthMonitor(self._client, self._config.station_id, self._logger)

    def setup(self) -> None:
        self._connect()
        self._client.set_callback(self._handle_message)
        self._set_online()
        self._setup_entities()
        self._start_periodic_publish()
        self._health_monitor.start_health_monitoring()
        self._last_successful_operation = ticks_ms()  # Initialize timestamp

    def check_msg(self) -> None:
        try:
            self._client.check_msg()
            self._last_successful_operation = ticks_ms()
        except Exception as e:
            self._logger.log(f"MQTT check_msg failed: {e}, restarting device")
            reset()

    def handle_pending_publish(self) -> None:
        # Handle health monitor first
        self._health_monitor.handle_pending_publish()
        
        if not self._pending_publish:
            return
        
        # Check if connection is stale (no successful operations for 5 minutes)
        current_time = ticks_ms()
        if self._last_successful_operation > 0 and (current_time - self._last_successful_operation) > 300000:
            self._logger.log("MQTT connection appears stale, restarting device")
            reset()
        
        for sensor_messager in self._sensor_messagers:
            try:
                sensor_messager.publish_moisture_level()
                self._last_successful_operation = current_time
            except Exception as e:
                self._logger.log(f"Failed to publish sensor data: {e}, restarting device")
                reset()
        self._pending_publish = False

    def _connect(self) -> None:
        retry_time = 0
        connected = False
        while not connected and retry_time <= MAX_RETRY_TIME:
            try:
                self._client.set_last_will(
                    topic=self._availability_topic,
                    msg="offline",
                    retain=True,
                    qos=0,
                )
                self._client.connect()
                connected = True
            except OSError:
                sleep(RETRY_DELAY)
                retry_time += RETRY_DELAY
                self._logger.log(f"Trying to connect to MQTT Broker ({retry_time}s)")

        if not connected:
            self._logger.log("Connection to MQTT Broker failed, going to reset")
            reset()

        message = "\n".join(
            [
                "Connected to MQTT Broker:",
                f"Address:   {self._config.network.mqtt_broker_ip}:{PORT}",
                f"Client ID: {self._config.station_mqtt_id}",
            ]
        )
        self._logger.log(message)

    def _set_online(self) -> None:
        try:
            self._client.publish(self._availability_topic, "online", retain=True)
        except Exception as e:
            self._logger.log(f"Failed to publish LWT online message: {e}")

    def _setup_entities(self) -> None:
        for _, point in self._config.irrigation_points.items():
            irrigation_point = self._station.get_point(point.id)

            params = MessagerParams(
                mqtt_client=self._client,
                station_id=self._config.station_id,
                irrigation_point=irrigation_point,
                device_info=self._device_info,
                availability_topic=self._availability_topic,
                logger=self._logger,
            )
            sensor_messager = SensorMessager(params)
            valve_messager = ValveMessager(params)

            self._sensor_messagers.append(sensor_messager)
            self._valve_messagers.append(valve_messager)
            self._command_topic_to_valve[valve_messager._command_topic] = valve_messager
            try:
                valve_messager.subscribe_to_command_topic()
            except Exception as e:
                self._logger.log(
                    f"Failed to subscribe to {valve_messager._command_topic}: {e}"
                )

    def _handle_message(self, topic_bytes: bytes, msg_bytes: bytes) -> None:
        topic = topic_bytes.decode()
        msg = msg_bytes.decode()
        valve_messager = self._command_topic_to_valve.get(topic)
        if valve_messager:
            try:
                valve_messager.handle_command_message(msg)
            except Exception as e:
                self._logger.log(f"Error handling command message for {topic}: {e}")
        # No else: logging is handled by the messager classes

    def _start_periodic_publish(self) -> None:
        self._timer.init(
            period=PUBLISH_INTERVAL,
            mode=Timer.PERIODIC,
            callback=self._set_pending_publish,
        )

    def _set_pending_publish(self, _=None) -> None:
        self._pending_publish = True
