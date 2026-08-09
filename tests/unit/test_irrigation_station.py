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


class MockOpenValvePersister:
    """Mock open valve persister for testing."""

    _instance = None
    MAX_RECOVERY_ATTEMPTS = 3

    def __init__(self, config, logger) -> None:
        self._logger = logger
        self.data = None  # dict with point_id, opened_timestamp, recovery_count or None
        self.set_calls = []  # list of point_id strings
        self.clear_calls = []  # list of empty tuples
        self.increment_calls = []  # list of empty tuples
        self.__class__._instance = self

    @classmethod
    def get_instance(cls):
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    def get(self) -> ValveState | None:
        if self.data is None:
            return None
        point_id = self.data["point_id"]
        opened_timestamp = self.data["opened_timestamp"]
        recovery_count = self.data.get("recovery_count", 0)

        # Simulate recovery count check
        if recovery_count >= self.MAX_RECOVERY_ATTEMPTS:
            self.data = None
            return None

        # DO NOT increment recovery count here anymore
        return ValveState(point_id, "open")

    def increment_opened_valve_recovery_count(self) -> None:
        self.increment_calls.append(())
        if self.data is None:
            return
        recovery_count = self.data.get("recovery_count", 0)
        self.data["recovery_count"] = recovery_count + 1

    def set(self, point_id: str) -> None:
        from simple_mocks import mock_time

        self.data = {
            "point_id": point_id,
            "opened_timestamp": mock_time.time(),
            "recovery_count": 0,
        }
        self.set_calls.append(point_id)

    def clear(self) -> None:
        self.data = None
        self.clear_calls.append(())


# Mock open_valve_persister module
class MockOpenValvePersisterModule:
    OpenValvePersister = MockOpenValvePersister


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time
sys.modules["ads1x15"] = mock_ads1x15
sys.modules["open_valve_persister"] = MockOpenValvePersisterModule()

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
        self.max_valve_open_time = 45 * 60  # 45 minutes in seconds
        self.calibration_updates: list[tuple] = []

    def add_point(self, point_id: str, point_config) -> None:
        self.irrigation_points[point_id] = point_config

    def update_calibration(
        self, point_id: str, dry_v: float | None = None, wet_v: float | None = None
    ) -> None:
        self.calibration_updates.append((point_id, dry_v, wet_v))


class MockPointConfig:
    """Mock irrigation point configuration."""

    def __init__(
        self,
        name: str,
        valve_pin: int,
        ads_address: int,
        ads_channel: int,
    ) -> None:
        self.name = name
        self.valve_pin = valve_pin
        self.ads_address = ads_address
        self.ads_channel = ads_channel
        self.id = name.lower().replace(" ", "")
        self.rolling_window = 3
        self.ema_alpha = 0.2
        self.dry_voltage: float = 2.4
        self.wet_voltage: float = 0.95


class MockIrrigationPoint:
    """Mock irrigation point for testing."""

    def __init__(self, point_id: str = "") -> None:
        self.point_id = point_id
        self.valve_state = "closed"
        self.sensor_value = 0.5
        self.open_count = 0
        self.close_count = 0
        self.calibration_updates: list[tuple[float, float]] = []
        self.raw_voltage_calls: int = 0
        self.raw_voltage_return = 1.387
        # config-like attributes needed by calibration
        self.config = self

    _dry_voltage: float | None
    _wet_voltage: float | None

    @property
    def dry_voltage(self) -> float | None:
        return getattr(self, "_dry_voltage", None)

    @dry_voltage.setter
    def dry_voltage(self, value: float | None) -> None:
        self._dry_voltage = value

    @property
    def wet_voltage(self) -> float | None:
        return getattr(self, "_wet_voltage", None)

    @wet_voltage.setter
    def wet_voltage(self, value: float | None) -> None:
        self._wet_voltage = value

    def get_sensor_value(self) -> float:
        return self.sensor_value

    def measure_sensor(self) -> None:
        pass

    def open_valve(self) -> None:
        self.valve_state = "open"
        self.open_count += 1

    def close_valve(self) -> None:
        self.valve_state = "closed"
        self.close_count += 1

    def get_valve_state(self) -> str:
        return self.valve_state

    def get_raw_voltage(self) -> float:
        self.raw_voltage_calls += 1
        return self.raw_voltage_return

    def update_calibration(self, dry_v: float, wet_v: float) -> None:
        self.calibration_updates.append((dry_v, wet_v))

    def reset_counts(self) -> None:
        """Reset operation counts for testing."""
        self.open_count = 0
        self.close_count = 0


