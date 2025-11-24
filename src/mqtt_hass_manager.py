from machine import Timer
from mqtt_robust_client import MqttRobustClient
from umqtt.simple import MQTTClient
from config import Config
from logger import Logger
from irrigation_station import IrrigationStation
from mqtt_hass_entities import MqttHassSensor, MqttHassValve, MessagerParams
from ssl import SSLContext, PROTOCOL_TLS_CLIENT
from time import ticks_ms

CA_PATH = "./ca_crt.der"
CERT_PATH = "./irrigationbackyard_crt.der"
KEY_PATH = "./irrigationbackyard_key.der"
PORT = 8883
KEEPALIVE = 60
BROKER_CONNECTIVITY_TEST_INTERVAL = 1800000


def create_ssl_context() -> SSLContext:
    ssl_context = SSLContext(PROTOCOL_TLS_CLIENT)
    ssl_context.load_verify_locations(cafile=CA_PATH)
    ssl_context.load_cert_chain(certfile=CERT_PATH, keyfile=KEY_PATH)
    return ssl_context


class MqttHassManager:
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
        self._broker_connectivity_timer = Timer(-1)
        self._pending_publish = False
        self._pending_reconnect = False
        self._pending_broker_connectivity_test = False
        self._availability_topic = f"irrigation/{self._config.station_id}/availability"
        self._broker_connectivity_topic = (
            f"irrigation/{self._config.station_id}/broker_connectivity"
        )
        self._sensor_messagers = []
        self._valve_messagers = []
        self._command_topic_to_valve = {}
        self._device_info = {
            "identifiers": [self._config.station_id],
            "name": self._config.station_name,
            "manufacturer": "HenkNet IoT",
            "model": "Raspberry Pi Pico 2 W",
            "sw_version": "0.1",
        }
        self._client = MqttRobustClient(
            client_id=self._config.station_mqtt_id,
            server=self._config.network.mqtt_broker_ip,
            port=PORT,
            keepalive=KEEPALIVE,
            ssl=create_ssl_context(),
            logger=self._logger,
            on_reconnect_callback=self._on_reconnect_callback,
        )

    def setup(self) -> None:
        self._connect()
        self._client.set_callback(self._handle_message)
        self._set_online()
        self._setup_entities()
        self._monitor_hass_status()
        self._start_periodic_publish()
        self._start_broker_connectivity_monitoring()

    def check_msg(self) -> None:
        self._client.check_msg()

    def handle_pending_messages(self) -> None:
        if self._pending_broker_connectivity_test:
            self._handle_pending_broker_connectivity_test()
            self._pending_broker_connectivity_test = False

        if self._pending_reconnect:
            self._handle_pending_reconnect()
            self._pending_reconnect = False

        if self._pending_publish:
            for sensor_messager in self._sensor_messagers:
                sensor_messager.publish_moisture_level()
            self._pending_publish = False

    def _handle_pending_reconnect(self) -> None:
        self._logger.log(
            "Reconnected to MQTT - restoring availability and subscriptions"
        )
        self._set_online()
        self._resubscribe_after_reconnect()

    def _resubscribe_after_reconnect(self) -> None:
        """Resubscribe to all topics after reconnection since we use clean_session=True initially"""
        try:
            # Resubscribe to Home Assistant status
            self._client.subscribe("homeassistant/status", qos=0)

            # Resubscribe to all valve command topics
            for valve_messager in self._valve_messagers:
                valve_messager.subscribe_to_command_topic()

            self._logger.log("Resubscribed to all command topics after reconnection")
        except Exception as e:
            self._logger.log(f"Failed to resubscribe after reconnection: {e}")

    def _handle_pending_broker_connectivity_test(self) -> None:
        current_time = ticks_ms()
        test_payload = f"broker_connectivity_test_{current_time}"

        self._client.publish(self._broker_connectivity_topic, test_payload, qos=1)
        self._logger.log(f"Broker connectivity test acknowledged: {test_payload}")

    def _connect(self) -> None:
        self._client.connect(
            clean_session=True,
            timeout=None,
            lwt_topic=self._availability_topic,
            lwt_msg="offline",
            lwt_retain=True,
            lwt_qos=0,
        )

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

    def _on_reconnect_callback(self) -> None:
        self._pending_reconnect = True

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
            sensor_messager = MqttHassSensor(params)
            valve_messager = MqttHassValve(params)

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

        if topic == "homeassistant/status":
            self._handle_ha_status_message(msg)
            return

        valve_messager = self._command_topic_to_valve.get(topic)
        if valve_messager:
            try:
                valve_messager.handle_command_message(msg)
            except Exception as e:
                self._logger.log(f"Error handling command message for {topic}: {e}")

    def _start_periodic_publish(self) -> None:
        self._timer.init(
            period=self._config.publish_interval_ms,
            mode=Timer.PERIODIC,
            callback=self._set_pending_publish,
        )

    def _set_pending_publish(self, _=None) -> None:
        self._pending_publish = True

    def _start_broker_connectivity_monitoring(self) -> None:
        self._broker_connectivity_timer.init(
            period=BROKER_CONNECTIVITY_TEST_INTERVAL,
            mode=Timer.PERIODIC,
            callback=self._set_pending_broker_connectivity_test,
        )
        self._logger.log("Broker connectivity monitoring started")

    def _set_pending_broker_connectivity_test(self, _=None) -> None:
        self._pending_broker_connectivity_test = True

    def _monitor_hass_status(self) -> None:
        try:
            self._client.subscribe("homeassistant/status", qos=0)
            self._logger.log("Subscribed to Home Assistant status messages")
        except Exception as e:
            self._logger.log(f"Failed to subscribe to HA status: {e}")

    def _handle_ha_status_message(self, status: str) -> None:
        if status == "online":
            self._logger.log("Home Assistant came online - republishing availability")
            self._republish_after_ha_restart()
        elif status == "offline":
            self._logger.log("Home Assistant went offline")

    def _republish_after_ha_restart(self) -> None:
        try:
            self._client.publish(self._availability_topic, "online", retain=True)

            for sensor_messager in self._sensor_messagers:
                sensor_messager.publish_discovery_message()

            for valve_messager in self._valve_messagers:
                valve_messager.publish_discovery_message()

        except Exception as e:
            self._logger.log(f"Failed to republish after HA online: {e}")
