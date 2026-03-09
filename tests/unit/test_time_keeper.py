"""Test time_keeper.py using simple mocks."""

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

        def __le__(self, other):
            return True

    class date:
        def __init__(self, year, month, day):
            self.year = year
            self.month = month
            self.day = day

        def weekday(self):
            # Mock weekday - return 0 for Monday
            return 0

        def __sub__(self, other):
            if isinstance(other, MockDatetimeEnhanced.timedelta):
                return self
            return MockDatetimeEnhanced.timedelta(days=0)

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
            self.hours = hours

        def __add__(self, other):
            return MockDatetimeEnhanced.timedelta(
                days=self.days, seconds=self.seconds, hours=self.hours
            )


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["datetime"] = MockDatetimeEnhanced()
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time

# Now import the modules to test
from time_keeper import TimeKeeper  # type: ignore


class MockLogger:
    """Mock Logger."""

    def __init__(self):
        self.messages = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)


def test_time_keeper_initialization() -> bool:
    """Test time keeper initialization."""
    print("Testing time keeper initialization...")

    logger = MockLogger()

    try:
        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Check that RTC was initialized
        if not hasattr(time_keeper, "_rtc"):
            print(f"  ❌ RTC not initialized")
            return False

        # Check that timer was initialized
        if not hasattr(time_keeper, "_sync_timer"):
            print(f"  ❌ Sync timer not initialized")
            return False

        # Check that NTP host was set
        if mock_ntptime.host != "nl.pool.ntp.org":
            print(f"  ❌ NTP host not set correctly: {mock_ntptime.host}")
            return False

        # Check default intervals
        if time_keeper._sync_interval_ms != 7200 * 1000:  # 2 hours in ms
            print(f"  ❌ Sync interval incorrect: {time_keeper._sync_interval_ms}")
            return False

        if time_keeper._retry_interval_ms != 60 * 1000:  # 1 minute in ms
            print(f"  ❌ Retry interval incorrect: {time_keeper._retry_interval_ms}")
            return False

    except Exception as e:
        print(f"  ❌ TimeKeeper initialization raised exception: {e}")
        return False

    print("  ✅ Time keeper initialization test passed")
    return True


def test_time_keeper_get_current_cet_datetime_str() -> bool:
    """Test get_current_cet_datetime_str method."""
    print("Testing get_current_cet_datetime_str()...")

    logger = MockLogger()

    try:
        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Mock RTC to return a specific time
        time_keeper._rtc.datetime_return = (2024, 6, 15, 0, 12, 30, 45, 0)
        # Format: year, month, day, weekday, hour, minute, second, microsecond

        # Get CET datetime string
        cet_str = time_keeper.get_current_cet_datetime_str()

        # Check format (should be YYYY/MM/DD-HH:MM:SS)
        if not cet_str:
            print(f"  ❌ Empty CET string returned")
            return False

        # Check basic format
        parts = cet_str.split("-")
        if len(parts) != 2:
            print(f"  ❌ CET string format incorrect: {cet_str}")
            return False

        date_part, time_part = parts
        if date_part.count("/") != 2:
            print(f"  ❌ Date part format incorrect: {date_part}")
            return False

        if time_part.count(":") != 2:
            print(f"  ❌ Time part format incorrect: {time_part}")
            return False

    except Exception as e:
        print(f"  ❌ get_current_cet_datetime_str raised exception: {e}")
        return False

    print("  ✅ get_current_cet_datetime_str() test passed")
    return True


