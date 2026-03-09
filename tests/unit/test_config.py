"""Test config.py using simple mocks."""

import sys
import json

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
from config import Config, IrrigationPointConfig, NetworkConfig  # type: ignore


def test_clean_string() -> bool:
    """Test _clean_string function."""
    print("Testing _clean_string()...")

    # Import the function directly
    from config import _clean_string  # type: ignore

    # Test cases
    test_cases = [
        ("Hello World", "helloworld"),
        ("Test-123_ABC", "test123abc"),
        ("  Spaces  ", "spaces"),
        ("Special!@#$%Chars", "specialchars"),
        ("", ""),
    ]

    for input_str, expected in test_cases:
        result = _clean_string(input_str)
        if result != expected:
            print(
                f"  ❌ _clean_string('{input_str}') = '{result}', expected '{expected}'"
            )
            return False

    print("  ✅ _clean_string() test passed")
    return True


def test_get_if_valid() -> bool:
    """Test _get_if_valid function."""
    print("Testing _get_if_valid()...")

    # Import the function directly
    from config import _get_if_valid  # type: ignore

    # Test valid case
    conf = {"name": "Test", "count": 42, "enabled": True}

    # Valid string
    try:
        result = _get_if_valid("name", conf, str)
        if result != "Test":
            print(f"  ❌ _get_if_valid('name') = '{result}', expected 'Test'")
            return False
    except Exception as e:
        print(f"  ❌ _get_if_valid('name') raised exception: {e}")
        return False

    # Valid int
    try:
        result = _get_if_valid("count", conf, int)
        if result != 42:
            print(f"  ❌ _get_if_valid('count') = {result}, expected 42")
            return False
    except Exception as e:
        print(f"  ❌ _get_if_valid('count') raised exception: {e}")
        return False

    # Valid bool
    try:
        result = _get_if_valid("enabled", conf, bool)
        if result != True:
            print(f"  ❌ _get_if_valid('enabled') = {result}, expected True")
            return False
    except Exception as e:
        print(f"  ❌ _get_if_valid('enabled') raised exception: {e}")
        return False

    # Test missing key
    try:
        _get_if_valid("missing", conf, str)
        print(f"  ❌ _get_if_valid('missing') should have raised KeyError")
        return False
    except KeyError:
        pass  # Expected
    except Exception as e:
        print(f"  ❌ _get_if_valid('missing') raised wrong exception: {e}")
        return False

    # Test wrong type
    try:
        _get_if_valid("name", conf, int)
        print(f"  ❌ _get_if_valid('name', type=int) should have raised TypeError")
        return False
    except TypeError:
        pass  # Expected
    except Exception as e:
        print(f"  ❌ _get_if_valid('name', type=int) raised wrong exception: {e}")
        return False

    # Test empty string
    try:
        _get_if_valid("empty", {"empty": ""}, str)
        print(
            f"  ❌ _get_if_valid('empty') with empty string should have raised ValueError"
        )
        return False
    except ValueError:
        pass  # Expected
    except Exception as e:
        print(
            f"  ❌ _get_if_valid('empty') with empty string raised wrong exception: {e}"
        )
        return False

    print("  ✅ _get_if_valid() test passed")
    return True


def test_network_config() -> bool:
    """Test NetworkConfig class."""
    print("Testing NetworkConfig...")

    # Valid config
    conf = {
        "wifi_ssid": "MyNetwork",
        "wifi_password": "secret123",
        "mqtt_broker_ip": "192.168.1.100",
    }

    try:
        network = NetworkConfig(conf)

        if network.wifi_ssid != "MyNetwork":
            print(f"  ❌ wifi_ssid = '{network.wifi_ssid}', expected 'MyNetwork'")
            return False

        if network.wifi_password != "secret123":
            print(
                f"  ❌ wifi_password = '{network.wifi_password}', expected 'secret123'"
            )
            return False

        if network.mqtt_broker_ip != "192.168.1.100":
            print(
                f"  ❌ mqtt_broker_ip = '{network.mqtt_broker_ip}', expected '192.168.1.100'"
            )
            return False

    except Exception as e:
        print(f"  ❌ NetworkConfig raised exception: {e}")
        return False

    # Test missing field
    try:
        NetworkConfig({"wifi_ssid": "Test", "wifi_password": "secret"})
        print(
            f"  ❌ NetworkConfig with missing mqtt_broker_ip should have raised KeyError"
        )
        return False
    except KeyError:
        pass  # Expected
    except Exception as e:
        print(f"  ❌ NetworkConfig with missing field raised wrong exception: {e}")
        return False

    print("  ✅ NetworkConfig test passed")
    return True


