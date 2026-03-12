"""Test watchdog.py using unittest framework."""

# pyright: basic
import sys

# Setup paths
sys.path.insert(0, "src")
sys.path.insert(0, "tests")

# Import simple mocks
from simple_mocks import (
    MockPin,
    mock_machine,
    mock_os,
    mock_ntptime,
    mock_time,
)


# Create mock modules before importing ANY project code
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id
    RTC = type("MockRTC", (), {"datetime": lambda self: (2024, 1, 1, 0, 0, 0, 0, 0)})
    Timer = mock_machine.Timer

    reset_called = False

    @staticmethod
    def reset():
        MachineModule.reset_called = True


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
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

    def test_timeout_after_expiry(self) -> None:
        """Test that timeout occurs after simulated time passes expiry."""
        logger = MockLogger()

        # Reset flag
        MachineModule.reset_called = False

        # Create watchdog with 3 second timeout
        watchdog = Watchdog(3, logger)  # type: ignore
        timer = watchdog.timer

        # Simulate 2 seconds passed - should not trigger
        timer.simulate_time_passed(2000)
        self.assertFalse(
            MachineModule.reset_called,
            "Reset should NOT be called after 2 seconds (3 second timeout)",
        )

        # Simulate another 1.5 seconds passed - total 3.5 seconds > 3 second timeout
        timer.simulate_time_passed(1500)

        # Verify reset was called (timeout occurred)
        self.assertTrue(
            MachineModule.reset_called,
            "Reset SHOULD be called after 3.5 seconds (exceeds 3 second timeout)",
        )

        # Verify timer is inactive after ONE_SHOT expiration
        self.assertFalse(timer.active, "ONE_SHOT timer should be inactive after firing")

        # Verify timeout log message
        timeout_log_found = any(
            "WatchDog timeout occurred, restarting device" in msg
            for msg in logger.messages
        )
        self.assertTrue(timeout_log_found, "Timeout log message should be recorded")

    def test_feed_prevents_timeout(self) -> None:
        """Test that feeding the watchdog resets timer and prevents timeout."""
        logger = MockLogger()

        # Reset flag
        MachineModule.reset_called = False

        # Create watchdog with 5 second timeout
        watchdog = Watchdog(5, logger)  # type: ignore
        timer = watchdog.timer

        # Simulate 4 seconds passed - 1 second before timeout
        timer.simulate_time_passed(4000)
        self.assertFalse(
            MachineModule.reset_called,
            "Reset should NOT be called after 4 seconds (5 second timeout)",
        )
        self.assertEqual(
            timer.elapsed_time, 4000, "Elapsed time should be 4000ms after 4 seconds"
        )

        # Call feed() to reset the timer
        watchdog.feed()

        # Timer should be active with elapsed time reset
        self.assertTrue(timer.active, "Timer should be active after feed()")
        self.assertEqual(
            timer.elapsed_time, 0, "Elapsed time should be reset to 0 after feed()"
        )

        # Simulate 3 seconds passed after feed
        timer.simulate_time_passed(3000)
        self.assertFalse(
            MachineModule.reset_called,
            "Reset should NOT be called 3s after feed (timer was reset)",
        )

        # Simulate another 3 seconds - total 6s after feed, which is > 5s timeout
        timer.simulate_time_passed(3000)

        # Now reset SHOULD be called because 6 seconds passed since feed
        self.assertTrue(
            MachineModule.reset_called,
            "Reset SHOULD be called 6s after feed (exceeds 5s timeout)",
        )


if __name__ == "__main__":
    # Run the tests
    unittest.main()
