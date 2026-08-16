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
    mock_ads1x15,
    mock_ssl_context,
    mock_umqtt_simple,
)


# Create mock modules before importing ANY project code
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id
    RTC = type("MockRTC", (), {"datetime": lambda self: (2024, 1, 1, 0, 0, 0, 0, 0)})
    I2C = type("MockI2C", (), {"__init__": lambda self, *args, **kwargs: None})
    reset = mock_machine.reset


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time
sys.modules["ads1x15"] = mock_ads1x15


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
import builtins

file_writes = {}
file_opens = []


class MockFile:
    def __init__(self, filename, mode):
        self.filename = filename
        self.mode = mode
        self.content = file_writes.get(filename, "") if "r" in mode else ""

    def write(self, text):
        self.content += text
        file_writes[self.filename] = self.content

    def read(self):
        return self.content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        file_writes[self.filename] = self.content


def mock_open(filename, mode="r"):
    file_opens.append((filename, mode))
    if filename not in file_writes:
        file_writes[filename] = ""
    return MockFile(filename, mode)


builtins.open = mock_open


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self) -> None:
        self.station_id = "teststation"
        self.station_mqtt_id = "teststation-mqtt"
        self.station_name = "Test Station"
        self.irrigation_points = {
            "pointa": MockPointConfig("Point A", 2, 0x48, 0),
            "pointb": MockPointConfig("Point B", 3, 0x49, 1),
        }
        self.network = MockNetworkConfig()

    def __str__(self) -> str:
        return "Irrigation station config:\nstation_name: Test Station"


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
        ads_address: int,
        ads_channel: int,
    ) -> None:
        self.name = name
        self.valve_pin = valve_pin
        self.ads_address = ads_address
        self.ads_channel = ads_channel
        self.id = name.lower().replace(" ", "")
        self.dry_voltage: float = 2.4
        self.wet_voltage: float = 0.95


class MockLogger:
    """Mock logger for testing."""

    def __init__(self) -> None:
        self.messages = []

    def log(self, message: str) -> None:
        self.messages.append(message)


