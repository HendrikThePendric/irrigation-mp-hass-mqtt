"""Test sensor.py using unittest framework."""

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
from sensor import Sensor  # type: ignore

import unittest


class MockConfig:
    """Mock IrrigationPointConfig."""

    def __init__(self, name: str, ads_channel: int):
        self.name = name
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
        config = MockConfig("Test Sensor", 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        # Create sensor
        sensor = Sensor(config, ads, logger)  # type: ignore

        # Check initial sensor value
        self.assertEqual(sensor._value, 0.5)

    def test_sensor_measure_wet(self) -> None:
        """Test sensor measurement with wet soil reading."""
        config = MockConfig("Test Sensor", 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        sensor = Sensor(config, ads, logger)  # type: ignore

        # 0.95V -> normalized 0.19 -> moisture = (0.48-0.19)/(0.48-0.19) = 1.0
        ads.voltage_return_value = 0.95

        sensor.measure()

        self.assertTrue(len(ads.read_calls) > 0)
        rate, channel = ads.read_calls[0]
        self.assertEqual(channel, config.ads_channel)
        self.assertTrue(len(ads.raw_to_v_calls) > 0)

        value = sensor.get_value()
        self.assertAlmostEqual(value, 1.0, places=1)

    def test_sensor_measure_dry(self) -> None:
        """Test sensor measurement with dry soil reading."""
        config = MockConfig("Test Sensor", 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        sensor = Sensor(config, ads, logger)  # type: ignore

        # 2.4V -> normalized 0.48 -> moisture = (0.48-0.48)/(0.48-0.19) = 0.0
        ads.voltage_return_value = 2.40

        sensor.measure()

        value = sensor.get_value()
        self.assertAlmostEqual(value, 0.0, places=1)

    def test_sensor_measure_midrange(self) -> None:
        """Test sensor measurement with mid-range reading."""
        config = MockConfig("Test Sensor", 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        sensor = Sensor(config, ads, logger)  # type: ignore

        # 1.675V -> normalized 0.335 -> moisture = (0.48-0.335)/(0.48-0.19) = 0.5
        ads.voltage_return_value = 1.675

        sensor.measure()

        value = sensor.get_value()
        self.assertAlmostEqual(value, 0.5, places=1)

    def test_sensor_measure_clamps_above_wet(self) -> None:
        """Test that voltage below WET calibration is clamped to 1.0."""
        config = MockConfig("Test Sensor", 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        sensor = Sensor(config, ads, logger)  # type: ignore

        # 0.5V -> normalized 0.10 -> moisture would be >1.0, clamped to 1.0
        ads.voltage_return_value = 0.5

        sensor.measure()

        value = sensor.get_value()
        self.assertAlmostEqual(value, 1.0, places=1)

    def test_sensor_measure_clamps_below_dry(self) -> None:
        """Test that voltage above DRY calibration is clamped to 0.0."""
        config = MockConfig("Test Sensor", 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        sensor = Sensor(config, ads, logger)  # type: ignore

        # 4.0V -> normalized 0.80 -> moisture would be <0.0, clamped to 0.0
        ads.voltage_return_value = 4.0

        sensor.measure()

        value = sensor.get_value()
        self.assertAlmostEqual(value, 0.0, places=1)

    def test_sensor_measure_adc_error(self) -> None:
        """Test sensor handles ADC errors gracefully."""
        config = MockConfig("Test Sensor", 0)
        ads = ADS1115Module.ADS1115()
        logger = MockLogger()

        sensor = Sensor(config, ads, logger)  # type: ignore

        # Make read() raise an exception
        def failing_read(rate, channel):
            raise OSError("I2C bus error")

        ads.read = failing_read

        initial_value = sensor.get_value()
        sensor.measure()

        error_logged = any("Error reading sensor" in msg for msg in logger.messages)
        self.assertTrue(error_logged)

        final_value = sensor.get_value()
        self.assertEqual(final_value, initial_value)

    def test_sensor_get_value(self) -> None:
        """Test sensor get_value method."""
        config = MockConfig("Test Sensor", 0)
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
