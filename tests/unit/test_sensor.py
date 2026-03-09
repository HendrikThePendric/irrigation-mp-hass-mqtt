"""Test sensor.py using simple mocks."""

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
    Timer = type("MockTimer", (), {"init": lambda self, **kwargs: None, "ONE_SHOT": 0})
    reset = lambda: None


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


def test_sensor_initialization() -> bool:
    """Test sensor initialization."""
    print("Testing sensor initialization...")

    config = MockConfig("Test Sensor", 21, 0)
    ads = ADS1115Module.ADS1115()
    logger = MockLogger()

    # Reset mock pins
    mock_machine.pins_created.clear()

    # Create sensor
    sensor = Sensor(config, ads, logger)  # type: ignore

    # Check that MOSFET pin was created
    if len(mock_machine.pins_created) != 1:
        print(
            f"  ❌ Expected 1 pin created for MOSFET, got {len(mock_machine.pins_created)}"
        )
        return False

    # Check that MOSFET is initially off
    mosfet_pin = mock_machine.pins_created[0]
    if mosfet_pin._value != 0:
        print(f"  ❌ MOSFET should be off (0) initially, got {mosfet_pin._value}")
        return False

    # Check initial sensor value
    if sensor._value != 0.5:
        print(f"  ❌ Initial sensor value should be 0.5, got {sensor._value}")
        return False

    print("  ✅ Sensor initialization test passed")
    return True


def test_sensor_measure_normal() -> bool:
    """Test sensor measurement with normal reading."""
    print("Testing sensor measurement (normal)...")

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
    if "on" not in [call[0] for call in mosfet_pin.calls]:
        print(f"  ❌ MOSFET should have been turned on")
        return False

    if "off" not in [call[0] for call in mosfet_pin.calls]:
        print(f"  ❌ MOSFET should have been turned off")
        return False

    # Check that ADS1115 was called correctly
    if len(ads.read_calls) == 0:
        print(f"  ❌ ADS1115.read() should have been called")
        return False

    # Check channel
    rate, channel = ads.read_calls[0]
    if channel != config.ads_channel:
        print(
            f"  ❌ ADS1115.read() called with wrong channel: {channel}, expected {config.ads_channel}"
        )
        return False

    # Check that raw_to_v was called
    if len(ads.raw_to_v_calls) == 0:
        print(f"  ❌ ADS1115.raw_to_v() should have been called")
        return False

    # Check sensor value (should be around 0.5 with 2.5V reading)
    value = sensor.get_value()
    expected = 0.5  # 2.5V / 5V = 0.5
    if abs(value - expected) > 0.01:
        print(f"  ❌ Sensor value should be ~{expected}, got {value}")
        return False

    print("  ✅ Sensor measurement (normal) test passed")
    return True


def test_sensor_measure_out_of_range() -> bool:
    """Test sensor measurement with out-of-range reading."""
    print("Testing sensor measurement (out of range)...")

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
    try:
        sensor.measure()
    except Exception as e:
        print(f"  ❌ Sensor.measure() should not crash on out-of-range reading: {e}")
        return False

    # Check that error was logged
    error_logged = any("Error reading sensor" in msg for msg in logger.messages)
    if not error_logged:
        print(f"  ❌ Should have logged error for out-of-range reading")
        return False

    # Check that sensor value remains at initial value (last known good value)
    final_value = sensor.get_value()
    if final_value != initial_value:
        print(
            f"  ❌ Sensor value should remain at last known value {initial_value} on error, got {final_value}"
        )
        return False

    print("  ✅ Sensor measurement (out of range) test passed")
    return True


def test_sensor_get_value() -> bool:
    """Test sensor get_value method."""
    print("Testing sensor get_value()...")

    config = MockConfig("Test Sensor", 21, 0)
    ads = ADS1115Module.ADS1115()
    logger = MockLogger()

    # Create sensor
    sensor = Sensor(config, ads, logger)  # type: ignore

    # Initial value should be 0.5
    value = sensor.get_value()
    if value != 0.5:
        print(f"  ❌ Initial get_value() should return 0.5, got {value}")
        return False

    # Change internal value and check get_value returns it
    sensor._value = 0.75
    value = sensor.get_value()
    if value != 0.75:
        print(f"  ❌ get_value() should return current value 0.75, got {value}")
        return False

    print("  ✅ Sensor get_value() test passed")
    return True


def main() -> None:
    """Run all sensor tests."""
    print("=== Testing sensor.py ===")

    passed = 0
    total = 0

    # Run tests
    total += 1
    if test_sensor_initialization():
        passed += 1

    total += 1
    if test_sensor_measure_normal():
        passed += 1

    total += 1
    if test_sensor_measure_out_of_range():
        passed += 1

    total += 1
    if test_sensor_get_value():
        passed += 1

    # Summary
    print("=" * 40)
    if passed == total:
        print("✅ All sensor tests passed!")
    else:
        print(f"❌ {passed}/{total} tests passed")


if __name__ == "__main__":
    main()
