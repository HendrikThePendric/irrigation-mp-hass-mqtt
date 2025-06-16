from typing import Any, Dict
from json import dumps
from umqtt.simple import MQTTClient
from logger import Logger

from irrigation_station import IrrigationPoint


from collections import namedtuple

MessagerParams = namedtuple(
    "MessagerParams",
    [
        "mqtt_client",
        "station_id",
        "irrigation_point",
        "device_info",
        "availability_topic",
        "logger",
    ],
)


class BaseMessager:
    def __init__(self, params: "MessagerParams") -> None:
        self._client: MQTTClient = params.mqtt_client
        self._station_id: str = params.station_id
        self._point: IrrigationPoint = params.irrigation_point
        self._device_info: Dict[str, Any] = params.device_info
        self._availability_topic: str = params.availability_topic
        self._logger: Logger = params.logger

    def _publish_discovery_message(self) -> None:
        raise NotImplementedError(
            "_publish_discovery_message must be implemented by subclasses"
        )

    def _log_discovery_message(self, topic: str, payload: dict) -> None:
        lines = [
            "Sent discovery message",
            f"topic:         {topic}",
            f"state_topic:   {payload['state_topic']}",
        ]
        if "command_topic" in payload:
            lines.append(f"command_topic: {payload['command_topic']}")
        self._logger.log("\n".join(lines))


class SensorMessager(BaseMessager):
    def __init__(self, params: MessagerParams) -> None:
        super().__init__(params)
        self._state_topic: str = (
            f"irrigation/{params.station_id}/{params.irrigation_point.config.id}/sensor"
        )
        self._publish_discovery_message()

    def _publish_discovery_message(self) -> None:
        discovery_topic: str = (
            f"homeassistant/sensor/{self._station_id}-{self._point.config.id}/config"
        )
        payload: Dict[str, Any] = {
            "name": f"{self._point.config.name} Moisture",
            "unique_id": f"{self._point.config.id}_sensor",
            "device_class": "moisture",
            "state_class": "measurement",
            "unit_of_measurement": "%",
            "state_topic": self._state_topic,
            "value_template": "{{ value_json.moisture }}",
            "availability_topic": self._availability_topic,
            "device": self._device_info,
        }
        self._client.publish(discovery_topic, dumps(payload), retain=True)
        self._log_discovery_message(discovery_topic, payload)

    def publish_moisture_level(self) -> None:
        value: float = self._point.get_sensor_value()
        payload: str = dumps({"moisture": round(value * 100, 2)})
        self._client.publish(self._state_topic, payload)
        self._logger.log(f"{self._state_topic}::{payload}")


class ValveMessager(BaseMessager):
    def __init__(self, params: MessagerParams) -> None:
        super().__init__(params)
        self._state_topic: str = f"irrigation/{params.station_id}/{params.irrigation_point.config.id}/valve/state"
        self._command_topic: str = f"irrigation/{params.station_id}/{params.irrigation_point.config.id}/valve/set"
        self._publish_discovery_message()
        self.publish_valve_state()

    def _publish_discovery_message(self) -> None:
        discovery_topic: str = (
            f"homeassistant/valve/{self._station_id}-{self._point.config.id}/config"
        )
        payload: Dict[str, Any] = {
            "name": f"{self._point.config.name} Valve",
            "unique_id": f"{self._point.config.id}_valve",
            "state_topic": self._state_topic,
            "command_topic": self._command_topic,
            "payload_open": "open",
            "payload_close": "closed",
            "availability_topic": self._availability_topic,
            "device": self._device_info,
            "device_class": "water",
        }
        self._client.publish(discovery_topic, dumps(payload), retain=True)
        self._log_discovery_message(discovery_topic, payload)

    def publish_valve_state(self) -> None:
        state = self._point.get_valve_state()
        # Only allow IrrigationPoint.STATE_OPEN or STATE_CLOSED for Home Assistant
        if state not in (IrrigationPoint.STATE_OPEN, IrrigationPoint.STATE_CLOSED):
            raise ValueError(
                f"Valve state '{state}' is invalid. Must be '{IrrigationPoint.STATE_OPEN}' or '{IrrigationPoint.STATE_CLOSED}'"
            )
        self._client.publish(self._state_topic, state, retain=True)
        self._logger.log(f"{self._state_topic}::{state}")

    def subscribe_to_command_topic(self) -> None:
        self._client.subscribe(self._command_topic)
        self._logger.log(f"Subscribed::{self._command_topic}")

    def handle_command_message(self, msg: str) -> None:
        self._logger.log(f"{self._command_topic}::{msg}")
        action = msg.strip().lower()
        if action == IrrigationPoint.STATE_OPEN:
            self._point.open_valve()
        elif action == IrrigationPoint.STATE_CLOSED:
            self._point.close_valve()
        else:
            raise ValueError(f"Unknown valve command: {action}")
        self.publish_valve_state()
