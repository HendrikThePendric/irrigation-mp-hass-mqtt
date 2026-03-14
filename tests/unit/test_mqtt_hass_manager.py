"""Test mqtt_hass_manager.py using unittest framework with new API."""

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
    mock_ssl_context,
    mock_umqtt_simple,
)


# Create mock modules before importing ANY project code
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id
    RTC = type("MockRTC", (), {"datetime": lambda self: (2024, 1, 1, 0, 0, 0, 0, 0)})
    reset = lambda: None


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time
sys.modules["ads1x15"] = mock_ads1115


# Mock SSL module
class MockSSLModule:
    SSLContext = mock_ssl_context
    PROTOCOL_TLS_CLIENT = 1


sys.modules["ssl"] = MockSSLModule()


# Mock umqtt module
class MockUMQTTModule:
    simple = mock_umqtt_simple


sys.modules["umqtt"] = MockUMQTTModule()
sys.modules["umqtt.simple"] = mock_umqtt_simple

# Now import the modules to test
from mqtt_hass_manager import MqttHassManager, create_ssl_context  # type: ignore
from irrigation_states import ValveState, SensorState  # type: ignore

import unittest


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self) -> None:
        self.station_id = "teststation"
        self.station_mqtt_id = "teststation-mqtt"
        self.station_name = "Test Station"
        self.irrigation_points = {
            "pointa": MockPointConfig("Point A", 2, 21, 0x48, 0),
            "pointb": MockPointConfig("Point B", 3, 22, 0x49, 1),
        }
        self.network = MockNetworkConfig()


class MockNetworkConfig:
    """Mock network configuration."""

    def __init__(self) -> None:
        self.wifi_ssid = "TestNetwork"
        self.wifi_password = "password"
        self.mqtt_broker_ip = "192.168.1.100"


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


class MockLogger:
    """Mock logger for testing."""

    def __init__(self) -> None:
        self.messages = []

    def log(self, message: str) -> None:
        self.messages.append(message)


class TestMqttHassManagerNew(unittest.TestCase):
    """Test MqttHassManager class with new API."""

    def test_create_ssl_context(self) -> None:
        """Test create_ssl_context function."""
        # This is a simple test that just checks the function exists
        ssl_context = create_ssl_context()
        self.assertIsNotNone(ssl_context)

    def test_mqtt_hass_manager_initialization(self) -> None:
        """Test MqttHassManager initialization."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore

        # Check that client was created
        self.assertIsNotNone(manager._client)
        self.assertEqual(manager._config, config)
        self.assertEqual(manager._logger, logger)

    def test_mqtt_hass_manager_setup(self) -> None:
        """Test MqttHassManager setup method."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        # Check that client is connected
        self.assertTrue(manager._client.connected)

    def test_mqtt_hass_manager_get_station_instructions(self) -> None:
        """Test get_station_instructions method."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        # Simulate receiving MQTT messages
        manager._received_messages = [
            ("irrigation/teststation/pointa/valve/set", "open"),
            ("irrigation/teststation/pointb/valve/set", "closed"),
            ("homeassistant/status", "online"),  # Should be filtered out
            ("irrigation/teststation/pointa/sensor", "data"),  # Should be filtered out
        ]

        # Get station instructions
        commands = manager.get_station_instructions()

        # Should only return valve commands
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0].point_id, "pointa")
        self.assertEqual(commands[0].state, "open")
        self.assertEqual(commands[1].point_id, "pointb")
        self.assertEqual(commands[1].state, "closed")

        # Only valve messages should be cleared, other messages remain
        self.assertEqual(
            len(manager._received_messages), 2
        )  # HA status and sensor remain

    def test_mqtt_hass_manager_publish_valve_states(self) -> None:
        """Test publish_valve_states method."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        # Clear published messages
        manager._client.published_messages.clear()

        # Publish valve states
        valve_states = [
            ValveState("pointa", "open"),
            ValveState("pointb", "closed"),
        ]
        manager.publish_valve_states(valve_states)

        # Check that messages were published
        self.assertEqual(len(manager._client.published_messages), 2)

        # Check topics and messages
        topics = [msg[0] for msg in manager._client.published_messages]
        messages = [msg[1] for msg in manager._client.published_messages]

        self.assertIn("irrigation/teststation/pointa/valve/state", topics)
        self.assertIn("irrigation/teststation/pointb/valve/state", topics)
        self.assertIn("open", messages)
        self.assertIn("closed", messages)

    def test_mqtt_hass_manager_publish_sensor_states(self) -> None:
        """Test publish_sensor_states method."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        # Clear published messages
        manager._client.published_messages.clear()

        # Publish sensor states
        sensor_states = [
            SensorState("pointa", 0.65),
            SensorState("pointb", 0.35),
        ]
        manager.publish_sensor_states(sensor_states)

        # Check that messages were published
        self.assertEqual(len(manager._client.published_messages), 2)

        # Check topics and messages
        topics = [msg[0] for msg in manager._client.published_messages]
        messages = [msg[1] for msg in manager._client.published_messages]

        self.assertIn("irrigation/teststation/pointa/sensor", topics)
        self.assertIn("irrigation/teststation/pointb/sensor", topics)

        # Check that moisture values were converted to percentages
        self.assertTrue(any('"moisture": 65.0' in msg for msg in messages))
        self.assertTrue(any('"moisture": 35.0' in msg for msg in messages))

    def test_mqtt_hass_manager_test_broker_connectivity(self) -> None:
        """Test test_broker_connectivity method."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        # Clear published messages
        manager._client.published_messages.clear()

        # Test broker connectivity
        manager.test_broker_connectivity()

        # Should publish a test message
        self.assertTrue(len(manager._client.published_messages) > 0)

        # Check that it published to the broker connectivity topic
        self.assertTrue(
            any(
                topic.startswith("irrigation/teststation/broker_connectivity")
                for topic, message, retain, qos in manager._client.published_messages
            )
        )

    def test_mqtt_hass_manager_check_msg(self) -> None:
        """Test MqttHassManager check_msg method."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        # Call check_msg (should not raise exceptions)
        manager.check_msg()


if __name__ == "__main__":
    # Run the tests
    unittest.main()
