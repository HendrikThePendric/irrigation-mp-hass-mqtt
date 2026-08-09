from mqtt_robust_client import MqttRobustClient

from config import Config
from logger import Logger
from irrigation_states import (
    ValveState,
    SensorState,
    CalibrationCommand,
    CalibrationState,
    VoltageCommand,
    VoltageState,
)

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
    """Manages MQTT connection, Home Assistant entity discovery, and message routing.

    Receives incoming messages and stores pending commands. The FirmwareController
    polls for commands and routes them through the IrrigationStation.
    """

    def __init__(
        self,
        config: Config,
        logger: Logger,
    ) -> None:
        self._config = config
        self._logger = logger
        self._pending_valve_commands: list[ValveState] = []
        self._pending_calibration_commands: list[CalibrationCommand] = []
        self._pending_voltage_commands: list[VoltageCommand] = []
        self._pending_reconnect = False
        self._sensor_messagers: dict[str, MqttHassSensor] = {}
        self._valve_messagers: dict[str, MqttHassValve] = {}
        self._device_info = {
            "identifiers": [config.station_id],
            "name": config.station_name,
            "manufacturer": "HenkNet IoT",
            "model": "Raspberry Pi Pico 2 W",
            "sw_version": "0.1",
        }
        self._client = MqttRobustClient(
            client_id=config.station_mqtt_id,
            server=config.network.mqtt_broker_ip,
            port=PORT,
            keepalive=KEEPALIVE,
            ssl=create_ssl_context(),
            logger=self._logger,
            on_reconnect_callback=self._on_reconnect_callback,
        )

    def _topic(self, rest: str) -> str:
        """Build a station-level topic: irrigation/{station_id}/{rest}."""
        return f"irrigation/{self._config.station_id}/{rest}"

    def _point_topic(self, point_id: str, rest: str) -> str:
        """Build a point-level topic: irrigation/{station_id}/{point_id}/{rest}."""
        return f"irrigation/{self._config.station_id}/{point_id}/{rest}"

    def _availability_topic(self) -> str:
        """Build the availability topic: irrigation/{station_id}/availability."""
        return self._topic("availability")

    def _on_reconnect_callback(self) -> None:
        """Called when MQTT client reconnects after a disconnection."""
        self._pending_reconnect = True

    def _handle_pending_reconnect(self) -> None:
        """Handle reconnection by restoring availability and subscriptions."""
        self._logger.log(
            "Reconnected to MQTT - restoring availability and subscriptions"
        )
        self._set_online()
        # Ensure callback is still set after reconnection
        self._client.set_callback(self._handle_message)
        self._resubscribe_after_reconnect()

    def _resubscribe_after_reconnect(self) -> None:
        """Resubscribe to all topics after reconnection since we use clean_session=True initially."""
        try:
            # Resubscribe to Home Assistant status
            self._client.subscribe("homeassistant/status", qos=0)

            # Resubscribe to all valve command topics
            for valve_messager in self._valve_messagers.values():
                valve_messager.subscribe_to_command_topic()

            for point_id in self._config.irrigation_points:
                self._subscribe_calibration_topics(point_id)
            self._logger.log("Resubscribed to all command topics after reconnection")
        except Exception as e:
            self._logger.log(f"Failed to resubscribe after reconnection: {e}")

    def setup(self) -> None:
        """Connect to MQTT, publish availability, set up HA entities and subscriptions."""
        self._connect()
        self._client.set_callback(self._handle_message)
        self._set_online()
        self._setup_entities()
        self._monitor_hass_status()

    def process_messages(self) -> None:
        """Check for incoming MQTT messages. Call from the main loop."""
        if self._pending_reconnect:
            self._handle_pending_reconnect()
            self._pending_reconnect = False

        self._client.check_msg()

    def get_station_instructions(self) -> list[ValveState]:
        """Return and clear pending valve commands."""
        commands = self._pending_valve_commands[:]
        self._pending_valve_commands.clear()
        return commands

    def get_calibration_commands(self) -> list[CalibrationCommand]:
        """Return and clear pending calibration commands."""
        commands = self._pending_calibration_commands[:]
        self._pending_calibration_commands.clear()
        return commands

    def get_voltage_commands(self) -> list[VoltageCommand]:
        """Return and clear pending voltage measurement commands."""
        commands = self._pending_voltage_commands[:]
        self._pending_voltage_commands.clear()
        return commands

    def publish_valve_states(self, valve_states: list[ValveState]) -> None:
        """Publish valve state updates to MQTT."""
        for valve_state in valve_states:
            if valve_state.point_id in self._valve_messagers:
                self._valve_messagers[valve_state.point_id].publish_valve_state(
                    valve_state.state
                )
            else:
                self._logger.log(f"Unknown point_id for valve: {valve_state.point_id}")

    def publish_sensor_states(self, sensor_states: list[SensorState]) -> None:
        """Publish sensor moisture readings to MQTT."""
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
        """Publish a test message to verify MQTT broker connectivity."""
        current_time = ticks_ms()
        test_payload = "broker_connectivity_test_" + str(current_time)
        self._client.publish(
            self._topic("broker_connectivity"),
            test_payload,
            qos=1,
        )
        self._logger.log("Broker connectivity test: " + test_payload)

    def publish_calibration_states(self, states: list[CalibrationState]) -> None:
        """Publish retained calibration voltage state for the given points."""
        for state in states:
            self._client.publish(
                self._point_topic(state.point_id, "calibration/dry_v"),
                str(state.dry_v),
                retain=True,
            )
            self._client.publish(
                self._point_topic(state.point_id, "calibration/wet_v"),
                str(state.wet_v),
                retain=True,
            )

    def publish_voltage_states(self, states: list[VoltageState]) -> None:
        """Publish retained raw voltage readings for the given points."""
        for state in states:
            self._client.publish(
                self._point_topic(state.point_id, "voltage"),
                str(state.voltage),
                retain=True,
            )

    def _connect(self) -> None:
        self._client.connect(
            clean_session=True,
            timeout=None,
            lwt_topic=self._availability_topic(),
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
        """Publish online status via retained LWT message."""
        try:
            self._client.publish(
                self._availability_topic(),
                "online",
                retain=True,
            )
        except Exception as e:
            self._logger.log(f"Failed to publish LWT online message: {e}")

    def _setup_entities(self) -> None:
        """Create HA sensor/valve entities for each point and subscribe to commands."""
        for point_id, point_config in self._config.irrigation_points.items():
            params = MessagerParams(
                mqtt_client=self._client,
                station_id=self._config.station_id,
                point_id=point_id,
                point_config=point_config,
                device_info=self._device_info,
                availability_topic=self._availability_topic(),
                logger=self._logger,
            )
            self._sensor_messagers[point_id] = MqttHassSensor(params)
            self._valve_messagers[point_id] = MqttHassValve(params)
            try:
                self._valve_messagers[point_id].subscribe_to_command_topic()
            except Exception as e:
                self._logger.log(
                    f"Failed to subscribe to "
                    f"{self._valve_messagers[point_id]._command_topic}: {e}"
                )
            self._subscribe_calibration_topics(point_id)

        self._publish_all_calibration_states()

    def _subscribe_calibration_topics(self, point_id: str) -> None:
        """Subscribe to calibration set and voltage measure topics for a point."""
        for suffix in (
            "calibration/dry_v/set",
            "calibration/wet_v/set",
            "voltage/measure",
        ):
            topic = self._point_topic(point_id, suffix)
            try:
                self._client.subscribe(topic)
            except Exception as e:
                self._logger.log(f"Failed to subscribe to {topic}: {e}")

    def _publish_all_calibration_states(self) -> None:
        """Publish retained calibration state for all points."""
        states = [
            CalibrationState(pid, pcfg.dry_voltage, pcfg.wet_voltage)
            for pid, pcfg in self._config.irrigation_points.items()
        ]
        self.publish_calibration_states(states)

    def _handle_message(self, topic_bytes: bytes, msg_bytes: bytes) -> None:
        """Route incoming MQTT messages to the appropriate handler.

        Messages are parsed from the topic structure:
          irrigation/{station_id}/{point_id}/{action}
        """
        topic = topic_bytes.decode()
        msg = msg_bytes.decode()

        if topic == "homeassistant/status":
            self._handle_ha_status_message(msg)
            return

        parts = topic.split("/")
        if (
            len(parts) < 4
            or parts[0] != "irrigation"
            or parts[1] != self._config.station_id
        ):
            return

        point_id = parts[2]
        action = "/".join(parts[3:])

        if action in ("calibration/dry_v/set", "calibration/wet_v/set"):
            try:
                value = float(msg.strip())
                self._pending_calibration_commands.append(
                    CalibrationCommand(point_id, action.split("/")[1], value)
                )
            except ValueError:
                self._logger.log(f"Invalid calibration value: {msg}")

        elif action == "voltage/measure":
            self._pending_voltage_commands.append(VoltageCommand(point_id))

        elif action == "valve/set":
            try:
                self._pending_valve_commands.append(
                    ValveState(point_id, msg.strip().lower())
                )
            except ValueError as e:
                self._logger.log(f"Invalid valve command: {e}")

    def _monitor_hass_status(self) -> None:
        """Subscribe to Home Assistant online/offline announcements."""
        try:
            self._client.subscribe("homeassistant/status", qos=0)
            self._logger.log("Subscribed to Home Assistant status messages")
        except Exception as e:
            self._logger.log(f"Failed to subscribe to HA status: {e}")

    def _handle_ha_status_message(self, status: str) -> None:
        """Handle Home Assistant online/offline status changes."""
        if status == "online":
            self._logger.log("Home Assistant came online - republishing availability")
            self._republish_after_ha_restart()
        elif status == "offline":
            self._logger.log("Home Assistant went offline")

    def _republish_after_ha_restart(self) -> None:
        """Re-publish availability, discovery messages, and calibration state after HA restart."""
        try:
            self._client.publish(
                self._availability_topic(),
                "online",
                retain=True,
            )
            for sensor_messager in self._sensor_messagers.values():
                sensor_messager.publish_discovery_message()

            for valve_messager in self._valve_messagers.values():
                valve_messager.publish_discovery_message()

            self._publish_all_calibration_states()
        except Exception as e:
            self._logger.log(f"Failed to republish after HA online: {e}")
