"""Test task_scheduler.py using unittest framework."""

# pyright: basic
import sys

# Setup paths
sys.path.insert(0, "src")
sys.path.insert(0, "tests")

# Import simple mocks
from simple_mocks import mock_time


# Create mock modules before importing ANY project code
class MachineModule:
    Pin = type("MockPin", (), {"OUT": 0, "IN": 1})
    unique_id = b"\x00\x01\x02\x03\x04\x05\x06\x07"
    reset = lambda: None


# Create a proper mock time module
class MockTime:
    """Mock time module for testing."""

    _current_time = 1000.0  # Start at 1000 seconds

    @staticmethod
    def time() -> float:
        """Return mock time."""
        return MockTime._current_time

    @staticmethod
    def set_time(new_time: float) -> None:
        """Set mock time for testing."""
        MockTime._current_time = new_time

    @staticmethod
    def advance(seconds: float) -> None:
        """Advance mock time by seconds."""
        MockTime._current_time += seconds

    @staticmethod
    def reset() -> None:
        """Reset mock time to default."""
        MockTime._current_time = 1000.0


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["time"] = MockTime()
sys.modules["ntptime"] = type(
    "MockNTPTime", (), {"host": "", "settime": lambda: None}
)()

# Now import the module under test
from task_scheduler import Task, TaskScheduler  # type: ignore

import unittest


class TestTask(unittest.TestCase):
    """Test the Task class."""

    def setUp(self) -> None:
        """Set up test fixture."""
        MockTime.reset()

    def test_task_initialization(self) -> None:
        """Test Task initialization with interval."""
        task = Task(interval_seconds=10.0)
        self.assertEqual(task.interval_seconds, 10.0)
        self.assertEqual(
            task.last_completion_time, 0.0
        )  # Initialized to 0.0, will be set on first complete()
        self.assertTrue(task.is_due())  # Tasks are due immediately on startup

    def test_task_update_status_not_due(self) -> None:
        """Test update_status when not enough time has passed."""
        task = Task(interval_seconds=10.0)
        # Complete the task first to set last_completion_time
        task.complete()  # Sets last_completion_time to current time (1000.0)
        # Now 5 seconds have passed
        MockTime.set_time(1005.0)  # 5 seconds elapsed
        task.update_status(current_time=1005.0)
        self.assertFalse(task.is_due())  # Needs 10 seconds total

    def test_task_update_status_due(self) -> None:
        """Test update_status when enough time has passed."""
        task = Task(interval_seconds=10.0)
        # Complete the task first to set last_completion_time
        task.complete()  # Sets last_completion_time to current time (1000.0)
        # Now 10 seconds have passed
        MockTime.set_time(1010.0)  # 10 seconds elapsed
        task.update_status(current_time=1010.0)
        self.assertTrue(task.is_due())

        # Mark complete at current time (1010.0)
        task.complete()
        self.assertEqual(task.last_completion_time, 1010.0)
        self.assertFalse(task.is_due())

        # Advance time 5 seconds - should not be due
        MockTime.set_time(1016.0)
        task.update_status(current_time=1016.0)
        self.assertFalse(task.is_due())  # Only 5 seconds since completion

        # Advance time 6 more seconds - should be due
        MockTime.set_time(1022.0)
        task.update_status(current_time=1022.0)
        self.assertTrue(task.is_due())  # 11 seconds since completion

    # Note: reset() method was removed as it was functionally identical to complete()


