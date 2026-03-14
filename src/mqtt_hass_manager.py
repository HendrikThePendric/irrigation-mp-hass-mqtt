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
    ) -> None:
        self._config = config
        self._logger = logger
        self._pending_reconnect = False
        self._received_messages: list[tuple[str, str]] = []
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

    def check_msg(self) -> None:
        self._client.check_msg()

    def process_messages(self) -> None:
        """Process incoming MQTT messages and store them."""
        self.check_msg()

    def get_station_instructions(self) -> list[ValveState]:
        """Return valve commands from received MQTT messages."""
        commands: list[ValveState] = []
        valve_messages: list[tuple[str, str]] = []

        # Filter and process valve commands
        for topic, payload in self._received_messages:
            if topic.endswith("/valve/set"):
                # Extract point_id from topic: irrigation/{station_id}/{point_id}/valve/set
                parts = topic.split("/")
                if (
                    len(parts) >= 4
                    and parts[0] == "irrigation"
                    and parts[1] == self._config.station_id
                ):
                    point_id = parts[2]
                    try:
                        commands.append(ValveState(point_id, payload.strip().lower()))
                    except ValueError as e:
                        self._logger.log("Invalid valve command: " + str(e))
                else:
                    self._logger.log("Malformed valve command topic: " + topic)
                valve_messages.append((topic, payload))

        # Remove processed valve messages from received messages
        for msg in valve_messages:
            if msg in self._received_messages:
                self._received_messages.remove(msg)

        return commands

    def publish_valve_states(self, valve_states: list[ValveState]) -> None:
        """Publish valve states via MQTT."""
        for valve_state in valve_states:
            topic = (
                "irrigation/"
                + self._config.station_id
                + "/"
                + valve_state.point_id
                + "/valve/state"
            )
            self._client.publish(topic, valve_state.state, retain=True)
            self._logger.log(
                "Published valve state: "
                + valve_state.point_id
                + " = "
                + valve_state.state
            )

    def publish_sensor_states(self, sensor_states: list[SensorState]) -> None:
        """Publish sensor readings via MQTT."""
        for sensor_state in sensor_states:
            topic = (
                "irrigation/"
                + self._config.station_id
                + "/"
                + sensor_state.point_id
                + "/sensor"
            )
            # Convert 0.0-1.0 to percentage 0-100%
            moisture_percent = round(sensor_state.moisture * 100, 1)
            payload = '{"moisture": ' + str(moisture_percent) + "}"
            self._client.publish(topic, payload, retain=True)
            self._logger.log(
                "Published sensor reading: "
                + sensor_state.point_id
                + " = "
                + str(moisture_percent)
                + "%"
            )

    def test_broker_connectivity(self) -> None:
        """Test MQTT broker connectivity."""
        current_time = ticks_ms()
        test_payload = "broker_connectivity_test_" + str(current_time)
        self._client.publish(self._broker_connectivity_topic, test_payload, qos=1)
        self._logger.log("Broker connectivity test: " + test_payload)

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

    def read_received_messages(self) -> list[tuple[str, str]]:
        """Return and clear the list of received messages."""
        messages = self._received_messages[:]
        self._received_messages.clear()
        return messages

    def send_message(self, topic: str, payload: str) -> None:
        """Send a message via MQTT."""
        self._client.publish(topic, payload, retain=True)
        self._logger.log(f"Sent message: {topic} :: {payload}")

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

        # Store received messages for later processing
        self._received_messages.append((topic, msg))

        if topic == "homeassistant/status":
            self._handle_ha_status_message(msg)
            return

        # Note: Valve command handling is now done in IrrigationStation

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
