"""Test irrigation_station.py using simple mocks."""

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
    mock_ads1115,
)


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
sys.modules["datetime"] = mock_datetime
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

    def __init__(self, name, valve_pin, mosfet_pin, ads_address, ads_channel):
        self.name = name
        self.valve_pin = valve_pin
        self.mosfet_pin = mosfet_pin
        self.ads_address = ads_address
        self.ads_channel = ads_channel
        self.id = name.lower().replace(" ", "")
        self.rolling_window = 3  # Required by Sensor class
        self.ema_alpha = 0.2  # Required by Sensor class


class MockLogger:
    """Mock Logger."""

    def __init__(self):
        self.messages = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)


def test_irrigation_station_initialization() -> bool:
    """Test irrigation station initialization."""
    print("Testing irrigation station initialization...")

    config = MockConfig()
    logger = MockLogger()

    # Add a test point
    point_config = MockPointConfig("Location A", 2, 21, 0x48, 0)
    config.add_point("locationa", point_config)

    # Reset mock pins
    mock_machine.pins_created.clear()

    try:
        # Create irrigation station
        station = IrrigationStation(config, logger)  # type: ignore

        # Check that I2C was initialized
        if not hasattr(station, "_i2c"):
            print(f"  ❌ I2C not initialized")
            return False

        # Check that ADS modules were set up
        if not hasattr(station, "_ads_modules"):
            print(f"  ❌ ADS modules not set up")
            return False

        # Check that irrigation points were created
        if len(station._points) != 1:
            print(f"  ❌ Expected 1 irrigation point, got {len(station._points)}")
            return False

        # Check that point exists
        if "locationa" not in station._points:
            print(f"  ❌ Point 'locationa' not in station._points")
            return False

        # Check that timer was initialized
        if not hasattr(station, "_measurement_timer"):
            print(f"  ❌ Measurement timer not initialized")
            return False

    except Exception as e:
        print(f"  ❌ IrrigationStation initialization raised exception: {e}")
        return False

    print("  ✅ Irrigation station initialization test passed")
    return True


def test_irrigation_station_get_point() -> bool:
    """Test get_point method."""
    print("Testing get_point()...")

    config = MockConfig()
    logger = MockLogger()

    # Add test points
    point_config_a = MockPointConfig("Location A", 2, 21, 0x48, 0)
    point_config_b = MockPointConfig("Location B", 3, 22, 0x49, 1)
    config.add_point("locationa", point_config_a)
    config.add_point("locationb", point_config_b)

    # Reset mock pins
    mock_machine.pins_created.clear()

    try:
        # Create irrigation station
        station = IrrigationStation(config, logger)  # type: ignore

        # Get existing point
        point_a = station.get_point("locationa")
        if point_a.config.name != "Location A":
            print(f"  ❌ get_point('locationa') returned wrong point")
            return False

        # Get another existing point
        point_b = station.get_point("locationb")
        if point_b.config.name != "Location B":
            print(f"  ❌ get_point('locationb') returned wrong point")
            return False

        # Try to get non-existent point
        try:
            station.get_point("nonexistent")
            print(f"  ❌ get_point('nonexistent') should have raised ValueError")
            return False
        except ValueError:
            pass  # Expected
        except Exception as e:
            print(f"  ❌ get_point('nonexistent') raised wrong exception: {e}")
            return False

    except Exception as e:
        print(f"  ❌ get_point test raised exception: {e}")
        return False

    print("  ✅ get_point() test passed")
    return True


