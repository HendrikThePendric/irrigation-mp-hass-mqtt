"""Test irrigation_point.py using unittest framework."""

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
    Timer = type("MockTimer", (), {"init": lambda self, **kwargs: None, "ONE_SHOT": 0})
    reset = lambda: None


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time


# Mock ADS1115 module
class ADS1115Module:
    """Mock ads1x15 module with ADS1115 class."""

    class ADS1115:
        def __init__(self, i2c_bus=None, address=None, gain=None):
            self.read_calls = []
            self.raw_to_v_calls = []
            self.read_return_value = 1000  # Default raw reading
            self.voltage_return_value = 2.5  # Default voltage

        def read(self, rate, channel):
            self.read_calls.append((rate, channel))
            return self.read_return_value

        def raw_to_v(self, raw):
            self.raw_to_v_calls.append(raw)
            return self.voltage_return_value


sys.modules["ads1x15"] = ADS1115Module()


# Now import the modules to test
from irrigation_point import IrrigationPoint  # type: ignore

import unittest


class MockConfig:
    """Mock IrrigationPointConfig."""

    def __init__(self, name: str, valve_pin: int, ads_channel: int):
        self.name = name
        self.valve_pin = valve_pin
        self.ads_channel = ads_channel
        self.rolling_window = 3
        self.ema_alpha = 0.2


class MockLogger:
    """Mock Logger."""

    def __init__(self):
        self.messages = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)


class TestIrrigationPoint(unittest.TestCase):
    """Test irrigation_point.py using unittest framework."""

    def setUp(self) -> None:
        """Reset mock state before each test."""
        mock_machine.pins_created.clear()

    def test_irrigation_point_initialization(self) -> None:
        """Test irrigation point initialization."""
        config = MockConfig("Test Point", 2, 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        # Create irrigation point
        point = IrrigationPoint(config, ads, logger)  # type: ignore

        # Check that config and logger are stored
        self.assertEqual(point.config, config)
        self.assertEqual(point._logger, logger)

    def test_irrigation_point_get_sensor_value(self) -> None:
        """Test getting sensor value from irrigation point."""
        config = MockConfig("Test Point", 2, 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        # Create irrigation point
        point = IrrigationPoint(config, ads, logger)  # type: ignore

        # Mock the sensor's get_value method
        # We need to patch the sensor's get_value to return a known value
        # Since we can't easily mock the Sensor class, we'll test the integration
        # by checking that the method exists and can be called
        value = point.get_sensor_value()
        # Default value should be 0.5 (from Sensor.__init__)
        self.assertEqual(value, 0.5)

    def test_irrigation_point_valve_operations(self) -> None:
        """Test valve operations through irrigation point."""
        config = MockConfig("Test Point", 2, 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        # Reset mock pins
        mock_machine.pins_created.clear()

        # Create irrigation point
        point = IrrigationPoint(config, ads, logger)  # type: ignore

        # Test opening valve
        point.open_valve()

        # Check that a pin was created for the valve
        self.assertTrue(len(mock_machine.pins_created) > 0)

        # Check valve state
        state = point.get_valve_state()
        self.assertEqual(state, "open")

        # Test closing valve
        point.close_valve()

        # Check valve state
        state = point.get_valve_state()
        self.assertEqual(state, "closed")

    def test_irrigation_point_measure_sensor(self) -> None:
        """Test measure_sensor method."""
        config = MockConfig("Test Point", 2, 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        # Reset mock pins
        mock_machine.pins_created.clear()

        # Create irrigation point
        point = IrrigationPoint(config, ads, logger)  # type: ignore

        # Test measuring sensor
        point.measure_sensor()
        self.assertTrue(len(mock_machine.pins_created) > 0)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
