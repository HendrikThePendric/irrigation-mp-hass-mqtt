"""Test time_keeper.py using unittest framework."""

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

    # Mock RTC class
    class RTC:
        def __init__(self):
            self.datetime_calls = []
            self.datetime_return = (2024, 1, 1, 0, 0, 0, 0, 0)  # Default time

        def datetime(self):
            self.datetime_calls.append(())
            return self.datetime_return

    # Mock Timer class
    class Timer:
        PERIODIC = 1
        ONE_SHOT = 0

        def __init__(self, id):
            self.id = id
            self.init_calls = []

        def init(self, period, mode, callback):
            self.init_calls.append((period, mode, callback))

    reset = lambda: None


# Mock datetime module with more functionality
class MockDatetimeEnhanced:
    """Enhanced mock datetime module for time_keeper."""

    class datetime:
        def __init__(self, year, month=1, day=1, hour=0, minute=0, second=0):
            self.year = year
            self.month = month
            self.day = day
            self.hour = hour
            self.minute = minute
            self.second = second

        def __str__(self):
            return f"{self.year}-{self.month:02}-{self.day:02} {self.hour:02}:{self.minute:02}:{self.second:02}"

        def __add__(self, other):
            if isinstance(other, MockDatetimeEnhanced.timedelta):
                # Simple mock addition
                return MockDatetimeEnhanced.datetime(
                    self.year, self.month, self.day, self.hour, self.minute, self.second
                )
            return self

        def __lt__(self, other):
            # Simple comparison for DST logic
            return True

        def __le__(self, other):
            return True

        @staticmethod
        def combine(date, time):
            return MockDatetimeEnhanced.datetime(
                date.year, date.month, date.day, time.hour, time.minute, time.second
            )

    class date:
        def __init__(self, year, month, day):
            self.year = year
            self.month = month
            self.day = day

        def weekday(self):
            # Mock weekday - return 0 for Monday
            return 0

        def __sub__(self, other):
            # Mock subtraction with timedelta
            if isinstance(other, MockDatetimeEnhanced.timedelta):
                # Return a new date (simplified)
                return MockDatetimeEnhanced.date(self.year, self.month, self.day)
            return self

    class time:
        def __init__(self, hour=0, minute=0, second=0):
            self.hour = hour
            self.minute = minute
            self.second = second

    class timedelta:
        def __init__(
            self,
            days=0,
            seconds=0,
            microseconds=0,
            milliseconds=0,
            minutes=0,
            hours=0,
            weeks=0,
        ):
            self.days = days
            self.seconds = seconds

        def __add__(self, other):
            # Simple mock addition
            return MockDatetimeEnhanced.timedelta(days=self.days, seconds=self.seconds)


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["datetime"] = MockDatetimeEnhanced()
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time

# Now import the modules to test
from time_keeper import TimeKeeper  # type: ignore

import unittest


class MockLogger:
    """Mock Logger."""

    def __init__(self):
        self.messages = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)


class TestTimeKeeper(unittest.TestCase):
    """Test time_keeper.py using unittest framework."""

    def setUp(self) -> None:
        """Reset mock state before each test."""
        # Reset time mock
        mock_time.reset_ticks()

    def test_time_keeper_initialization(self) -> None:
        """Test time keeper initialization."""
        logger = MockLogger()

        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Check that RTC was initialized
        self.assertIsNotNone(time_keeper._rtc)

        # Check that timer was created (but not necessarily initialized yet)
        self.assertIsNotNone(time_keeper._sync_timer)

    def test_time_keeper_get_current_cet_datetime_str(self) -> None:
        """Test get_current_cet_datetime_str method."""
        logger = MockLogger()

        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Get current CET datetime string
        datetime_str = time_keeper.get_current_cet_datetime_str()

        # Check that it returns a string
        self.assertIsInstance(datetime_str, str)

        # Check format (should be like "2024/01/01-HH:MM:SS" for CET)
        # The actual conversion depends on mock implementation
        # Just check it's a string
        self.assertIsInstance(datetime_str, str)
        # Simple check for format (not using regex in MicroPython)
        self.assertTrue(
            "/" in datetime_str and "-" in datetime_str and ":" in datetime_str
        )

    def test_time_keeper_handle_pending_ntp_sync(self) -> None:
        """Test handle_pending_ntp_sync method."""
        logger = MockLogger()

        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Initially, pending NTP sync should be False
        self.assertFalse(time_keeper._pending_ntp_sync)

        # Set pending NTP sync
        time_keeper._pending_ntp_sync = True

        # Handle pending NTP sync
        time_keeper.handle_pending_ntp_sync()

        # Check that pending NTP sync was handled (set to False)
        self.assertFalse(time_keeper._pending_ntp_sync)

    def test_time_keeper_set_pending_ntp_sync(self) -> None:
        """Test _set_pending_ntp_sync method."""
        logger = MockLogger()

        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Initially, pending NTP sync should be False
        self.assertFalse(time_keeper._pending_ntp_sync)

        # Set pending NTP sync
        time_keeper._set_pending_ntp_sync()

        # Check that pending NTP sync was set to True
        self.assertTrue(time_keeper._pending_ntp_sync)

    def test_time_keeper_schedule_methods(self) -> None:
        """Test schedule methods."""
        logger = MockLogger()

        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Clear any previous timer calls
        time_keeper._sync_timer.init_calls.clear()

        # Test _schedule_normal_sync
        time_keeper._schedule_normal_sync()
        self.assertTrue(len(time_keeper._sync_timer.init_calls) > 0)

        # Clear timer calls again
        time_keeper._sync_timer.init_calls.clear()

        # Test _schedule_retry
        time_keeper._schedule_retry()
        self.assertTrue(len(time_keeper._sync_timer.init_calls) > 0)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
