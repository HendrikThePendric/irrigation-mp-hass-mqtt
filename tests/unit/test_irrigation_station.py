"""Test irrigation_station.py using unittest framework."""

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

    # Mock Timer class with PERIODIC and ONE_SHOT attributes
    class Timer:
        PERIODIC = 1
        ONE_SHOT = 0

        def __init__(self, id):
            self.id = id
            self.init_calls = []

        def init(self, period, mode, callback):
            self.init_calls.append((period, mode, callback))

    reset = lambda: None

    # Mock I2C class
    class I2C:
        def __init__(self, bus, scl, sda, freq):
            self.bus = bus
            self.scl = scl
            self.sda = sda
            self.freq = freq
            self.calls = []


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
            self.i2c_bus = i2c_bus
            self.address = address
            self.gain = gain
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
from irrigation_station import IrrigationStation  # type: ignore

import unittest


class MockConfig:
    """Mock Config class."""

    def __init__(self):
        self.station_id = "teststation"
        self.rolling_window = 3
        self.publish_interval_ms = 300000  # 5 minutes in ms
        self.irrigation_points = {}

    def add_point(self, point_id, point_config):
        self.irrigation_points[point_id] = point_config


class MockPointConfig:
    """Mock IrrigationPointConfig."""

    def __init__(
        self,
        name: str,
        valve_pin: int,
        mosfet_pin: int,
        ads_address: int,
        ads_channel: int,
    ):
        self.name = name
        self.valve_pin = valve_pin
        self.mosfet_pin = mosfet_pin
        self.ads_address = ads_address
        self.ads_channel = ads_channel
        self.rolling_window = 3
        self.ema_alpha = 0.2
        self.id = name.lower().replace(" ", "")


class MockLogger:
    """Mock Logger."""

    def __init__(self):
        self.messages = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)


class TestIrrigationStation(unittest.TestCase):
    """Test irrigation_station.py using unittest framework."""

    def setUp(self) -> None:
        """Reset mock state before each test."""
        mock_machine.pins_created.clear()

    def test_irrigation_station_initialization(self) -> None:
        """Test irrigation station initialization."""
        config = MockConfig()
        logger = MockLogger()

        # Create irrigation station
        station = IrrigationStation(config, logger)  # type: ignore

        # Check that config and logger are stored
        self.assertEqual(station._config, config)
        self.assertEqual(station._logger, logger)

        # Check that I2C was created
        self.assertIsNotNone(station._i2c)

        # Check that ADS modules dictionary was created
        self.assertIsNotNone(station._ads_modules)

        # Check that irrigation points dictionary was created
        self.assertIsNotNone(station._points)

        # Check that measurement timer was created
        self.assertIsNotNone(station._measurement_timer)

    def test_irrigation_station_get_point(self) -> None:
        """Test getting irrigation point by ID."""
        config = MockConfig()
        logger = MockLogger()

        # Add a point to config
        point_config = MockPointConfig("Test Point", 2, 21, 0x48, 0)
        config.add_point("testpoint", point_config)

        # Create irrigation station
        station = IrrigationStation(config, logger)  # type: ignore

        # Get the point
        point = station.get_point("testpoint")

        # Check that point was created
        self.assertIsNotNone(point)

        # Check that point has correct config
        self.assertEqual(point.config.name, "Test Point")

        # Test getting non-existent point - should raise ValueError
        with self.assertRaises(ValueError):
            station.get_point("nonexistent")

    def test_irrigation_station_provide_instructions(self) -> None:
        """Test provide_instructions method."""
        config = MockConfig()
        logger = MockLogger()

        # Add a point to config
        point_config = MockPointConfig("Test Point", 2, 21, 0x48, 0)
        config.add_point("testpoint", point_config)

        # Create irrigation station
        station = IrrigationStation(config, logger)  # type: ignore

        # Provide instructions (list of tuples)
        instructions = [("test/topic", "open")]
        station.provide_instructions(instructions)

        # Check that instructions were stored
        self.assertEqual(station._pending_instructions, instructions)

    def test_irrigation_station_execute_pending_tasks(self) -> None:
        """Test execute_pending_tasks method."""
        config = MockConfig()
        logger = MockLogger()

        # Add a point to config
        point_config = MockPointConfig("Test Point", 2, 21, 0x48, 0)
        config.add_point("testpoint", point_config)

        # Create irrigation station
        station = IrrigationStation(config, logger)  # type: ignore

        # Add pending instructions
        station._pending_instructions = [("test/topic", "open")]

        # Execute pending tasks
        station.execute_pending_tasks()

        # Check that pending instructions were cleared
        self.assertEqual(station._pending_instructions, [])

    def test_irrigation_station_get_status_updates(self) -> None:
        """Test get_status_updates method."""
        config = MockConfig()
        logger = MockLogger()

        # Add a point to config
        point_config = MockPointConfig("Test Point", 2, 21, 0x48, 0)
        config.add_point("testpoint", point_config)

        # Create irrigation station
        station = IrrigationStation(config, logger)  # type: ignore

        # Add some status updates
        station._status_updates = [
            ("testpoint", "sensor_value=0.5"),
            ("testpoint", "valve_state=closed"),
        ]

        # Get status updates
        updates = station.get_status_updates()

        # Check that updates were returned
        self.assertEqual(
            updates,
            [("testpoint", "sensor_value=0.5"), ("testpoint", "valve_state=closed")],
        )

        # Check that status updates were cleared
        self.assertEqual(station._status_updates, [])


if __name__ == "__main__":
    # Run the tests
    unittest.main()
