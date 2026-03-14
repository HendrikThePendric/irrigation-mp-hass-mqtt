"""Test time_keeper.py using unittest framework with new API."""

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
    mock_ads1115,
)


# Create mock modules before importing ANY project code
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id
    RTC = type("MockRTC", (), {"datetime": lambda self: (2024, 1, 1, 0, 0, 0, 0, 0)})
    reset = lambda: None


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time
sys.modules["ads1x15"] = mock_ads1115

# Now import the modules to test
from time_keeper import TimeKeeper  # type: ignore

import unittest


class MockLogger:
    """Mock logger for testing."""

    def __init__(self) -> None:
        self.messages = []

    def log(self, message: str) -> None:
        self.messages.append(message)


class TestTimeKeeperNew(unittest.TestCase):
    """Test TimeKeeper class with new API."""

    def test_time_keeper_initialization(self) -> None:
        """Test time keeper initialization."""
        logger = MockLogger()

        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Check that RTC was created
        self.assertIsNotNone(time_keeper._rtc)

        # Check that intervals are set
        self.assertEqual(time_keeper._sync_interval, 7200)
        self.assertEqual(time_keeper._retry_interval, 60)

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
        self.assertTrue("/" in datetime_str)
        self.assertTrue(":" in datetime_str)

    def test_time_keeper_sync_time_success(self) -> None:
        """Test sync_time method with successful sync."""
        logger = MockLogger()

        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Mock ntptime.settime to succeed
        original_settime = sys.modules["ntptime"].settime
        sys.modules["ntptime"].settime = lambda: None

        try:
            # Sync time
            result = time_keeper.sync_time()

            # Should return True on success
            self.assertTrue(result)

            # Should log success
            self.assertTrue(
                any("NTP sync successful" in msg for msg in logger.messages)
            )
        finally:
            # Restore original
            sys.modules["ntptime"].settime = original_settime

    def test_time_keeper_sync_time_failure(self) -> None:
        """Test sync_time method with failed sync."""
        logger = MockLogger()

        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Mock ntptime.settime to fail
        original_settime = sys.modules["ntptime"].settime
        sys.modules["ntptime"].settime = lambda: (_ for _ in ()).throw(
            OSError("Network error")
        )

        try:
            # Sync time
            result = time_keeper.sync_time()

            # Should return False on failure
            self.assertFalse(result)

            # Should log failure
            self.assertTrue(any("NTP sync failed" in msg for msg in logger.messages))
        finally:
            # Restore original
            sys.modules["ntptime"].settime = original_settime

    def test_time_keeper_initialize_ntp_synchronization(self) -> None:
        """Test initialize_ntp_synchronization method."""
        logger = MockLogger()

        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Mock ntptime.settime to succeed
        original_settime = sys.modules["ntptime"].settime
        call_count = 0

        def mock_settime():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # Success on first try

        sys.modules["ntptime"].settime = mock_settime

        try:
            # Initialize NTP synchronization
            time_keeper.initialize_ntp_synchronization()

            # Should have called settime
            self.assertEqual(call_count, 1)

            # Should log success
            self.assertTrue(
                any("Initial NTP sync successful" in msg for msg in logger.messages)
            )
        finally:
            # Restore original
            sys.modules["ntptime"].settime = original_settime


if __name__ == "__main__":
    # Run the tests
    unittest.main()
