"""Test valve.py using simple mocks."""

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
    Timer = type("MockTimer", (), {"init": lambda self, **kwargs: None, "ONE_SHOT": 0})
    reset = lambda: None


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["datetime"] = mock_datetime
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time

# Now import the modules to test
from valve import Valve  # type: ignore


class MockConfig:
    """Mock IrrigationPointConfig."""

    def __init__(self, name: str, valve_pin: int):
        self.name = name
        self.valve_pin = valve_pin


class MockLogger:
    """Mock Logger."""

    def __init__(self):
        self.messages = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)


def test_valve_initialization() -> bool:
    """Test valve initialization."""
    print("Testing valve initialization...")

    config = MockConfig("Test Valve", 2)
    logger = MockLogger()

    # Create valve
    valve = Valve(config, logger)  # type: ignore

    # Check initial state
    if valve.get_state() != "closed":
        print(f"  ❌ Initial state should be 'closed', got {valve.get_state()}")
        return False

    # Check that pin was created and turned off
    if len(mock_machine.pins_created) != 1:
        print(f"  ❌ Expected 1 pin created, got {len(mock_machine.pins_created)}")
        return False

    pin = mock_machine.pins_created[0]
    if pin._value != 0:
        print(f"  ❌ Pin should be off (0), got {pin._value}")
        return False

    print("  ✅ Valve initialization test passed")
    return True


def test_valve_open_close() -> bool:
    """Test valve open and close operations."""
    print("Testing valve open/close...")

    config = MockConfig("Test Valve", 2)
    logger = MockLogger()

    # Reset mock
    mock_machine.pins_created.clear()

    # Create valve
    valve = Valve(config, logger)  # type: ignore

    # Open valve
    valve.open()

    # Check state
    if valve.get_state() != "open":
        print(f"  ❌ State should be 'open' after open(), got {valve.get_state()}")
        return False

    # Check pin
    pin = mock_machine.pins_created[0]
    if pin._value != 1:
        print(f"  ❌ Pin should be on (1) after open(), got {pin._value}")
        return False

    # Close valve
    valve.close()

    # Check state
    if valve.get_state() != "closed":
        print(f"  ❌ State should be 'closed' after close(), got {valve.get_state()}")
        return False

    # Check pin
    if pin._value != 0:
        print(f"  ❌ Pin should be off (0) after close(), got {pin._value}")
        return False

    print("  ✅ Valve open/close test passed")
    return True


def test_valve_logging() -> bool:
    """Test valve logging."""
    print("Testing valve logging...")

    config = MockConfig("Test Valve", 2)
    logger = MockLogger()

    # Reset mock
    mock_machine.pins_created.clear()

    # Create valve
    valve = Valve(config, logger)  # type: ignore

    # Open and close
    valve.open()
    valve.close()
    valve.get_state()

    # Check logs (no log for initial off, just open, close, get_state)
    expected_logs = 3
    if len(logger.messages) != expected_logs:
        print(f"  ❌ Expected {expected_logs} log messages, got {len(logger.messages)}")
        for msg in logger.messages:
            print(f"    - {msg}")
        return False

    # Check log content
    print(f"  Log messages: {logger.messages}")
    has_open = any("[Valve] Test Valve: Valve opened" in msg for msg in logger.messages)
    has_close = any(
        "[Valve] Test Valve: Valve closed" in msg for msg in logger.messages
    )

    if not has_open:
        print(f"  ❌ Missing open log")
        return False

    if not has_close:
        print(f"  ❌ Missing close log")
        return False

    print("  ✅ Valve logging test passed")
    return True


def main() -> None:
    """Run all valve tests."""
    print("=== Testing valve.py ===")

    passed = 0
    total = 0

    # Run tests
    total += 1
    if test_valve_initialization():
        passed += 1

    total += 1
    if test_valve_open_close():
        passed += 1

    total += 1
    if test_valve_logging():
        passed += 1

    # Summary
    print("=" * 40)
    if passed == total:
        print("✅ All valve tests passed!")
    else:
        print(f"❌ {passed}/{total} tests passed")


if __name__ == "__main__":
    main()
