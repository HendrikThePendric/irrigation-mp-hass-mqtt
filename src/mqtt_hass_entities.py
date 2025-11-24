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
        "point_id",  # Point ID as string instead of full object
        "point_config",  # Point config for discovery
        "device_info",
        "availability_topic",
        "logger",
    ],
)


class MqttHassEntity:
    def __init__(self, params: "MessagerParams") -> None:
        self._client: MQTTClient = params.mqtt_client
        self._station_id: str = params.station_id
        self._point_id: str = params.point_id
        self._point_config = params.point_config
        self._device_info: Dict[str, Any] = params.device_info
        self._availability_topic: str = params.availability_topic
        self._logger: Logger = params.logger

    def publish_discovery_message(self) -> None:
        raise NotImplementedError(
            "publish_discovery_message must be implemented by subclasses"
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


class MqttHassSensor(MqttHassEntity):
    def __init__(self, params: MessagerParams) -> None:
        super().__init__(params)
        self._state_topic: str = (
            f"irrigation/{params.station_id}/{params.point_id}/sensor"
        )
        self.publish_discovery_message()

    def publish_discovery_message(self) -> None:
        discovery_topic: str = (
            f"homeassistant/sensor/{self._station_id}-{self._point_id}/config"
        )
        payload: Dict[str, Any] = {
            "name": f"{self._point_config.name} Moisture",
            "unique_id": f"{self._point_id}_sensor",
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
        # Note: Sensor state publishing is now handled in IrrigationStation

    def publish_moisture_level(self) -> None:
        # Note: This method is no longer used since sensor publishing is handled in IrrigationStation
        pass


class MqttHassValve(MqttHassEntity):
    def __init__(self, params: MessagerParams) -> None:
        super().__init__(params)
        self._state_topic: str = (
            f"irrigation/{params.station_id}/{params.point_id}/valve/state"
        )
        self._command_topic: str = (
            f"irrigation/{params.station_id}/{params.point_id}/valve/set"
        )
        self.publish_discovery_message()

    def publish_discovery_message(self) -> None:
        discovery_topic: str = (
            f"homeassistant/valve/{self._station_id}-{self._point_id}/config"
        )
        payload: Dict[str, Any] = {
            "name": f"{self._point_config.name} Valve",
            "unique_id": f"{self._point_id}_valve",
            "state_topic": self._state_topic,
            "command_topic": self._command_topic,
            "payload_open": "open",
            "payload_close": "closed",
            "state_open": "open",
            "state_closed": "closed",
            "optimistic": True,
            "availability_topic": self._availability_topic,
            "device": self._device_info,
            "device_class": "water",
        }
        self._client.publish(discovery_topic, dumps(payload), retain=True)
        self._log_discovery_message(discovery_topic, payload)
        # Note: Valve state publishing is now handled in IrrigationStation

    def publish_valve_state(self) -> None:
        # Note: This method is no longer used since valve publishing is handled in IrrigationStation
        pass

    def subscribe_to_command_topic(self) -> None:
        self._client.subscribe(self._command_topic)
        self._logger.log(f"Subscribed::{self._command_topic}")

    def handle_command_message(self, msg: str) -> None:
        # Note: This method is no longer used since command handling is moved to IrrigationStation
        pass
