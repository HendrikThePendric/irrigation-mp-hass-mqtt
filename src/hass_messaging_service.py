from json import dumps
from machine import Timer
from umqtt.simple import MQTTClient
from config import Config
from logger import Logger
from irrigation_station import IrrigationStation

# PUBLISH_INTERVAL = 240_000  # milliseconds (4 minutes)
PUBLISH_INTERVAL = 10000


class HassMessagingService:
    def __init__(
        self,
        config: Config,
        mqtt_client: MQTTClient,
        logger: Logger,
        station: IrrigationStation,
    ) -> None:
        self._config = config
        self._client = mqtt_client
        self._logger = logger
        self._station = station
        self._timer = Timer(-1)
        self._pending_publish = False
        # Set callback once
        self._client.set_callback(self._handle_message)
        self._setup_lwt()
        self._setup_subscriptions()
        self.publish_discovery_messages()
        self._start_periodic_publish()

    def _make_availability_topic(self) -> str:
        return f"irrigation/{self._config.station_id}/availability"

    def _make_topic(self, point_id: str, kind: str, action: str) -> str:
        base = f"irrigation/{self._config.station_id}/{point_id}"
        if kind == "sensor" and action == "state":
            return f"{base}/sensor"
        elif kind == "valve" and action == "state":
            return f"{base}/valve/state"
        elif kind == "valve" and action == "command":
            return f"{base}/valve/set"
        else:
            raise ValueError(f"Unknown topic kind/action: {kind}/{action}")

    def _setup_lwt(self) -> None:
        topic = self._make_availability_topic()
        self._client.set_last_will(
            topic=topic,
            msg="offline",
            retain=True,
            qos=0,
        )
        try:
            self._client.publish(topic, "online", retain=True)
        except Exception as e:
            self._logger.log(f"Failed to publish LWT online message: {e}")

    def _setup_subscriptions(self) -> None:
        for point_id in self._config.irrigation_points:
            topic = self._make_topic(point_id, "valve", "command")
            try:
                self._client.subscribe(topic)
                self._logger.log(f"Subscribed to {topic}")
            except Exception as e:
                self._logger.log(f"Failed to subscribe to {topic}: {e}")

    def _handle_message(self, topic_bytes: bytes, msg_bytes: bytes) -> None:
        topic = topic_bytes.decode()
        msg = msg_bytes.decode()

        parts = topic.split("/")
        if len(parts) < 4:
            return

        point_id = parts[2]
        action = msg.upper()

        point = self._station.get_point(point_id)
        if action == "OPEN":
            point.open_valve()
        elif action == "CLOSED":
            point.close_valve()
        else:
            # Ignore unknown commands
            self._logger.log(f"Ignored unknown valve command: {action}")
            return

        state_topic = self._make_topic(point_id, "valve", "state")
        try:
            self._client.publish(state_topic, point.get_valve_state(), retain=True)
        except Exception as e:
            self._logger.log(f"Failed to publish valve state to {state_topic}: {e}")

    def _start_periodic_publish(self) -> None:
        self._timer.init(
            period=PUBLISH_INTERVAL,
            mode=Timer.PERIODIC,
            callback=self._set_pending_publish,
        )

    def _set_pending_publish(self, _=None) -> None:
        self._pending_publish = True

    def handle_pending_publish(self) -> None:
        if not self._pending_publish:
            return
        for point_id in self._config.irrigation_points:
            point = self._station.get_point(point_id)
            value = point.get_sensor_value()
            topic = self._make_topic(point_id, "sensor", "state")
            payload = dumps({"moisture": round(value * 100, 2)})
            try:
                self._client.publish(topic, payload)
                self._logger.log(f"Published sensor data to {topic}\n{payload}")
            except Exception as e:
                self._logger.log(f"Failed to publish sensor data to {topic}: {e}")
        self._pending_publish = False

    def _publish(self, topic: str, payload: dict) -> None:
        try:
            self._client.publish(topic, dumps(payload), retain=True)
            self._logger.log(f"Published discovery config to {topic}\n{payload}")
        except Exception as e:
            self._logger.log(f"Failed to publish discovery config to {topic}: {e}")

    def publish_discovery_messages(self) -> None:
        discovery_prefix = "homeassistant"
        base_state_topic = f"irrigation/{self._config.station_id}"
        availability_topic = self._make_availability_topic()

        device_info = {
            "identifiers": [self._config.station_id],
            "name": self._config.station_name,
            "manufacturer": "HenkNet IoT",
            "model": "Pico 2",
            "sw_version": "0.1",
        }

        for point_id, point in self._config.irrigation_points.items():
            sensor_unique_id = f"{point_id}_sensor"
            valve_unique_id = f"{point_id}_valve"
            discovery_id = f"{self._config.station_id}-{point_id}"

            # Sensor
            sensor_config = {
                "name": f"{point.name} Moisture",
                "unique_id": sensor_unique_id,
                "device_class": "moisture",
                "unit_of_measurement": "%",
                "state_topic": self._make_topic(point_id, "sensor", "state"),
                "value_template": "{{ value_json.moisture }}",
                "availability_topic": availability_topic,
                "device": device_info,
            }
            sensor_topic = f"{discovery_prefix}/sensor/{discovery_id}/config"
            self._publish(sensor_topic, sensor_config)

            # Valve (MQTT Valve platform)
            valve_config = {
                "name": f"{point.name} Valve",
                "unique_id": valve_unique_id,
                "state_topic": self._make_topic(point_id, "valve", "state"),
                "command_topic": self._make_topic(point_id, "valve", "command"),
                "payload_open": "OPEN",
                "payload_close": "CLOSED",
                "availability_topic": availability_topic,
                "device": device_info,
                "device_class": "water",
            }
            valve_topic = f"{discovery_prefix}/valve/{discovery_id}/config"
            self._publish(valve_topic, valve_config)

            # Immediately publish the current state after discovery
            state_topic = self._make_topic(point_id, "valve", "state")
            try:
                # Get the current state from the IrrigationStation
                irrigation_point = self._station.get_point(point_id)
                self._client.publish(
                    state_topic, irrigation_point.get_valve_state(), retain=True
                )
                self._logger.log(
                    f"Published initial valve state to {state_topic}: {irrigation_point.get_valve_state()}"
                )
            except Exception as e:
                self._logger.log(
                    f"Failed to publish initial valve state to {state_topic}: {e}"
                )
