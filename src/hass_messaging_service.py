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
    ):
        self._config = config
        self._client = mqtt_client
        self._logger = logger
        self._station = station
        self._timer = Timer(-1)
        self._pending_publish = False
        self._setup_lwt()
        self._setup_subscriptions()
        self.publish_discovery_messages()
        self._start_periodic_publish()

    def _setup_lwt(self):
        self._client.set_last_will(
            topic=f"irrigation/{self._config.station_id}/availability",
            msg="offline",
            retain=True,
            qos=0,
        )
        self._client.publish(
            f"irrigation/{self._config.station_id}/availability", "online", retain=True
        )

    def _setup_subscriptions(self):
        for point_id in self._config.irrigation_points:
            topic = f"irrigation/{self._config.station_id}/{point_id}/valve/set"
            self._client.set_callback(self._handle_message)
            self._client.subscribe(topic)
            self._logger.log(f"Subscribed to {topic}")

    def _handle_message(self, topic_bytes, msg_bytes):
        topic = topic_bytes.decode()
        msg = msg_bytes.decode()

        parts = topic.split("/")
        if len(parts) < 4:
            return

        point_id = parts[2]
        action = msg.upper()

        point = self._station.get_point(point_id)
        if action == "ON":
            point.open_valve()
        elif action == "OFF":
            point.close_valve()

        state_topic = f"irrigation/{self._config.station_id}/{point_id}/valve/state"
        self._client.publish(state_topic, point.get_valve_state(), retain=True)

    def _start_periodic_publish(self):
        self._timer.init(
            period=PUBLISH_INTERVAL,
            mode=Timer.PERIODIC,
            callback=lambda t: self._set_pending_publish()
        )

    def _set_pending_publish(self):
        self._pending_publish = True

    def handle_pending_publish(self):
        if not self._pending_publish:
            return
        for point_id in self._config.irrigation_points:
            point = self._station.get_point(point_id)
            value = point.get_sensor_value()
            topic = f"irrigation/{self._config.station_id}/{point_id}/sensor"
            payload = dumps({"moisture": round(value * 100, 2)})
            self._client.publish(topic, payload)
            self._logger.log(f"Published sensor data to {topic}\n{payload}")
        self._pending_publish = False

    def _publish(self, topic, payload):
        self._client.publish(topic, dumps(payload), retain=True)
        self._logger.log(f"Published discovery config to {topic}\n{payload}")

    def publish_discovery_messages(self):
        discovery_prefix = "homeassistant"
        base_state_topic = f"irrigation/{self._config.station_id}"

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
                "state_topic": f"{base_state_topic}/{point_id}/sensor",
                "value_template": "{{ value_json.moisture }}",
                "availability_topic": f"{base_state_topic}/availability",
                "device": device_info,
            }
            sensor_topic = f"{discovery_prefix}/sensor/{discovery_id}/config"
            self._publish(sensor_topic, sensor_config)

            # Valve (MQTT Valve platform)
            valve_config = {
                "name": f"{point.name} Valve",
                "unique_id": valve_unique_id,
                "state_topic": f"{base_state_topic}/{point_id}/valve/state",
                "command_topic": f"{base_state_topic}/{point_id}/valve/set",
                "payload_open": "OPEN",
                "payload_close": "CLOSED",
                "availability_topic": f"{base_state_topic}/availability",
                "device": device_info,
                "device_class": "water",
            }
            valve_topic = f"{discovery_prefix}/valve/{discovery_id}/config"
            self._publish(valve_topic, valve_config)
