from machine import Timer
from umqtt.robust import MQTTClient
from config import Config
from logger import Logger
from irrigation_station import IrrigationStation
from hass_entities import SensorMessager, ValveMessager
from machine import reset
from ssl import SSLContext, PROTOCOL_TLS_CLIENT
from time import sleep

MAX_RETRY_TIME = 30
RETRY_DELAY = 2
CA_PATH = "./ca_crt.der"
CERT_PATH = "./irrigationbackyard_crt.der"
KEY_PATH = "./irrigationbackyard_key.der"
PORT = 8883
KEEPALIVE = 60
# PUBLISH_INTERVAL = 240_000  # milliseconds (4 minutes)
PUBLISH_INTERVAL = 50000


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
            "model": "Pico 2",
            "sw_version": "0.1",
        }
        self._client = MQTTClient(
            client_id=self._config.station_mqtt_id,
            server=self._config.network.mqtt_broker_ip,
            port=PORT,
            keepalive=KEEPALIVE,
            ssl=create_ssl_context(),
        )

        self._connect()
        self._client.set_callback(self._handle_message)
        self._set_online()
        self._setup_entities()
        self._start_periodic_publish()

    def check_msg(self) -> None:
        self._client.check_msg()

    def handle_pending_publish(self) -> None:
        if not self._pending_publish:
            return
        for sensor_messager in self._sensor_messagers:
            try:
                sensor_messager.publish_moisture_level()
            except Exception as e:
                self._logger.log(f"Failed to publish sensor data: {e}")
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
            sensor_messager = SensorMessager(
                self._client,
                self._config.station_id,
                irrigation_point,
                self._device_info,
                self._availability_topic,
                self._logger,
            )
            self._sensor_messagers.append(sensor_messager)

            valve_messager = ValveMessager(
                self._client,
                self._config.station_id,
                irrigation_point,
                self._device_info,
                self._availability_topic,
                self._logger,
            )
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
