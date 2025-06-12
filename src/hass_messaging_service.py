from machine import Timer
from umqtt.simple import MQTTClient
from config import Config
from logger import Logger
from irrigation_station import IrrigationStation
from hass_entities import SensorMessager, ValveMessager

# PUBLISH_INTERVAL = 240_000  # milliseconds (4 minutes)
PUBLISH_INTERVAL = 50000


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

        self._client.set_callback(self._handle_message)
        self._setup_lwt()
        self._setup_entities()
        self._start_periodic_publish()

    def _setup_lwt(self) -> None:
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

    def handle_pending_publish(self) -> None:
        if not self._pending_publish:
            return
        for sensor_messager in self._sensor_messagers:
            try:
                sensor_messager.publish_moisture_level()
            except Exception as e:
                self._logger.log(f"Failed to publish sensor data: {e}")
        self._pending_publish = False