class MockLogger:
    """Mock logger for testing."""

    def __init__(self) -> None:
        self.messages = []

    def log(self, message: str) -> None:
        self.messages.append(message)


class TestIrrigationStationNew(unittest.TestCase):
    """Test IrrigationStation class with new API."""

    def setUp(self) -> None:
        """Reset mock state before each test."""
        MockOpenValvePersister.reset()
        # Also reset mock time if needed
        from simple_mocks import mock_time

        mock_time.reset_time()
        mock_time.reset_ticks()

    def test_irrigation_station_initialization(self) -> None:
        """Test irrigation station initialization."""
        config = MockConfig()
        logger = MockLogger()

        # Add a point to config
        point_config = MockPointConfig("Test Point", 2, 0x48, 0)
        config.add_point("testpoint", point_config)

        # Create irrigation station
        persister = MockOpenValvePersister(config, logger)
        station = IrrigationStation(config, logger, persister)

        # Check that irrigation points dictionary was created
        self.assertIsNotNone(station._points)
        self.assertEqual(len(station._points), 1)

    def test_irrigation_station_process_instructions(self) -> None:
        """Test process_instructions method."""
        config = MockConfig()
        logger = MockLogger()

        # Add a point to config
        point_config = MockPointConfig("Test Point", 2, 0x48, 0)
        config.add_point("testpoint", point_config)

        # Create irrigation station with mocked point
        persister = MockOpenValvePersister(config, logger)
        station = IrrigationStation(config, logger, persister)
        # Replace the point with a mock
        mock_point = MockIrrigationPoint("testpoint")
        station._points["testpoint"] = mock_point

        # Process valve commands and get valve updates
        commands = [ValveState("testpoint", "open")]
        valve_updates = station.process_instructions(commands)

        # Check that valve was opened
        self.assertEqual(mock_point.valve_state, "open")

        # Check that valve updates were returned
        self.assertEqual(len(valve_updates), 1)
        self.assertEqual(valve_updates[0].point_id, "testpoint")
        self.assertEqual(valve_updates[0].state, "open")

    def test_irrigation_station_take_measurements(self) -> None:
        """Test take_measurements method."""
        config = MockConfig()
        logger = MockLogger()

        # Add a point to config
        point_config = MockPointConfig("Test Point", 2, 0x48, 0)
        config.add_point("testpoint", point_config)

        # Create irrigation station with mocked point
        persister = MockOpenValvePersister(config, logger)
        station = IrrigationStation(config, logger, persister)
        # Replace the point with a mock
        mock_point = MockIrrigationPoint("testpoint")
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
        # This test is no longer relevant since get_valve_states() was removed
        # and process_instructions() now returns valve updates directly
        self.skipTest("get_valve_states() method was removed in refactoring")

    def test_irrigation_station_get_sensor_states(self) -> None:
        """Test get_sensor_states method."""
        config = MockConfig()
        logger = MockLogger()

        # Add two points to config
        point_config1 = MockPointConfig("Test Point 1", 2, 0x48, 0)
        point_config2 = MockPointConfig("Test Point 2", 3, 0x49, 1)
        config.add_point("testpoint1", point_config1)
        config.add_point("testpoint2", point_config2)

        # Create irrigation station with mocked points
        persister = MockOpenValvePersister(config, logger)
        station = IrrigationStation(config, logger, persister)
        # Replace points with mocks
        mock_point1 = MockIrrigationPoint("testpoint1")
        mock_point1.sensor_value = 0.6
        mock_point2 = MockIrrigationPoint("testpoint2")
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

    def test_valve_persistence_integration(self) -> None:
        """Test that valve state is persisted on open/close."""
        config = MockConfig()
        logger = MockLogger()

        # Add two points
        point_config_a = MockPointConfig("Point A", 2, 0x48, 0)
        point_config_b = MockPointConfig("Point B", 3, 0x49, 1)
        config.add_point("pointa", point_config_a)
        config.add_point("pointb", point_config_b)

        # Create station with mock persister
        persister = MockOpenValvePersister(config, logger)
        station = IrrigationStation(config, logger, persister)

        # Replace points with mocks
        mock_point_a = MockIrrigationPoint("pointa")
        mock_point_b = MockIrrigationPoint("pointb")
        station._points["pointa"] = mock_point_a
        station._points["pointb"] = mock_point_b

        # Open valve A via process_instructions
        instructions = [ValveState("pointa", "open")]
        _ = station.process_instructions(instructions)

        # Verify valve opened and persister written
        self.assertEqual(mock_point_a.valve_state, "open")
        self.assertEqual(mock_point_a.open_count, 1)
        self.assertEqual(len(persister.set_calls), 1)
        self.assertEqual(persister.set_calls[0], "pointa")

        # Close valve A by opening valve B
        instructions = [ValveState("pointb", "open")]
        _ = station.process_instructions(instructions)

        # Verify valve A closed, valve B opened, persister updated
        self.assertEqual(mock_point_a.valve_state, "closed")
        self.assertEqual(mock_point_a.close_count, 1)
        self.assertEqual(mock_point_b.valve_state, "open")
        self.assertEqual(mock_point_b.open_count, 1)
        self.assertEqual(len(persister.set_calls), 2)
        self.assertEqual(persister.set_calls[1], "pointb")
        self.assertEqual(len(persister.clear_calls), 1)

        # Close valve B via CLOSED command
        instructions = [ValveState("pointb", "closed")]
        _ = station.process_instructions(instructions)

        # Verify valve B closed and persister deleted
        self.assertEqual(mock_point_b.valve_state, "closed")
        self.assertEqual(mock_point_b.close_count, 1)
        self.assertEqual(len(persister.clear_calls), 2)

    def test_recovery_count_limit(self) -> None:
        """Test that recovery count limits valve restoration after reboots."""
        config = MockConfig()
        logger = MockLogger()
        persister = MockOpenValvePersister(config, logger)

        # Simulate valve opened
        persister.set("pointa")
        self.assertIsNotNone(persister.data)
        self.assertEqual(persister.data["recovery_count"], 0)

        # First restoration (reboot 1) - should succeed
        state1 = persister.get()
        self.assertIsNotNone(state1)
        self.assertEqual(state1.point_id, "pointa")
        # recovery_count still 0 (not incremented yet)
        self.assertEqual(persister.data["recovery_count"], 0)
        persister.increment_opened_valve_recovery_count()
        self.assertEqual(persister.data["recovery_count"], 1)
        self.assertEqual(len(persister.increment_calls), 1)

        # Second restoration (reboot 2) - should succeed
        state2 = persister.get()
        self.assertIsNotNone(state2)
        self.assertEqual(persister.data["recovery_count"], 1)
        persister.increment_opened_valve_recovery_count()
        self.assertEqual(persister.data["recovery_count"], 2)

        # Third restoration (reboot 3) - should succeed
        state3 = persister.get()
        self.assertIsNotNone(state3)
        self.assertEqual(persister.data["recovery_count"], 2)
        persister.increment_opened_valve_recovery_count()
        self.assertEqual(persister.data["recovery_count"], 3)

        # Fourth restoration (reboot 4) - should FAIL (exceeds MAX_RECOVERY_ATTEMPTS=3)
        state4 = persister.get()
        self.assertIsNone(state4)
        # File should be deleted (data set to None) because recovery_count >= limit
        self.assertIsNone(persister.data)

        # After clear (valve closed properly), count resets
        persister.set("pointa")
        self.assertEqual(persister.data["recovery_count"], 0)

        # Missing recovery_count field (backward compatibility)
        persister.data = {"point_id": "pointb", "opened_timestamp": 123456}
        state = persister.get()
        self.assertIsNotNone(state)
        # recovery_count still missing/0 (not incremented yet)
        self.assertEqual(persister.data.get("recovery_count", 0), 0)
        persister.increment_opened_valve_recovery_count()
        self.assertEqual(persister.data.get("recovery_count", 0), 1)