def test_irrigation_point_config() -> bool:
    """Test IrrigationPointConfig class."""
    print("Testing IrrigationPointConfig...")

    # Valid config
    conf = {
        "name": "Location A",
        "valve_pin": 2,
        "mosfet_pin": 21,
        "ads_address": "0x48",
        "ads_channel": 0,
    }

    try:
        point = IrrigationPointConfig(conf)

        if point.name != "Location A":
            print(f"  ❌ name = '{point.name}', expected 'Location A'")
            return False

        if point.valve_pin != 2:
            print(f"  ❌ valve_pin = {point.valve_pin}, expected 2")
            return False

        if point.mosfet_pin != 21:
            print(f"  ❌ mosfet_pin = {point.mosfet_pin}, expected 21")
            return False

        if point.ads_address != 0x48:
            print(f"  ❌ ads_address = {hex(point.ads_address)}, expected 0x48")
            return False

        if point.ads_channel != 0:
            print(f"  ❌ ads_channel = {point.ads_channel}, expected 0")
            return False

        if point.id != "locationa":
            print(f"  ❌ id = '{point.id}', expected 'locationa'")
            return False

        # Check default values
        if point.rolling_window != 5:
            print(f"  ❌ rolling_window = {point.rolling_window}, expected 5")
            return False

        if point.ema_alpha != 0.2:
            print(f"  ❌ ema_alpha = {point.ema_alpha}, expected 0.2")
            return False

    except Exception as e:
        print(f"  ❌ IrrigationPointConfig raised exception: {e}")
        return False

    # Test invalid ADS address
    try:
        IrrigationPointConfig(
            {
                "name": "Test",
                "valve_pin": 2,
                "mosfet_pin": 21,
                "ads_address": "0x99",  # Invalid address
                "ads_channel": 0,
            }
        )
        print(
            f"  ❌ IrrigationPointConfig with invalid ads_address should have raised ValueError"
        )
        return False
    except ValueError:
        pass  # Expected
    except Exception as e:
        print(
            f"  ❌ IrrigationPointConfig with invalid ads_address raised wrong exception: {e}"
        )
        return False

    # Test invalid ADS channel
    try:
        IrrigationPointConfig(
            {
                "name": "Test",
                "valve_pin": 2,
                "mosfet_pin": 21,
                "ads_address": "0x48",
                "ads_channel": 5,  # Invalid channel
            }
        )
        print(
            f"  ❌ IrrigationPointConfig with invalid ads_channel should have raised ValueError"
        )
        return False
    except ValueError:
        pass  # Expected
    except Exception as e:
        print(
            f"  ❌ IrrigationPointConfig with invalid ads_channel raised wrong exception: {e}"
        )
        return False

    print("  ✅ IrrigationPointConfig test passed")
    return True


def test_config_class() -> bool:
    """Test Config class."""
    print("Testing Config class...")

    # Use fixture file
    test_file = "tests/fixtures/test_config.json"

    try:
        # Create config from fixture file
        config = Config(test_file)

        # Check station info
        if config.station_name != "Backyard irrigation station":
            print(
                f"  ❌ station_name = '{config.station_name}', expected 'Backyard irrigation station'"
            )
            return False

        # Check device ID (based on mock unique_id)
        expected_id = "".join(f"{b:02x}" for b in mock_machine.unique_id())[-8:]
        if config.station_id != expected_id:
            print(f"  ❌ station_id = '{config.station_id}', expected '{expected_id}'")
            return False

        # Check MQTT ID
        expected_mqtt_id = f"backyardirrigationstation-{expected_id}"
        if config.station_mqtt_id != expected_mqtt_id:
            print(
                f"  ❌ station_mqtt_id = '{config.station_mqtt_id}', expected '{expected_mqtt_id}'"
            )
            return False

        # Check network config
        if config.network.wifi_ssid != "MyNetwork":
            print(
                f"  ❌ network.wifi_ssid = '{config.network.wifi_ssid}', expected 'MyNetwork'"
            )
            return False

        # Check global parameters
        if config.rolling_window != 3:
            print(f"  ❌ rolling_window = {config.rolling_window}, expected 3")
            return False

        if config.ema_alpha != 0.2:
            print(f"  ❌ ema_alpha = {config.ema_alpha}, expected 0.2")
            return False

        if config.publish_interval_ms != 5 * 60 * 1000:  # 5 minutes in ms
            print(
                f"  ❌ publish_interval_ms = {config.publish_interval_ms}, expected {5 * 60 * 1000}"
            )
            return False

        # Check irrigation points
        if len(config.irrigation_points) != 2:
            print(
                f"  ❌ Expected 2 irrigation points, got {len(config.irrigation_points)}"
            )
            return False

        # Check first point
        point_a = config.irrigation_points.get("locationa")
        if not point_a:
            print(f"  ❌ Point 'locationa' not found")
            return False

        if point_a.name != "Location A":
            print(f"  ❌ point_a.name = '{point_a.name}', expected 'Location A'")
            return False

        # Check that global parameters were copied to points
        if point_a.rolling_window != 3:
            print(f"  ❌ point_a.rolling_window = {point_a.rolling_window}, expected 3")
            return False

        if point_a.ema_alpha != 0.2:
            print(f"  ❌ point_a.ema_alpha = {point_a.ema_alpha}, expected 0.2")
            return False

        # Check __str__ method
        str_repr = str(config)
        if not str_repr.startswith("Irrigation station config:"):
            print(f"  ❌ str(config) doesn't start with expected prefix")
            return False

    except Exception as e:
        print(f"  ❌ Config raised exception: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("  ✅ Config class test passed")
    return True


def main() -> None:
    """Run all config tests."""
    print("=== Testing config.py ===")

    passed = 0
    total = 0

    # Run tests
    total += 1
    if test_clean_string():
        passed += 1

    total += 1
    if test_get_if_valid():
        passed += 1

    total += 1
    if test_network_config():
        passed += 1

    total += 1
    if test_irrigation_point_config():
        passed += 1

    total += 1
    if test_config_class():
        passed += 1

    # Summary
    print("=" * 40)
    if passed == total:
        print("✅ All config tests passed!")
    else:
        print(f"❌ {passed}/{total} tests passed")


if __name__ == "__main__":
    main()