class TestTaskScheduler(unittest.TestCase):
    """Test the TaskScheduler class."""

    def setUp(self) -> None:
        """Set up test fixture."""
        MockTime.reset()
        self.scheduler = TaskScheduler(
            wifi_check_interval=600.0,
            ntp_sync_interval=7200.0,
            sensor_measurement_interval=100.0,
            mqtt_publish_interval=300.0,
            broker_test_interval=1800.0,
            garbage_collect_interval=30.0,
            led_update_interval=3.0,
        )

    def test_scheduler_initialization(self) -> None:
        """Test TaskScheduler initialization with tasks."""
        # Check all tasks exist
        self.assertIsInstance(self.scheduler.wifi_check, Task)
        self.assertIsInstance(self.scheduler.ntp_sync, Task)
        self.assertIsInstance(self.scheduler.sensor_measurement, Task)
        self.assertIsInstance(self.scheduler.mqtt_publish, Task)
        self.assertIsInstance(self.scheduler.broker_test, Task)
        self.assertIsInstance(self.scheduler.garbage_collect, Task)
        self.assertIsInstance(self.scheduler.led_update, Task)

        # Check intervals
        self.assertEqual(self.scheduler.wifi_check.interval_seconds, 600.0)
        self.assertEqual(self.scheduler.led_update.interval_seconds, 3.0)

    def test_scheduler_update(self) -> None:
        """Test updating all tasks in scheduler."""
        # Initially all tasks should be due (just initialized)
        self.scheduler.update()
        self.assertTrue(self.scheduler.wifi_check.is_due())
        self.assertTrue(self.scheduler.led_update.is_due())

        # Complete all tasks at initial time
        self.scheduler.wifi_check.complete()
        self.scheduler.led_update.complete()
        self.assertFalse(self.scheduler.wifi_check.is_due())
        self.assertFalse(self.scheduler.led_update.is_due())

        # Advance time 5 seconds - LED update should be due (interval 3s)
        MockTime.advance(5.0)
        self.scheduler.update()
        self.assertFalse(
            self.scheduler.wifi_check.is_due()
        )  # Needs 600s, only 5s elapsed
        self.assertTrue(self.scheduler.led_update.is_due())  # Needs 3s, 5s elapsed

        # Complete LED update
        self.scheduler.led_update.complete()
        self.assertFalse(self.scheduler.led_update.is_due())

        # Advance 2 seconds - LED should not be due
        MockTime.advance(2.0)
        self.scheduler.update()
        self.assertFalse(self.scheduler.led_update.is_due())  # Only 2s since completion

        # Advance 2 more seconds - LED should be due again
        MockTime.advance(2.0)
        self.scheduler.update()
        self.assertTrue(self.scheduler.led_update.is_due())  # 4s > 3s interval

    def test_task_attribute_access_pattern(self) -> None:
        """Test the pattern: scheduler.task_name.is_due() and .complete()."""
        # Test the exact pattern from requirements
        self.scheduler.update()

        # LED update should be due after 5 seconds (initialized at time 1000)
        MockTime.set_time(1005.0)
        self.scheduler.update()

        if self.scheduler.led_update.is_due():
            # Simulate task execution
            executed = True
            self.scheduler.led_update.complete()
        else:
            executed = False

        self.assertTrue(executed)
        self.assertFalse(self.scheduler.led_update.is_due())

    def test_different_task_intervals(self) -> None:
        """Test that tasks with different intervals work correctly."""
        # Complete all tasks at time 1000.0 (when scheduler was created)
        self.scheduler.wifi_check.complete()
        self.scheduler.ntp_sync.complete()
        self.scheduler.sensor_measurement.complete()
        self.scheduler.mqtt_publish.complete()
        self.scheduler.broker_test.complete()
        self.scheduler.garbage_collect.complete()
        self.scheduler.led_update.complete()

        # Advance time 35 seconds
        MockTime.set_time(1035.0)
        self.scheduler.update()

        # Check which tasks should be due:
        # - wifi_check: 600s interval, 35s elapsed → not due
        # - ntp_sync: 7200s interval, 35s elapsed → not due
        # - sensor_measurement: 100s interval, 35s elapsed → not due
        # - mqtt_publish: 300s interval, 35s elapsed → not due
        # - broker_test: 1800s interval, 35s elapsed → not due
        # - garbage_collect: 30s interval, 35s elapsed → due
        # - led_update: 3s interval, 35s elapsed → due

        self.assertFalse(self.scheduler.wifi_check.is_due())
        self.assertFalse(self.scheduler.ntp_sync.is_due())
        self.assertFalse(self.scheduler.sensor_measurement.is_due())
        self.assertFalse(self.scheduler.mqtt_publish.is_due())
        self.assertFalse(self.scheduler.broker_test.is_due())
        self.assertTrue(self.scheduler.garbage_collect.is_due())
        self.assertTrue(self.scheduler.led_update.is_due())


if __name__ == "__main__":
    unittest.main()
