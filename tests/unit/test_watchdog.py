"""Test watchdog.py using simple mocks."""

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


class MockLogger:
    """Mock Logger."""

    def __init__(self):
        self.messages = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)


def test_watchdog_initialization() -> bool:
    """Test watchdog initialization."""
    print("Testing watchdog initialization...")

    logger = MockLogger()

    # Reset reset flag
    MachineModule.reset_called = False

    try:
        # Create watchdog with 10 second timeout
        watchdog = Watchdog(10, logger)  # type: ignore

        # Check that timer was initialized
        if len(watchdog.timer.init_calls) == 0:
            print(f"  ❌ Timer should have been initialized")
            return False

        # Check initialization parameters
        period, mode, callback = watchdog.timer.init_calls[0]
        if period != 10000:  # 10 seconds in ms
            print(f"  ❌ Timer period incorrect: {period}, expected 10000")
            return False

        if mode != MachineModule.Timer.ONE_SHOT:
            print(f"  ❌ Timer mode should be ONE_SHOT, got {mode}")
            return False

        if callback != watchdog._timeout_callback:
            print(f"  ❌ Timer callback not set correctly")
            return False

        # Check that log message was recorded
        init_log_found = any(
            "WatchDog initialized with timeout 10 s" in msg for msg in logger.messages
        )
        if not init_log_found:
            print(f"  ❌ Initialization log message not found")
            return False

    except Exception as e:
        print(f"  ❌ Watchdog initialization raised exception: {e}")
        return False

    print("  ✅ Watchdog initialization test passed")
    return True


def test_watchdog_feed() -> bool:
    """Test watchdog feed method."""
    print("Testing watchdog.feed()...")

    logger = MockLogger()

    try:
        # Create watchdog
        watchdog = Watchdog(5, logger)  # type: ignore

        # Clear previous init calls
        watchdog.timer.init_calls.clear()

        # Feed the watchdog
        watchdog.feed()

        # Check that timer was re-initialized
        if len(watchdog.timer.init_calls) == 0:
            print(f"  ❌ Timer should have been re-initialized by feed()")
            return False

        # Check parameters
        period, mode, callback = watchdog.timer.init_calls[0]
        if period != 5000:  # 5 seconds in ms
            print(f"  ❌ Timer period incorrect after feed: {period}, expected 5000")
            return False

        if mode != MachineModule.Timer.ONE_SHOT:
            print(f"  ❌ Timer mode should be ONE_SHOT after feed, got {mode}")
            return False

    except Exception as e:
        print(f"  ❌ Watchdog.feed() raised exception: {e}")
        return False

    print("  ✅ Watchdog.feed() test passed")
    return True


def test_watchdog_timeout_callback() -> bool:
    """Test watchdog timeout callback."""
    print("Testing watchdog timeout callback...")

    logger = MockLogger()

    # Reset reset flag
    MachineModule.reset_called = False

    try:
        # Create watchdog
        watchdog = Watchdog(3, logger)  # type: ignore

        # Clear logs
        logger.messages.clear()

        # Manually call timeout callback
        watchdog._timeout_callback(None)

        # Check that reset was called
        if not MachineModule.reset_called:
            print(f"  ❌ reset() should have been called by timeout callback")
            return False

        # Check that log message was recorded
        timeout_log_found = any(
            "WatchDog timeout occurred, restarting device" in msg
            for msg in logger.messages
        )
        if not timeout_log_found:
            print(f"  ❌ Timeout log message not found")
            return False

    except Exception as e:
        print(f"  ❌ Watchdog timeout callback raised exception: {e}")
        return False

    print("  ✅ Watchdog timeout callback test passed")
    return True


def main() -> None:
    """Run all watchdog tests."""
    print("=== Testing watchdog.py ===")

    passed = 0
    total = 0

    # Run tests
    total += 1
    if test_watchdog_initialization():
        passed += 1

    total += 1
    if test_watchdog_feed():
        passed += 1

    total += 1
    if test_watchdog_timeout_callback():
        passed += 1

    # Summary
    print("=" * 40)
    if passed == total:
        print("✅ All watchdog tests passed!")
    else:
        print(f"❌ {passed}/{total} tests passed")


if __name__ == "__main__":
    main()