def test_irrigation_station_provide_instructions() -> bool:
    """Test provide_instructions method."""
    print("Testing provide_instructions()...")

    config = MockConfig()
    logger = MockLogger()

    # Add a test point
    point_config = MockPointConfig("Location A", 2, 21, 0x48, 0)
    config.add_point("locationa", point_config)
    config.station_id = "test123"

    # Reset mock pins
    mock_machine.pins_created.clear()

    try:
        # Create irrigation station
        station = IrrigationStation(config, logger)  # type: ignore

        # Provide instructions
        instructions = [
            ("irrigation/test123/locationa/valve/set", "open"),
            ("irrigation/test123/locationa/valve/set", "closed"),
        ]
        station.provide_instructions(instructions)

        # Check that instructions were stored
        if len(station._pending_instructions) != 2:
            print(
                f"  ❌ Expected 2 pending instructions, got {len(station._pending_instructions)}"
            )
            return False

        # Check instruction content
        if station._pending_instructions[0] != (
            "irrigation/test123/locationa/valve/set",
            "open",
        ):
            print(f"  ❌ First instruction incorrect")
            return False

    except Exception as e:
        print(f"  ❌ provide_instructions test raised exception: {e}")
        return False

    print("  ✅ provide_instructions() test passed")
    return True


def test_irrigation_station_execute_pending_tasks() -> bool:
    """Test execute_pending_tasks method."""
    print("Testing execute_pending_tasks()...")

    config = MockConfig()
    logger = MockLogger()

    # Add a test point
    point_config = MockPointConfig("Location A", 2, 21, 0x48, 0)
    config.add_point("locationa", point_config)
    config.station_id = "test123"

    # Reset mock pins
    mock_machine.pins_created.clear()

    try:
        # Create irrigation station
        station = IrrigationStation(config, logger)  # type: ignore

        # Provide instructions
        instructions = [
            ("irrigation/test123/locationa/valve/set", "open"),
        ]
        station.provide_instructions(instructions)

        # Execute pending tasks
        station.execute_pending_tasks()

        # Check that instructions were processed
        if len(station._pending_instructions) != 0:
            print(
                f"  ❌ Pending instructions should be cleared after execute_pending_tasks"
            )
            return False

        # Check that valve was opened (pin should be created)
        if len(mock_machine.pins_created) == 0:
            print(f"  ❌ No pins created for valve operation")
            return False

    except Exception as e:
        print(f"  ❌ execute_pending_tasks test raised exception: {e}")
        return False

    print("  ✅ execute_pending_tasks() test passed")
    return True


def test_irrigation_station_get_status_updates() -> bool:
    """Test get_status_updates method."""
    print("Testing get_status_updates()...")

    config = MockConfig()
    logger = MockLogger()

    # Add a test point
    point_config = MockPointConfig("Location A", 2, 21, 0x48, 0)
    config.add_point("locationa", point_config)
    config.station_id = "test123"

    # Reset mock pins
    mock_machine.pins_created.clear()

    try:
        # Create irrigation station
        station = IrrigationStation(config, logger)  # type: ignore

        # Manually add a status update
        station._status_updates = [
            ("irrigation/test123/locationa/valve/state", "open"),
            ("irrigation/test123/locationa/moisture", "0.75"),
        ]

        # Get status updates
        updates = station.get_status_updates()

        # Check that updates were returned
        if len(updates) != 2:
            print(f"  ❌ Expected 2 status updates, got {len(updates)}")
            return False

        # Check update content
        if updates[0] != ("irrigation/test123/locationa/valve/state", "open"):
            print(f"  ❌ First status update incorrect")
            return False

        # Check that status updates were cleared
        if len(station._status_updates) != 0:
            print(f"  ❌ Status updates should be cleared after get_status_updates")
            return False

    except Exception as e:
        print(f"  ❌ get_status_updates test raised exception: {e}")
        return False

    print("  ✅ get_status_updates() test passed")
    return True


def main() -> None:
    """Run all irrigation station tests."""
    print("=== Testing irrigation_station.py ===")

    passed = 0
    total = 0

    # Run tests
    total += 1
    if test_irrigation_station_initialization():
        passed += 1

    total += 1
    if test_irrigation_station_get_point():
        passed += 1

    total += 1
    if test_irrigation_station_provide_instructions():
        passed += 1

    total += 1
    if test_irrigation_station_execute_pending_tasks():
        passed += 1

    total += 1
    if test_irrigation_station_get_status_updates():
        passed += 1

    # Summary
    print("=" * 40)
    if passed == total:
        print("✅ All irrigation station tests passed!")
    else:
        print(f"❌ {passed}/{total} tests passed")


if __name__ == "__main__":
    main()
