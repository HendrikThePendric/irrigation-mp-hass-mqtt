"""Test sensor.py using unittest framework."""

# pyright: basic
import sys

# Setup paths
sys.path.insert(0, "src")
sys.path.insert(0, "tests")

# Import simple mocks
from simple_mocks import (MockPin,
    mock_machine,
    mock_os, mock_ntptime,
    mock_time,
    mock_ads1115,)


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
from sensor import Sensor  # type: ignore

import unittest


class MockConfig:
    """Mock IrrigationPointConfig."""

    def __init__(self, name: str, mosfet_pin: int, ads_channel: int):
        self.name = name
        self.mosfet_pin = mosfet_pin
        self.ads_channel = ads_channel
        self.rolling_window = 3
        self.ema_alpha = 0.2


class MockLogger:
    """Mock Logger."""

    def __init__(self):
        self.messages = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)


class TestSensor(unittest.TestCase):
    """Test sensor.py using unittest framework."""

    def setUp(self) -> None:
        """Reset mock state before each test."""
        mock_machine.pins_created.clear()

    def test_sensor_initialization(self) -> None:
        """Test sensor initialization."""
        config = MockConfig("Test Sensor", 21, 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        # Create sensor
        sensor = Sensor(config, ads, logger)  # type: ignore

        # Check that MOSFET pin was created
        self.assertEqual(len(mock_machine.pins_created), 1)

        # Check that MOSFET is initially off
        mosfet_pin = mock_machine.pins_created[0]
        self.assertEqual(mosfet_pin._value, 0)

        # Check initial sensor value
        self.assertEqual(sensor._value, 0.5)

    def test_sensor_measure_normal(self) -> None:
        """Test sensor measurement with normal reading."""
        config = MockConfig("Test Sensor", 21, 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        # Reset mock pins
        mock_machine.pins_created.clear()

        # Create sensor
        sensor = Sensor(config, ads, logger)  # type: ignore

        # Mock ADS1115 to return a normal voltage (2.5V -> 0.5 normalized)
        ads.voltage_return_value = 2.5  # 2.5V / 5V = 0.5

        # Measure sensor
        sensor.measure()

        # Check that MOSFET was turned on and off
        mosfet_pin = mock_machine.pins_created[0]
        self.assertIn("on", [call[0] for call in mosfet_pin.calls])
        self.assertIn("off", [call[0] for call in mosfet_pin.calls])

        # Check that ADS1115 was called correctly
        self.assertTrue(len(ads.read_calls) > 0)

        # Check channel
        rate, channel = ads.read_calls[0]
        self.assertEqual(channel, config.ads_channel)

        # Check that raw_to_v was called
        self.assertTrue(len(ads.raw_to_v_calls) > 0)

        # Check sensor value (should be around 0.5 with 2.5V reading)
        value = sensor.get_value()
        expected = 0.5  # 2.5V / 5V = 0.5
        self.assertAlmostEqual(value, expected, places=2)

    def test_sensor_measure_out_of_range(self) -> None:
        """Test sensor measurement with out-of-range reading."""
        config = MockConfig("Test Sensor", 21, 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        # Reset mock pins
        mock_machine.pins_created.clear()

        # Create sensor
        sensor = Sensor(config, ads, logger)  # type: ignore

        # Mock ADS1115 to return an out-of-range voltage (6V -> 1.2 normalized, should trigger error)
        ads.voltage_return_value = 6.0

        # Store initial value
        initial_value = sensor.get_value()

        # Measure sensor - should log error but not crash
        sensor.measure()

        # Check that error was logged
        error_logged = any("Error reading sensor" in msg for msg in logger.messages)
        self.assertTrue(error_logged)

        # Check that sensor value remains at initial value (last known good value)
        final_value = sensor.get_value()
        self.assertEqual(final_value, initial_value)

    def test_sensor_get_value(self) -> None:
        """Test sensor get_value method."""
        config = MockConfig("Test Sensor", 21, 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        # Create sensor
        sensor = Sensor(config, ads, logger)  # type: ignore

        # Initial value should be 0.5
        value = sensor.get_value()
        self.assertEqual(value, 0.5)

        # Change internal value and check get_value returns it
        sensor._value = 0.75
        value = sensor.get_value()
        self.assertEqual(value, 0.75)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
