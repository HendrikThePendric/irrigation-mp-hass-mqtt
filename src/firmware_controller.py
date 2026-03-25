from machine import Pin
from mqtt_hass_manager import MqttHassManager
from irrigation_station import IrrigationStation
from open_valve_persister import OpenValvePersister
from logger import Logger
from task_scheduler import TaskScheduler
from watchdog import Watchdog
from config import Config
from time_keeper import TimeKeeper
from wifi_manager import WiFiManager
from irrigation_states import ValveState
import gc


class FirmwareController:
    """Encapsulates the entire irrigation system with a tick-based main loop."""

    def __init__(
        self, config_path: str = "./config.json", print_logs: bool = True
    ) -> None:
        """Initialize all system components.

        Args:
            config_path: Path to configuration file
            print_logs: Whether to enable logging output
        """
        self._logger = Logger(print_logs)
        self._watchdog = Watchdog(120, self._logger)
        self._time_keeper = TimeKeeper(self._logger)
        self._config = Config(config_path)
        self._scheduler = TaskScheduler(
            sensor_measurement_interval=self._config.measurement_interval,
            mqtt_publish_interval=self._config.publish_interval,
        )
        self._mqtt_manager = MqttHassManager(self._config, self._logger)
        self._open_valve_persister = OpenValvePersister(self._config, self._logger)
        self._station = IrrigationStation(
            self._config, self._logger, self._open_valve_persister
        )
        self._wifi_manager = WiFiManager(self._config.network, self._logger)
        self._onboard_led = Pin("LED", Pin.OUT)

        # Setup components
        self._logger.log(str(self._config))
        self._wifi_manager.setup()
        self._time_keeper.initialize_ntp_synchronization()
        self._logger.enable_timestamp_prefix(
            self._time_keeper.get_current_cet_datetime_str
        )
        self._mqtt_manager.setup()

        # Restore persisted valve state and publish to Home Assistant
        restored_valve_state: ValveState | None = self._open_valve_persister.get()
        if restored_valve_state:
            self._open_valve_persister.increment_opened_valve_recovery_count()
            valve_updates = self._station.process_instructions([restored_valve_state])
            self._mqtt_manager.publish_valve_states(valve_updates)

    def tick(self) -> None:
        """Execute one iteration of the main loop.

        This should be called repeatedly in the main application loop.
        Handles:
        - Watchdog feeding
        - Task scheduling
        - WiFi connection checking
        - Time synchronization
        - Garbage collection
        - LED updates
        - MQTT broker testing
        - MQTT message processing
        - Valve command processing
        - Sensor measurements
        - MQTT publishing
        """
        # Feed watchdog
        self._watchdog.feed()

        # Update scheduler (checks which tasks are due)
        self._scheduler.update()

        # Execute scheduled tasks
        if self._scheduler.wifi_check.is_due():
            self._wifi_manager.check_connection()
            self._scheduler.wifi_check.complete()

        if self._scheduler.time_sync.is_due():
            self._time_keeper.sync_time()
            self._scheduler.time_sync.complete()

        if self._scheduler.garbage_collect.is_due():
            gc.collect()
            self._scheduler.garbage_collect.complete()

        if self._scheduler.led_update.is_due():
            self._onboard_led.value(0 if self._onboard_led.value() else 1)
            self._scheduler.led_update.complete()

        if self._scheduler.broker_test.is_due():
            self._mqtt_manager.test_broker_connectivity()
            self._scheduler.broker_test.complete()

        # Process MQTT messages and valve commands
        self._mqtt_manager.process_messages()
        valve_commands = self._mqtt_manager.get_station_instructions()

        if valve_commands:
            valve_updates = self._station.process_instructions(valve_commands)
            self._mqtt_manager.publish_valve_states(valve_updates)

        # Check for valve timeout
        if self._scheduler.valve_timeout_check.is_due():
            valve_update = self._station.check_valve_timeout()
            if valve_update:
                self._mqtt_manager.publish_valve_states([valve_update])
            self._scheduler.valve_timeout_check.complete()

        # Execute sensor tasks
        if self._scheduler.sensor_measurement.is_due():
            self._station.take_measurements()
            self._scheduler.sensor_measurement.complete()

        if self._scheduler.mqtt_publish.is_due():
            sensor_states = self._station.get_sensor_states()
            self._mqtt_manager.publish_sensor_states(sensor_states)
            self._scheduler.mqtt_publish.complete()

    @property
    def logger(self) -> Logger:
        """Get the logger instance."""
        return self._logger

    @property
    def config(self) -> Config:
        """Get the configuration instance."""
        return self._config

    @property
    def station(self) -> IrrigationStation:
        """Get the irrigation station instance."""
        return self._station

    @property
    def mqtt_manager(self) -> MqttHassManager:
        """Get the MQTT manager instance."""
        return self._mqtt_manager

    @property
    def wifi_manager(self) -> WiFiManager:
        """Get the WiFi manager instance."""
        return self._wifi_manager

    @property
    def scheduler(self) -> TaskScheduler:
        """Get the task scheduler instance."""
        return self._scheduler

    @property
    def time_keeper(self) -> TimeKeeper:
        """Get the time keeper instance."""
        return self._time_keeper

    @property
    def watchdog(self) -> Watchdog:
        """Get the watchdog instance."""
        return self._watchdog
