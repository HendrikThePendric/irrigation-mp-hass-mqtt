from mqtt_robust_client import MqttRobustClient

from config import Config
from logger import Logger
from irrigation_states import ValveState, SensorState

from mqtt_hass_entities import MqttHassSensor, MqttHassValve, MessagerParams
from ssl import SSLContext, PROTOCOL_TLS_CLIENT
from time import ticks_ms

CA_PATH = "./ca_crt.der"
CERT_PATH = "./irrigationbackyard_crt.der"
KEY_PATH = "./irrigationbackyard_key.der"
PORT = 8883
KEEPALIVE = 60


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
    ) -> None:
        self._config = config
        self._logger = logger
        self._pending_valve_commands: list[ValveState] = []
        self._availability_topic = f"irrigation/{self._config.station_id}/availability"
        self._broker_connectivity_topic = (
            f"irrigation/{self._config.station_id}/broker_connectivity"
        )
        self._sensor_messagers: dict[str, MqttHassSensor] = {}
        self._valve_messagers: dict[str, MqttHassValve] = {}
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
        )

    def setup(self) -> None:
        self._connect()
        self._client.set_callback(self._handle_message)
        self._set_online()
        self._setup_entities()
        self._monitor_hass_status()

    def process_messages(self) -> None:
        """Process incoming MQTT messages and store them."""
        self._client.check_msg()

    def get_station_instructions(self) -> list[ValveState]:
        """Return and clear pending valve commands."""
        commands = self._pending_valve_commands[:]
        self._pending_valve_commands.clear()
        return commands

    def publish_valve_states(self, valve_states: list[ValveState]) -> None:
        """Publish valve states via MQTT."""
        for valve_state in valve_states:
            if valve_state.point_id in self._valve_messagers:
                self._valve_messagers[valve_state.point_id].publish_valve_state(
                    valve_state.state
                )
            else:
                self._logger.log(f"Unknown point_id for valve: {valve_state.point_id}")

    def publish_sensor_states(self, sensor_states: list[SensorState]) -> None:
        """Publish sensor readings via MQTT."""
        for sensor_state in sensor_states:
            if sensor_state.point_id in self._sensor_messagers:
                self._sensor_messagers[sensor_state.point_id].publish_moisture_level(
                    sensor_state.moisture
                )
            else:
                self._logger.log(
                    f"Unknown point_id for sensor: {sensor_state.point_id}"
                )

    def test_broker_connectivity(self) -> None:
        """Test MQTT broker connectivity."""
        current_time = ticks_ms()
        test_payload = "broker_connectivity_test_" + str(current_time)
        self._client.publish(self._broker_connectivity_topic, test_payload, qos=1)
        self._logger.log("Broker connectivity test: " + test_payload)

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

    def _setup_entities(self) -> None:
        for point_id, point_config in self._config.irrigation_points.items():
            params = MessagerParams(
                mqtt_client=self._client,
                station_id=self._config.station_id,
                point_id=point_id,
                point_config=point_config,
                device_info=self._device_info,
                availability_topic=self._availability_topic,
                logger=self._logger,
            )
            sensor_messager = MqttHassSensor(params)
            valve_messager = MqttHassValve(params)

            self._sensor_messagers[point_id] = sensor_messager
            self._valve_messagers[point_id] = valve_messager
            try:
                valve_messager.subscribe_to_command_topic()
            except Exception as e:
                self._logger.log(
                    f"Failed to subscribe to {valve_messager._command_topic}: {e}"
                )

    def _parse_valve_command(self, topic: str, payload: str) -> ValveState:
        """Parse valve command from MQTT topic and payload."""
        # Extract point_id from topic: irrigation/{station_id}/{point_id}/valve/set
        parts = topic.split("/")
        if (
            len(parts) >= 4
            and parts[0] == "irrigation"
            and parts[1] == self._config.station_id
        ):
            point_id = parts[2]
            return ValveState(point_id, payload.strip().lower())
        else:
            raise ValueError(f"Malformed valve command topic: {topic}")

    def _handle_message(self, topic_bytes: bytes, msg_bytes: bytes) -> None:
        topic = topic_bytes.decode()
        msg = msg_bytes.decode()

        if topic == "homeassistant/status":
            self._handle_ha_status_message(msg)
            return

        if topic.endswith("/valve/set"):
            try:
                valve_command = self._parse_valve_command(topic, msg)
                self._pending_valve_commands.append(valve_command)
            except ValueError as e:
                self._logger.log(f"Invalid valve command: {e}")

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

            for sensor_messager in self._sensor_messagers.values():
                sensor_messager.publish_discovery_message()

            for valve_messager in self._valve_messagers.values():
                valve_messager.publish_discovery_message()

        except Exception as e:
            self._logger.log(f"Failed to republish after HA online: {e}")
