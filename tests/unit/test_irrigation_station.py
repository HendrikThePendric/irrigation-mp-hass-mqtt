"""Test irrigation_station.py using unittest framework with new API."""

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
    mock_ads1x15,
)


# Create mock modules before importing ANY project code
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id
    RTC = type("MockRTC", (), {"datetime": lambda self: (2024, 1, 1, 0, 0, 0, 0, 0)})
    I2C = type("MockI2C", (), {"__init__": lambda self, *args, **kwargs: None})
    reset = lambda: None


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time
sys.modules["ads1x15"] = mock_ads1x15

# Now import the modules to test
from irrigation_station import IrrigationStation  # type: ignore
from irrigation_states import ValveState, SensorState  # type: ignore

import unittest


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self) -> None:
        self.station_id = "teststation"
        self.irrigation_points = {}
        self.rolling_window = 3
        self.ema_alpha = 0.2
        self.publish_interval = 300  # 5 minutes in seconds
        self.measurement_interval = 100  # 100 seconds

    def add_point(self, point_id: str, point_config) -> None:
        self.irrigation_points[point_id] = point_config


class MockPointConfig:
    """Mock irrigation point configuration."""

    def __init__(
        self,
        name: str,
        valve_pin: int,
        mosfet_pin: int,
        ads_address: int,
        ads_channel: int,
    ) -> None:
        self.name = name
        self.valve_pin = valve_pin
        self.mosfet_pin = mosfet_pin
        self.ads_address = ads_address
        self.ads_channel = ads_channel
        self.id = name.lower().replace(" ", "")
        self.rolling_window = 3
        self.ema_alpha = 0.2


class MockIrrigationPoint:
    """Mock irrigation point for testing."""

    def __init__(self) -> None:
        self.valve_state = "closed"
        self.sensor_value = 0.5

    def get_sensor_value(self) -> float:
        return self.sensor_value

    def measure_sensor(self) -> None:
        pass

    def open_valve(self) -> None:
        self.valve_state = "open"

    def close_valve(self) -> None:
        self.valve_state = "closed"

    def get_valve_state(self) -> str:
        return self.valve_state


class MockLogger:
    """Mock logger for testing."""

    def __init__(self) -> None:
        self.messages = []

    def log(self, message: str) -> None:
        self.messages.append(message)


class TestIrrigationStationNew(unittest.TestCase):
    """Test IrrigationStation class with new API."""

    def test_irrigation_station_initialization(self) -> None:
        """Test irrigation station initialization."""
        config = MockConfig()
        logger = MockLogger()

        # Add a point to config
        point_config = MockPointConfig("Test Point", 2, 21, 0x48, 0)
        config.add_point("testpoint", point_config)

        # Create irrigation station
        station = IrrigationStation(config, logger)  # type: ignore

        # Check that irrigation points dictionary was created
        self.assertIsNotNone(station._points)
        self.assertEqual(len(station._points), 1)

    def test_irrigation_station_process_instructions(self) -> None:
        """Test process_instructions method."""
        config = MockConfig()
        logger = MockLogger()

        # Add a point to config
        point_config = MockPointConfig("Test Point", 2, 21, 0x48, 0)
        config.add_point("testpoint", point_config)

        # Create irrigation station with mocked point
        station = IrrigationStation(config, logger)  # type: ignore
        # Replace the point with a mock
        mock_point = MockIrrigationPoint()
        station._points["testpoint"] = mock_point

        # Process valve commands
        commands = [ValveState("testpoint", "open")]
        station.process_instructions(commands)

        # Check that valve was opened
        self.assertEqual(mock_point.valve_state, "open")

        # Check that valve state was recorded
        valve_states = station.get_valve_states()
        self.assertEqual(len(valve_states), 1)
        self.assertEqual(valve_states[0].point_id, "testpoint")
        self.assertEqual(valve_states[0].state, "open")

    def test_irrigation_station_take_measurements(self) -> None:
        """Test take_measurements method."""
        config = MockConfig()
        logger = MockLogger()

        # Add a point to config
        point_config = MockPointConfig("Test Point", 2, 21, 0x48, 0)
        config.add_point("testpoint", point_config)

        # Create irrigation station with mocked point
        station = IrrigationStation(config, logger)  # type: ignore
        # Replace the point with a mock
        mock_point = MockIrrigationPoint()
        mock_point.sensor_value = 0.75
        station._points["testpoint"] = mock_point

        # Take measurements
        station.take_measurements()

        # Check that sensor states can be retrieved
        sensor_states = station.get_sensor_states()
        self.assertEqual(len(sensor_states), 1)
        self.assertEqual(sensor_states[0].point_id, "testpoint")
        self.assertEqual(sensor_states[0].moisture, 0.75)

    def test_irrigation_station_get_valve_states(self) -> None:
        """Test get_valve_states method clears the list."""
        config = MockConfig()
        logger = MockLogger()

        # Add a point to config
        point_config = MockPointConfig("Test Point", 2, 21, 0x48, 0)
        config.add_point("testpoint", point_config)

        # Create irrigation station
        station = IrrigationStation(config, logger)  # type: ignore

        # Manually add a valve state
        station._valve_states.append(ValveState("testpoint", "open"))

        # Get valve states (should clear the list)
        states1 = station.get_valve_states()
        self.assertEqual(len(states1), 1)

        # Second call should return empty list
        states2 = station.get_valve_states()
        self.assertEqual(len(states2), 0)

    def test_irrigation_station_get_sensor_states(self) -> None:
        """Test get_sensor_states method."""
        config = MockConfig()
        logger = MockLogger()

        # Add two points to config
        point_config1 = MockPointConfig("Test Point 1", 2, 21, 0x48, 0)
        point_config2 = MockPointConfig("Test Point 2", 3, 22, 0x49, 1)
        config.add_point("testpoint1", point_config1)
        config.add_point("testpoint2", point_config2)

        # Create irrigation station with mocked points
        station = IrrigationStation(config, logger)  # type: ignore
        # Replace points with mocks
        mock_point1 = MockIrrigationPoint()
        mock_point1.sensor_value = 0.6
        mock_point2 = MockIrrigationPoint()
        mock_point2.sensor_value = 0.4
        station._points["testpoint1"] = mock_point1
        station._points["testpoint2"] = mock_point2

        # Get sensor states
        sensor_states = station.get_sensor_states()
        self.assertEqual(len(sensor_states), 2)

        # Check values
        values = {state.point_id: state.moisture for state in sensor_states}
        self.assertEqual(values["testpoint1"], 0.6)
        self.assertEqual(values["testpoint2"], 0.4)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
