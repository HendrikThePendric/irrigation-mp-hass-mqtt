"""Test valve.py using unittest framework."""

import sys

# Setup paths
sys.path.insert(0, "src")
sys.path.insert(0, "tests")

# Import simple mocks
from simple_mocks import (MockPin,
    mock_machine,
    mock_os, mock_ntptime,
    mock_time,)


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
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time

# Now import the modules to test
from valve import Valve  # type: ignore

import unittest


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


class TestValve(unittest.TestCase):
    """Test valve.py using unittest framework."""

    def setUp(self) -> None:
        """Reset mock state before each test."""
        mock_machine.pins_created.clear()

    def test_valve_initialization(self) -> None:
        """Test valve initialization."""
        config = MockConfig("Test Valve", 2)
        logger = MockLogger()

        # Create valve
        valve = Valve(config, logger)  # type: ignore

        # Check initial state
        self.assertEqual(valve.get_state(), "closed")

        # Check that pin was created and turned off
        self.assertEqual(len(mock_machine.pins_created), 1)

        pin = mock_machine.pins_created[0]
        self.assertEqual(pin._value, 0)

    def test_valve_open_close(self) -> None:
        """Test valve open and close operations."""
        config = MockConfig("Test Valve", 2)
        logger = MockLogger()

        # Reset mock
        mock_machine.pins_created.clear()

        # Create valve
        valve = Valve(config, logger)  # type: ignore

        # Open valve
        valve.open()

        # Check state
        self.assertEqual(valve.get_state(), "open")

        # Check pin
        pin = mock_machine.pins_created[0]
        self.assertEqual(pin._value, 1)

        # Close valve
        valve.close()

        # Check state
        self.assertEqual(valve.get_state(), "closed")

        # Check pin
        self.assertEqual(pin._value, 0)

    def test_valve_logging(self) -> None:
        """Test valve logging."""
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
        self.assertEqual(len(logger.messages), expected_logs)

        # Check log content
        has_open = any(
            "[Valve] Test Valve: Valve opened" in msg for msg in logger.messages
        )
        has_close = any(
            "[Valve] Test Valve: Valve closed" in msg for msg in logger.messages
        )

        self.assertTrue(has_open)
        self.assertTrue(has_close)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