class TestIrrigationStationProcessInstructionsComprehensive(unittest.TestCase):
    """Comprehensive tests for process_instructions() method."""

    def setUp(self) -> None:
        """Set up test fixtures with 3 irrigation points (A, B, C)."""
        # Reset mock time to known state
        mock_time.reset_time()
        mock_time.reset_ticks()
        self.config = MockConfig()
        self.logger = MockLogger()

        # Add three points to config
        point_config_a = MockPointConfig("Point A", 2, 0x48, 0)
        point_config_b = MockPointConfig("Point B", 3, 0x49, 1)
        point_config_c = MockPointConfig("Point C", 4, 0x4A, 2)

        self.config.add_point("A", point_config_a)
        self.config.add_point("B", point_config_b)
        self.config.add_point("C", point_config_c)

        # Create irrigation station
        self.persister = MockOpenValvePersister(self.config, self.logger)
        self.station = IrrigationStation(self.config, self.logger, self.persister)

        # Replace points with enhanced mocks
        self.point_a = MockIrrigationPoint("A")
        self.point_b = MockIrrigationPoint("B")
        self.point_c = MockIrrigationPoint("C")

        self.station._points["A"] = self.point_a
        self.station._points["B"] = self.point_b
        self.station._points["C"] = self.point_c

        # Reset all points to closed state
        self._reset_all_points()

    def _reset_all_points(self) -> None:
        """Reset all points to closed state and clear operation counts."""
        for point in [self.point_a, self.point_b, self.point_c]:
            point.valve_state = "closed"
            point.reset_counts()

    def _set_initial_state(self, open_point_id: str | None) -> None:
        """Set initial state with specified valve open."""
        self._reset_all_points()
        if open_point_id == "A":
            self.point_a.valve_state = "open"
        elif open_point_id == "B":
            self.point_b.valve_state = "open"
        elif open_point_id == "C":
            self.point_c.valve_state = "open"

    def _assert_physical_state(self, expected_open: str | None) -> None:
        """Assert physical valve states match expected."""
        expected_states = {
            "A": "open" if expected_open == "A" else "closed",
            "B": "open" if expected_open == "B" else "closed",
            "C": "open" if expected_open == "C" else "closed",
        }

        for point_id, expected in expected_states.items():
            point = getattr(self, f"point_{point_id.lower()}")
            self.assertEqual(
                point.valve_state,
                expected,
                f"Point {point_id} should be {expected}, but is {point.valve_state}",
            )

    def _assert_status_updates(
        self, updates: list[ValveState], expected: list[tuple[str, str]]
    ) -> None:
        """Assert status updates match expected."""
        self.assertEqual(
            len(updates),
            len(expected),
            f"Expected {len(expected)} updates, got {len(updates)}",
        )

        # Convert updates to dict for easier comparison
        update_dict = {u.point_id: u.state for u in updates}
        expected_dict = dict(expected)

        self.assertEqual(
            update_dict, expected_dict, "Status updates don't match expected"
        )

    def _assert_operation_counts(
        self, expected_counts: dict[str, tuple[int, int]]
    ) -> None:
        """Assert open/close operation counts match expected."""
        for point_id, (expected_open, expected_close) in expected_counts.items():
            point = getattr(self, f"point_{point_id.lower()}")
            self.assertEqual(
                point.open_count,
                expected_open,
                f"Point {point_id} should have {expected_open} open operations, got {point.open_count}",
            )
            self.assertEqual(
                point.close_count,
                expected_close,
                f"Point {point_id} should have {expected_close} close operations, got {point.close_count}",
            )

    # Test Case 1: Basic single-valve operations
    def test_basic_open_from_closed(self) -> None:
        """Test opening a valve from closed state."""
        commands = [ValveState("A", "open")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("A")
        self._assert_status_updates(updates, [("A", "open")])
        self._assert_operation_counts({"A": (1, 0), "B": (0, 0), "C": (0, 0)})

    def test_basic_close_from_open(self) -> None:
        """Test closing a valve from open state."""
        self._set_initial_state("A")
        commands = [ValveState("A", "closed")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state(None)
        self._assert_status_updates(updates, [("A", "closed")])
        self._assert_operation_counts({"A": (0, 1), "B": (0, 0), "C": (0, 0)})

    def test_open_already_open(self) -> None:
        """Test opening a valve that's already open (no-op)."""
        self._set_initial_state("A")
        commands = [ValveState("A", "open")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("A")
        self._assert_status_updates(updates, [("A", "open")])
        self._assert_operation_counts(
            {"A": (0, 0), "B": (0, 0), "C": (0, 0)}
        )  # No operations

    def test_close_already_closed(self) -> None:
        """Test closing a valve that's already closed (no-op)."""
        commands = [ValveState("A", "closed")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state(None)
        self._assert_status_updates(updates, [("A", "closed")])
        self._assert_operation_counts(
            {"A": (0, 0), "B": (0, 0), "C": (0, 0)}
        )  # No operations

    # Test Case 2: Multiple valve exclusivity
    def test_open_a_then_b_all_closed(self) -> None:
        """Test Open A, then Open B when all valves are closed."""
        commands = [ValveState("A", "open"), ValveState("B", "open")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("B")  # Last open wins
        self._assert_status_updates(updates, [("A", "closed"), ("B", "open")])
        self._assert_operation_counts({"A": (0, 0), "B": (1, 0), "C": (0, 0)})

    def test_open_a_then_b_a_initially_open(self) -> None:
        """Test Open A, then Open B when A is initially open."""
        self._set_initial_state("A")
        commands = [ValveState("A", "open"), ValveState("B", "open")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("B")
        self._assert_status_updates(updates, [("A", "closed"), ("B", "open")])
        self._assert_operation_counts({"A": (0, 1), "B": (1, 0), "C": (0, 0)})

    def test_open_a_b_c_sequence(self) -> None:
        """Test Open A, Open B, Open C sequence."""
        commands = [
            ValveState("A", "open"),
            ValveState("B", "open"),
            ValveState("C", "open"),
        ]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("C")  # Last open wins
        self._assert_status_updates(
            updates,
            [
                ("A", "closed"),
                ("B", "closed"),
                ("C", "open"),
            ],
        )
        self._assert_operation_counts({"A": (0, 0), "B": (0, 0), "C": (1, 0)})

    def test_open_a_close_a_open_b(self) -> None:
        """Test Open A, Close A, Open B sequence."""
        commands = [
            ValveState("A", "open"),
            ValveState("A", "closed"),
            ValveState("B", "open"),
        ]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("B")
        self._assert_status_updates(
            updates,
            [
                ("A", "closed"),
                ("B", "open"),
            ],
        )
        self._assert_operation_counts({"A": (0, 0), "B": (1, 0), "C": (0, 0)})

    # Test Case 3: Edge cases with initial states
    def test_open_b_when_a_initially_open(self) -> None:
        """Test Open B when A is initially open."""
        self._set_initial_state("A")
        commands = [ValveState("B", "open")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("B")
        self._assert_status_updates(updates, [("A", "closed"), ("B", "open")])
        self._assert_operation_counts({"A": (0, 1), "B": (1, 0), "C": (0, 0)})

    def test_close_a_when_a_initially_open(self) -> None:
        """Test Close A when A is initially open."""
        self._set_initial_state("A")
        commands = [ValveState("A", "closed")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state(None)
        self._assert_status_updates(updates, [("A", "closed")])
        self._assert_operation_counts({"A": (0, 1), "B": (0, 0), "C": (0, 0)})

    def test_close_b_when_a_initially_open(self) -> None:
        """Test Close B when A is initially open (B not open)."""
        self._set_initial_state("A")
        commands = [ValveState("B", "closed")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("A")  # A stays open
        self._assert_status_updates(updates, [("B", "closed")])
        self._assert_operation_counts(
            {"A": (0, 0), "B": (0, 0), "C": (0, 0)}
        )  # No operations

    # Test Case 4: Command sequence tests
    def test_open_a_close_b_b_not_open(self) -> None:
        """Test Open A, Close B (B not open)."""
        commands = [ValveState("A", "open"), ValveState("B", "closed")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("A")
        self._assert_status_updates(updates, [("A", "open"), ("B", "closed")])
        self._assert_operation_counts({"A": (1, 0), "B": (0, 0), "C": (0, 0)})

    def test_close_a_open_b_a_not_open(self) -> None:
        """Test Close A, Open B (A not open)."""
        commands = [ValveState("A", "closed"), ValveState("B", "open")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("B")
        self._assert_status_updates(updates, [("A", "closed"), ("B", "open")])
        self._assert_operation_counts({"A": (0, 0), "B": (1, 0), "C": (0, 0)})

    def test_open_a_open_b_close_a(self) -> None:
        """Test Open A, Open B, Close A (B should stay open)."""
        commands = [
            ValveState("A", "open"),
            ValveState("B", "open"),
            ValveState("A", "closed"),
        ]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("B")
        self._assert_status_updates(
            updates,
            [
                ("A", "closed"),
                ("B", "open"),
            ],
        )
        self._assert_operation_counts({"A": (0, 0), "B": (1, 0), "C": (0, 0)})

    def test_multiple_opens_same_valve(self) -> None:
        """Test multiple Open commands for same valve."""
        commands = [
            ValveState("A", "open"),
            ValveState("A", "open"),
            ValveState("A", "open"),
        ]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("A")
        self._assert_status_updates(updates, [("A", "open")])
        self._assert_operation_counts({"A": (1, 0), "B": (0, 0), "C": (0, 0)})

    # Test Case 5: Error handling tests
    def test_empty_instructions(self) -> None:
        """Test empty instructions list."""
        updates = self.station.process_instructions([])

        self._assert_physical_state(None)
        self.assertEqual(len(updates), 0)
        self._assert_operation_counts({"A": (0, 0), "B": (0, 0), "C": (0, 0)})

    def test_unknown_point_id(self) -> None:
        """Test command with unknown point_id."""
        commands = [ValveState("X", "open")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state(None)
        self.assertEqual(len(updates), 0)
        self._assert_operation_counts({"A": (0, 0), "B": (0, 0), "C": (0, 0)})
        # Check that error was logged
        self.assertTrue(
            any("Unknown irrigation point: X" in msg for msg in self.logger.messages)
        )

    def test_mixed_valid_invalid_commands(self) -> None:
        """Test mix of valid and invalid commands."""
        commands = [
            ValveState("A", "open"),
            ValveState("X", "open"),  # Unknown point
            ValveState("B", "open"),
        ]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("B")  # Last valid open wins
        self._assert_status_updates(updates, [("A", "closed"), ("B", "open")])
        self._assert_operation_counts({"A": (0, 0), "B": (1, 0), "C": (0, 0)})

    # Test Case 6: Complex scenarios
    def test_complex_sequence_1(self) -> None:
        """Test complex sequence: Open A, Close B, Open C."""
        commands = [
            ValveState("A", "open"),
            ValveState("B", "closed"),
            ValveState("C", "open"),
        ]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("C")
        self._assert_status_updates(
            updates,
            [
                ("A", "closed"),
                ("B", "closed"),
                ("C", "open"),
            ],
        )
        self._assert_operation_counts({"A": (0, 0), "B": (0, 0), "C": (1, 0)})

    def test_complex_sequence_2(self) -> None:
        """Test complex sequence: Close A, Close B, Open C with A initially open."""
        self._set_initial_state("A")
        commands = [
            ValveState("A", "closed"),
            ValveState("B", "closed"),
            ValveState("C", "open"),
        ]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("C")
        self._assert_status_updates(
            updates,
            [
                ("A", "closed"),
                ("B", "closed"),
                ("C", "open"),
            ],
        )
        self._assert_operation_counts({"A": (0, 1), "B": (0, 0), "C": (1, 0)})

    def test_multiple_no_op_closes(self) -> None:
        """Test multiple Close commands for valves that are not open."""
        commands = [
            ValveState("A", "closed"),
            ValveState("B", "closed"),
            ValveState("C", "closed"),
        ]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state(None)
        self._assert_status_updates(
            updates,
            [
                ("A", "closed"),
                ("B", "closed"),
                ("C", "closed"),
            ],
        )
        self._assert_operation_counts({"A": (0, 0), "B": (0, 0), "C": (0, 0)})

    # Test Case 7: Additional edge cases and requirements
    def test_additional_update_when_closing_current_valve(self) -> None:
        """Test the 'additional update' requirement when closing current valve to open new one."""
        self._set_initial_state("A")
        commands = [ValveState("B", "open")]
        updates = self.station.process_instructions(commands)

        # Should have 2 updates: A closed (additional), B open
        self._assert_physical_state("B")
        self._assert_status_updates(
            updates,
            [
                ("A", "closed"),
                ("B", "open"),
            ],
        )
        self._assert_operation_counts({"A": (0, 1), "B": (1, 0), "C": (0, 0)})

    def test_no_additional_update_when_same_valve(self) -> None:
        """Test no additional update when opening already open valve."""
        self._set_initial_state("A")
        commands = [ValveState("A", "open")]
        updates = self.station.process_instructions(commands)

        # Should have 1 update: A open (no additional)
        self._assert_physical_state("A")
        self._assert_status_updates(updates, [("A", "open")])
        self._assert_operation_counts({"A": (0, 0), "B": (0, 0), "C": (0, 0)})

    def test_valve_states_dict_contains_only_valid_entries(self) -> None:
        """Test that valve_states dictionary doesn't contain None or invalid keys."""
        commands = [
            ValveState("A", "open"),
            ValveState("B", "open"),
            ValveState("C", "closed"),
        ]
        updates = self.station.process_instructions(commands)

        # Check no None keys in updates
        for update in updates:
            self.assertIsNotNone(update.point_id, f"Update has None point_id: {update}")
            self.assertIn(
                update.point_id, ["A", "B", "C"], f"Invalid point_id: {update.point_id}"
            )

        self._assert_physical_state("B")

    def test_minimal_operations_for_multiple_commands(self) -> None:
        """Test that minimal physical operations are performed."""
        # A open, B open, C open - should only open C
        commands = [
            ValveState("A", "open"),
            ValveState("B", "open"),
            ValveState("C", "open"),
        ]
        self.station.process_instructions(commands)

        # Should only have 1 open operation (C) and no close operations
        self._assert_operation_counts({"A": (0, 0), "B": (0, 0), "C": (1, 0)})

    def test_command_override_sequence(self) -> None:
        """Test that later commands properly override earlier ones."""
        commands = [
            ValveState("A", "open"),
            ValveState("B", "open"),
            ValveState("A", "open"),  # Should override B
        ]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("A")
        self._assert_status_updates(
            updates,
            [
                ("A", "open"),
                ("B", "closed"),
            ],
        )
        self._assert_operation_counts({"A": (1, 0), "B": (0, 0), "C": (0, 0)})

    def test_close_then_open_same_valve(self) -> None:
        """Test close then open same valve in sequence (last command wins, no net change)."""
        self._set_initial_state("A")
        commands = [
            ValveState("A", "closed"),
            ValveState("A", "open"),
        ]
        updates = self.station.process_instructions(commands)

        # Last command "open" wins, so valve should be open (no net change from initial)
        self._assert_physical_state("A")
        self._assert_status_updates(updates, [("A", "open")])
        # No operations because initial state (open) matches final desired state (open)
        self._assert_operation_counts({"A": (0, 0), "B": (0, 0), "C": (0, 0)})

    def test_all_valves_closed_initially_open_new(self) -> None:
        """Test opening a valve when all valves are initially closed."""
        commands = [ValveState("B", "open")]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("B")
        self._assert_status_updates(updates, [("B", "open")])
        self._assert_operation_counts({"A": (0, 0), "B": (1, 0), "C": (0, 0)})

    def test_invalid_state_handling(self) -> None:
        """Test that invalid states are caught by ValveState constructor."""
        # This test verifies that ValveState constructor validates states
        # Invalid state should raise ValueError
        with self.assertRaises(ValueError):
            ValveState("A", "invalid_state")

        # Valid states should not raise
        try:
            ValveState("A", "open")
            ValveState("A", "closed")
            ValveState("A", "OPEN")  # Should be case-insensitive
            ValveState("A", "CLOSED")
        except ValueError:
            self.fail("Valid states should not raise ValueError")

    def test_mixed_case_commands(self) -> None:
        """Test that commands with mixed case are handled correctly."""
        commands = [
            ValveState("A", "OPEN"),  # Uppercase
            ValveState("B", "Closed"),  # Capitalized
            ValveState("C", "open"),  # lowercase
        ]
        updates = self.station.process_instructions(commands)

        self._assert_physical_state("C")  # Last open wins
        # ValveState normalizes to lowercase
        self._assert_status_updates(
            updates,
            [
                ("A", "closed"),
                ("B", "closed"),
                ("C", "open"),
            ],
        )

    def test_valve_timeout_tracking(self) -> None:
        """Test that valve open timestamp is tracked correctly."""
        # Initially no valve open
        self.assertIsNone(self.station._last_valve_open_time)

        # Open valve A
        commands = [ValveState("A", "open")]
        self.station.process_instructions(commands)

        # Check timestamp set
        self.assertIsNotNone(self.station._last_valve_open_time)
        initial_time = self.station._last_valve_open_time

        # Advance time by 10 seconds
        mock_time.advance(10.0)

        # Open valve B (closes A)
        commands = [ValveState("B", "open")]
        self.station.process_instructions(commands)

        # Check timestamp updated (new valve opened)
        self.assertIsNotNone(self.station._last_valve_open_time)
        self.assertNotEqual(self.station._last_valve_open_time, initial_time)

        # Close valve B
        commands = [ValveState("B", "closed")]
        self.station.process_instructions(commands)

        # Check timestamp cleared
        self.assertIsNone(self.station._last_valve_open_time)

    def test_check_valve_timeout(self) -> None:
        """Test auto-closing valve after timeout."""
        # Open valve A
        commands = [ValveState("A", "open")]
        self.station.process_instructions(commands)

        # Not enough time elapsed - should not close
        result = self.station.check_valve_timeout()  # No argument
        self.assertIsNone(result)
        self.assertEqual(self.point_a.valve_state, "open")

        # Advance time just under timeout (44 minutes)
        mock_time.advance(44 * 60)
        result = self.station.check_valve_timeout()
        self.assertIsNone(result)
        self.assertEqual(self.point_a.valve_state, "open")

        # Advance past timeout (additional 2 minutes)
        mock_time.advance(2 * 60)
        result = self.station.check_valve_timeout()
        self.assertIsNotNone(result)
        self.assertEqual(result.point_id, "A")
        self.assertEqual(result.state, "closed")
        self.assertEqual(self.point_a.valve_state, "closed")
        self.assertIsNone(self.station._last_valve_open_time)

        # Check logging
        auto_close_logs = [msg for msg in self.logger.messages if "[Auto-Close]" in msg]
        self.assertEqual(len(auto_close_logs), 1)
        self.assertIn("A", auto_close_logs[0])


if __name__ == "__main__":
    # Run the tests
    unittest.main()