class TestMqttHassManagerNew(unittest.TestCase):
    """Test MqttHassManager class with new API."""

    def setUp(self) -> None:
        """Reset mock state before each test."""
        from simple_mocks import MockMQTTClient

        MockMQTTClient.reset_instances()
        file_writes.clear()
        file_opens.clear()
        mock_machine.reset_calls.clear()
        mock_os.rename_calls.clear()

    def test_create_ssl_context(self) -> None:
        """Test create_ssl_context function."""
        ssl_context = create_ssl_context()
        self.assertIsNotNone(ssl_context)

    def test_mqtt_hass_manager_initialization(self) -> None:
        """Test MqttHassManager initialization."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore

        self.assertIsNotNone(manager._client)
        self.assertEqual(manager._config, config)
        self.assertEqual(manager._logger, logger)

    def test_mqtt_hass_manager_setup(self) -> None:
        """Test MqttHassManager setup method."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        self.assertTrue(manager._client.connected)

    def test_setup_subscribes_to_config_topic(self) -> None:
        """Test setup subscribes to the config/set topic."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        self.assertIn("irrigation/teststation/config/set", manager._client.subscribe_calls)

    def test_boot_echo_publishes_config_current(self) -> None:
        """Test setup publishes the config summary to config/current (retained)."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore

        manager.setup()

        echoed = None
        retain = False
        for topic, message, _retain, _qos in manager._client.published_messages:
            if topic == "irrigation/teststation/config/current":
                echoed = message
                retain = _retain

        self.assertIsNotNone(echoed)
        self.assertTrue(retain)
        self.assertEqual(echoed, str(config))

    def test_republishes_config_current_on_ha_restart(self) -> None:
        """Test config/current is republished when Home Assistant comes online."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        manager._client.published_messages.clear()

        manager._handle_message(b"homeassistant/status", b"online")

        self.assertTrue(
            any(
                topic == "irrigation/teststation/config/current"
                for topic, message, retain, qos in manager._client.published_messages
            )
        )

    def test_mqtt_hass_manager_get_station_instructions(self) -> None:
        """Test get_station_instructions method."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        manager._pending_valve_commands = [
            ValveState("pointa", "open"),
            ValveState("pointb", "closed"),
        ]

        commands = manager.get_station_instructions()

        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0].point_id, "pointa")
        self.assertEqual(commands[0].state, "open")
        self.assertEqual(commands[1].point_id, "pointb")
        self.assertEqual(commands[1].state, "closed")
        self.assertEqual(len(manager._pending_valve_commands), 0)

    def test_mqtt_hass_manager_publish_valve_states(self) -> None:
        """Test publish_valve_states method."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        manager._client.published_messages.clear()

        valve_states = [
            ValveState("pointa", "open"),
            ValveState("pointb", "closed"),
        ]
        manager.publish_valve_states(valve_states)

        self.assertEqual(len(manager._client.published_messages), 2)

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

        manager._client.published_messages.clear()

        sensor_states = [
            SensorState("pointa", 0.65),
            SensorState("pointb", 0.35),
        ]
        manager.publish_sensor_states(sensor_states)

        self.assertEqual(len(manager._client.published_messages), 2)

        topics = [msg[0] for msg in manager._client.published_messages]
        messages = [msg[1] for msg in manager._client.published_messages]

        self.assertIn("irrigation/teststation/pointa/sensor", topics)
        self.assertIn("irrigation/teststation/pointb/sensor", topics)

        self.assertTrue(any('"moisture": 65.0' in msg for msg in messages))
        self.assertTrue(any('"moisture": 35.0' in msg for msg in messages))

    def test_mqtt_hass_manager_test_broker_connectivity(self) -> None:
        """Test test_broker_connectivity method."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        manager._client.published_messages.clear()

        manager.test_broker_connectivity()

        self.assertTrue(len(manager._client.published_messages) > 0)

        self.assertTrue(
            any(
                topic.startswith("irrigation/teststation/broker_connectivity")
                for topic, message, retain, qos in manager._client.published_messages
            )
        )

    def test_mqtt_hass_manager_process_messages(self) -> None:
        """Test MqttHassManager process_messages method."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        manager.process_messages()

    def test_handle_calibration_set(self) -> None:
        """Test handling calibration dry_v/set message stores command."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        topic = b"irrigation/teststation/pointa/calibration/dry_v/set"
        msg = b"2.704"

        manager._handle_message(topic, msg)

        commands = manager.get_calibration_commands()
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].point_id, "pointa")
        self.assertEqual(commands[0].field, "dry_v")
        self.assertAlmostEqual(commands[0].value, 2.704, places=3)

    def test_handle_voltage_measure(self) -> None:
        """Test handling voltage/measure message stores command."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        topic = b"irrigation/teststation/pointa/voltage/measure"
        msg = b"measure"

        manager._handle_message(topic, msg)

        commands = manager.get_voltage_commands()
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].point_id, "pointa")

    def test_handle_config_set_writes_atomically_and_reboots(self) -> None:
        """Test config/set message writes config atomically and reboots."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore

        topic = b"irrigation/teststation/config/set"
        payload = b'{"station_name": "Renamed Station"}'

        manager._handle_message(topic, payload)

        self.assertEqual(
            file_writes["./config.json.tmp"], '{"station_name": "Renamed Station"}'
        )
        self.assertIn(("./config.json.tmp", "./config.json"), mock_os.rename_calls)
        self.assertEqual(len(mock_machine.reset_calls), 1)

    def test_handle_config_set_ignores_other_station_topics(self) -> None:
        """Test config/set for a different station is ignored."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore

        topic = b"irrigation/otherstation/config/set"
        payload = b'{"station_name": "Renamed Station"}'

        manager._handle_message(topic, payload)

        self.assertFalse("./config.json.tmp" in file_writes)
        self.assertEqual(len(mock_machine.reset_calls), 0)

    def test_handle_config_set_write_failure_does_not_reboot(self) -> None:
        """Test a config write failure logs and does not reboot."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore

        original_open = builtins.open

        def failing_open(filename, mode="r"):
            raise OSError("disk full")

        builtins.open = failing_open
        try:
            manager._handle_message(
                b"irrigation/teststation/config/set",
                b'{"station_name": "Renamed Station"}',
            )
        finally:
            builtins.open = original_open

        self.assertEqual(len(mock_machine.reset_calls), 0)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
