"""Test watchdog.py using unittest framework."""

import sys

# Setup paths
sys.path.insert(0, "src")
sys.path.insert(0, "tests")

# Import simple mocks
from simple_mocks import (
    MockPin,
    mock_machine,
    mock_os,
    mock_datetime,
    mock_ntptime,
    mock_time,
)


# Create mock modules before importing ANY project code
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id
    RTC = type("MockRTC", (), {"datetime": lambda self: (2024, 1, 1, 0, 0, 0, 0, 0)})

    # Mock Timer class
    class Timer:
        ONE_SHOT = 0
        PERIODIC = 1

        def __init__(self):
            self.init_calls = []
            self.callback = None

        def init(self, period, mode, callback):
            self.init_calls.append((period, mode, callback))
            self.callback = callback

    reset_called = False

    @staticmethod
    def reset():
        MachineModule.reset_called = True


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["datetime"] = mock_datetime
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time

# Now import the modules to test
from watchdog import Watchdog  # type: ignore

import unittest


class MockLogger:
    """Mock Logger."""

    def __init__(self):
        self.messages = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)


class TestWatchdog(unittest.TestCase):
    """Test watchdog.py using unittest framework."""

    def setUp(self) -> None:
        """Reset mock state before each test."""
        MachineModule.reset_called = False

    def test_watchdog_initialization(self) -> None:
        """Test watchdog initialization."""
        logger = MockLogger()

        # Create watchdog with 10 second timeout
        watchdog = Watchdog(10, logger)  # type: ignore

        # Check that timer was initialized
        self.assertTrue(len(watchdog.timer.init_calls) > 0)

        # Check initialization parameters
        period, mode, callback = watchdog.timer.init_calls[0]
        self.assertEqual(period, 10000)  # 10 seconds in ms
        self.assertEqual(mode, MachineModule.Timer.ONE_SHOT)
        self.assertEqual(callback, watchdog._timeout_callback)

        # Check that log message was recorded
        init_log_found = any(
            "WatchDog initialized with timeout 10 s" in msg for msg in logger.messages
        )
        self.assertTrue(init_log_found)

    def test_watchdog_feed(self) -> None:
        """Test watchdog feed method."""
        logger = MockLogger()

        # Create watchdog
        watchdog = Watchdog(5, logger)  # type: ignore

        # Clear previous init calls
        watchdog.timer.init_calls.clear()

        # Feed the watchdog
        watchdog.feed()

        # Check that timer was re-initialized
        self.assertTrue(len(watchdog.timer.init_calls) > 0)

        # Check parameters
        period, mode, callback = watchdog.timer.init_calls[0]
        self.assertEqual(period, 5000)  # 5 seconds in ms
        self.assertEqual(mode, MachineModule.Timer.ONE_SHOT)

    def test_watchdog_timeout_callback(self) -> None:
        """Test watchdog timeout callback."""
        logger = MockLogger()

        # Reset reset flag
        MachineModule.reset_called = False

        # Create watchdog
        watchdog = Watchdog(3, logger)  # type: ignore

        # Clear logs
        logger.messages.clear()

        # Manually call timeout callback
        watchdog._timeout_callback(None)

        # Check that reset was called
        self.assertTrue(MachineModule.reset_called)

        # Check that log message was recorded
        timeout_log_found = any(
            "WatchDog timeout occurred, restarting device" in msg
            for msg in logger.messages
        )
        self.assertTrue(timeout_log_found)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
