"""Test config.py using unittest framework."""

# pyright: basic
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
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time

# Now import the modules to test
from config import Config, IrrigationPointConfig, NetworkConfig  # type: ignore

import unittest


class TestConfig(unittest.TestCase):
    """Test config.py using unittest framework."""

    def test_clean_string(self) -> None:
        """Test _clean_string function."""
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
            self.assertEqual(result, expected, f"_clean_string('{input_str}')")

    def test_get_if_valid(self) -> None:
        """Test _get_if_valid function."""
        from config import _get_if_valid  # type: ignore

        # Test valid case
        conf = {"name": "Test", "count": 42, "enabled": True}

        # Valid string
        result = _get_if_valid("name", conf, str)
        self.assertEqual(result, "Test")

        # Valid int
        result = _get_if_valid("count", conf, int)
        self.assertEqual(result, 42)

        # Valid bool
        result = _get_if_valid("enabled", conf, bool)
        self.assertTrue(result)

        # Test missing key
        with self.assertRaises(KeyError):
            _get_if_valid("missing", conf, str)

        # Test wrong type
        with self.assertRaises(TypeError):
            _get_if_valid("name", conf, int)

        # Test empty string
        with self.assertRaises(ValueError):
            _get_if_valid("empty", {"empty": ""}, str)

    def test_network_config(self) -> None:
        """Test NetworkConfig class."""
        # Valid config
        conf = {
            "wifi_ssid": "MyNetwork",
            "wifi_password": "secret123",
            "mqtt_broker_ip": "192.168.1.100",
        }

        network = NetworkConfig(conf)

        self.assertEqual(network.wifi_ssid, "MyNetwork")
        self.assertEqual(network.wifi_password, "secret123")
        self.assertEqual(network.mqtt_broker_ip, "192.168.1.100")

        # Test missing field
        with self.assertRaises(KeyError):
            NetworkConfig({"wifi_ssid": "Test", "wifi_password": "secret"})

    def test_irrigation_point_config(self) -> None:
        """Test IrrigationPointConfig class."""
        # Valid config
        conf = {
            "name": "Location A",
            "valve_pin": 2,
            "ads_address": "0x48",
            "ads_channel": 0,
        }

        point = IrrigationPointConfig(conf)

        self.assertEqual(point.name, "Location A")
        self.assertEqual(point.valve_pin, 2)
        self.assertEqual(point.ads_address, 0x48)
        self.assertEqual(point.ads_channel, 0)
        self.assertEqual(point.id, "locationa")

        # Check default values
        self.assertEqual(point.rolling_window, 5)
        self.assertAlmostEqual(point.ema_alpha, 0.2)

        # Test invalid ADS address
        with self.assertRaises(ValueError):
            IrrigationPointConfig(
                {
                    "name": "Test",
                    "valve_pin": 2,
                    "ads_address": "0x99",  # Invalid address
                    "ads_channel": 0,
                }
            )

        # Test invalid ADS channel
        with self.assertRaises(ValueError):
            IrrigationPointConfig(
                {
                    "name": "Test",
                    "valve_pin": 2,
                    "ads_address": "0x48",
                    "ads_channel": 5,  # Invalid channel
                }
            )

    def test_config_class(self) -> None:
        """Test Config class."""
        # Use fixture file
        test_file = "tests/fixtures/test_config.json"

        # Create config from fixture file
        config = Config(test_file)

        # Check station info
        self.assertEqual(config.station_name, "Backyard irrigation station")

        # Check device ID (based on mock unique_id)
        expected_id = "".join(f"{b:02x}" for b in mock_machine.unique_id())[-8:]
        self.assertEqual(config.station_id, expected_id)

        # Check MQTT ID
        expected_mqtt_id = f"backyardirrigationstation-{expected_id}"
        self.assertEqual(config.station_mqtt_id, expected_mqtt_id)

        # Check network config
        self.assertEqual(config.network.wifi_ssid, "MyNetwork")

        # Check global parameters
        self.assertEqual(config.rolling_window, 3)
        self.assertAlmostEqual(config.ema_alpha, 0.2)
        self.assertEqual(config.publish_interval, 5 * 60)  # 5 minutes in seconds
        self.assertEqual(config.max_valve_open_time, 45 * 60)  # 45 minutes in seconds

        # Check irrigation points
        self.assertEqual(len(config.irrigation_points), 2)

        # Check first point
        point_a = config.irrigation_points.get("locationa")
        self.assertIsNotNone(point_a)
        if point_a:
            self.assertEqual(point_a.name, "Location A")
            # Check that global parameters were copied to points
            self.assertEqual(point_a.rolling_window, 3)
            self.assertAlmostEqual(point_a.ema_alpha, 0.2)

        # Check __str__ method
        str_repr = str(config)
        self.assertTrue(str_repr.startswith("Irrigation station config:"))


if __name__ == "__main__":
    # Run the tests
    unittest.main()
