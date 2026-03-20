from time import time


class Task:
    """Represents a scheduled task with interval-based timing."""

    def __init__(self, interval_seconds: float) -> None:
        """
        Initialize a task with a specific interval.

        Args:
            interval_seconds: Time between executions in seconds
        """
        self.interval_seconds = interval_seconds
        self.last_completion_time: float = 0.0  # Will be set on first complete()
        self._is_due = True  # Tasks are due immediately on startup

    def update_status(self, current_time: float) -> None:
        """
        Update internal due status based on elapsed time.

        Args:
            current_time: Current time in seconds (from time.time())
        """
        elapsed = current_time - self.last_completion_time
        self._is_due = elapsed >= self.interval_seconds

    def is_due(self) -> bool:
        """
        Query if task is due for execution.

        Returns:
            True if task is due, False otherwise
        """
        return self._is_due

    def complete(self) -> None:
        """
        Mark task as completed at current time.
        """
        self.last_completion_time = time()
        self._is_due = False


class TaskScheduler:
    """Manages multiple tasks with interval-based scheduling."""

    def __init__(
        self,
        wifi_check_interval: float = 600.0,  # 10 minutes
        time_sync_interval: float = 30.0,  # 30 seconds (checks if sync needed every 30s)
        sensor_measurement_interval: float = 100.0,  # 100 seconds (from config)
        mqtt_publish_interval: float = 300.0,  # 5 minutes
        broker_test_interval: float = 1800.0,  # 30 minutes
        garbage_collect_interval: float = 30.0,  # 30 seconds
        led_update_interval: float = 3.0,  # 3 seconds
        valve_timeout_check_interval: float = 30.0,  # 30 seconds
    ) -> None:
        """
        Initialize task scheduler with predefined tasks.

        Args:
            wifi_check_interval: WiFi connection check interval in seconds
            time_sync_interval: NTP time sync check interval in seconds (actual sync only every 2 hours)
            sensor_measurement_interval: Sensor measurement interval in seconds
            mqtt_publish_interval: MQTT status publish interval in seconds
            broker_test_interval: MQTT broker connectivity test interval in seconds
            garbage_collect_interval: Garbage collection interval in seconds
            led_update_interval: LED status update interval in seconds
            valve_timeout_check_interval: Valve timeout check interval in seconds
        """
        self.wifi_check = Task(wifi_check_interval)
        self.time_sync = Task(time_sync_interval)
        self.sensor_measurement = Task(sensor_measurement_interval)
        self.mqtt_publish = Task(mqtt_publish_interval)
        self.broker_test = Task(broker_test_interval)
        self.garbage_collect = Task(garbage_collect_interval)
        self.led_update = Task(led_update_interval)
        self.valve_timeout_check = Task(valve_timeout_check_interval)

    def update(self) -> None:
        """Update status of all tasks based on current time."""
        current_time = time()
        self.wifi_check.update_status(current_time)
        self.time_sync.update_status(current_time)
        self.sensor_measurement.update_status(current_time)
        self.mqtt_publish.update_status(current_time)
        self.broker_test.update_status(current_time)
        self.garbage_collect.update_status(current_time)
        self.led_update.update_status(current_time)
        self.valve_timeout_check.update_status(current_time)