def test_time_keeper_handle_pending_ntp_sync() -> bool:
    """Test handle_pending_ntp_sync method."""
    print("Testing handle_pending_ntp_sync()...")

    logger = MockLogger()

    try:
        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Clear any previous timer calls
        time_keeper._sync_timer.init_calls.clear()

        # Set pending sync
        time_keeper._pending_ntp_sync = True

        # Mock ntptime.settime to succeed
        original_settime = mock_ntptime.settime
        settime_called = []

        def mock_settime():
            settime_called.append(True)

        mock_ntptime.settime = mock_settime

        # Handle pending sync
        time_keeper.handle_pending_ntp_sync()

        # Check that settime was called
        if len(settime_called) == 0:
            print(f"  ❌ ntptime.settime() should have been called")
            return False

        # Check that pending flag was cleared
        if time_keeper._pending_ntp_sync != False:
            print(f"  ❌ Pending NTP sync flag should be cleared")
            return False

        # Check that timer was scheduled for normal sync
        if len(time_keeper._sync_timer.init_calls) == 0:
            print(f"  ❌ Timer should have been scheduled for normal sync")
            return False

        # Check timer was scheduled with ONE_SHOT mode
        period, mode, callback = time_keeper._sync_timer.init_calls[0]
        if mode != MachineModule.Timer.ONE_SHOT:
            print(f"  ❌ Timer should be scheduled with ONE_SHOT mode")
            return False

    except Exception as e:
        print(f"  ❌ handle_pending_ntp_sync raised exception: {e}")
        return False

    finally:
        # Restore original settime
        mock_ntptime.settime = original_settime

    print("  ✅ handle_pending_ntp_sync() test passed")
    return True


def test_time_keeper_set_pending_ntp_sync() -> bool:
    """Test _set_pending_ntp_sync method."""
    print("Testing _set_pending_ntp_sync()...")

    logger = MockLogger()

    try:
        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Initially should be False
        if time_keeper._pending_ntp_sync != False:
            print(f"  ❌ Initial pending NTP sync should be False")
            return False

        # Set pending sync
        time_keeper._set_pending_ntp_sync()

        # Should now be True
        if time_keeper._pending_ntp_sync != True:
            print(f"  ❌ Pending NTP sync should be True after _set_pending_ntp_sync")
            return False

    except Exception as e:
        print(f"  ❌ _set_pending_ntp_sync raised exception: {e}")
        return False

    print("  ✅ _set_pending_ntp_sync() test passed")
    return True


def test_time_keeper_schedule_methods() -> bool:
    """Test schedule methods."""
    print("Testing schedule methods...")

    logger = MockLogger()

    try:
        # Create time keeper
        time_keeper = TimeKeeper(logger)  # type: ignore

        # Clear any previous timer calls
        time_keeper._sync_timer.init_calls.clear()

        # Test _schedule_normal_sync
        time_keeper._schedule_normal_sync()

        if len(time_keeper._sync_timer.init_calls) == 0:
            print(f"  ❌ _schedule_normal_sync should schedule timer")
            return False

        period, mode, callback = time_keeper._sync_timer.init_calls[0]
        if period != time_keeper._sync_interval_ms:
            print(
                f"  ❌ Normal sync period incorrect: {period}, expected {time_keeper._sync_interval_ms}"
            )
            return False

        if mode != MachineModule.Timer.ONE_SHOT:
            print(f"  ❌ Normal sync should use ONE_SHOT mode")
            return False

        # Clear and test _schedule_retry
        time_keeper._sync_timer.init_calls.clear()
        time_keeper._schedule_retry()

        if len(time_keeper._sync_timer.init_calls) == 0:
            print(f"  ❌ _schedule_retry should schedule timer")
            return False

        period, mode, callback = time_keeper._sync_timer.init_calls[0]
        if period != time_keeper._retry_interval_ms:
            print(
                f"  ❌ Retry period incorrect: {period}, expected {time_keeper._retry_interval_ms}"
            )
            return False

        if mode != MachineModule.Timer.ONE_SHOT:
            print(f"  ❌ Retry should use ONE_SHOT mode")
            return False

    except Exception as e:
        print(f"  ❌ Schedule methods raised exception: {e}")
        return False

    print("  ✅ Schedule methods test passed")
    return True


def main() -> None:
    """Run all time keeper tests."""
    print("=== Testing time_keeper.py ===")

    passed = 0
    total = 0

    # Run tests
    total += 1
    if test_time_keeper_initialization():
        passed += 1

    total += 1
    if test_time_keeper_get_current_cet_datetime_str():
        passed += 1

    total += 1
    if test_time_keeper_handle_pending_ntp_sync():
        passed += 1

    total += 1
    if test_time_keeper_set_pending_ntp_sync():
        passed += 1

    total += 1
    if test_time_keeper_schedule_methods():
        passed += 1

    # Summary
    print("=" * 40)
    if passed == total:
        print("✅ All time keeper tests passed!")
    else:
        print(f"❌ {passed}/{total} tests passed")


if __name__ == "__main__":
    main()
