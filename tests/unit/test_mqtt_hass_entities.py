"""Test mqtt_hass_entities.py using unittest framework."""

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
    mock_ads1x15,
)


# Create mock modules before importing ANY project code
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id
    RTC = type("MockRTC", (), {"datetime": lambda self: (2024, 1, 1, 0, 0, 0, 0, 0)})
    Timer = type("MockTimer", (), {"init": lambda self, **kwargs: None, "ONE_SHOT": 0})
    I2C = type("MockI2C", (), {"init": lambda self, **kwargs: None})
    reset = lambda: None


# Mock MQTTClient for umqtt.simple
class MockMQTTClient:
    def __init__(self, *args, **kwargs):
        self.published_messages = []
        self.connected = True

    def publish(self, topic, message, retain=False, qos=0):
        self.published_messages.append((topic, message, retain, qos))

    def connect(self, *args, **kwargs):
        self.connected = True

    def disconnect(self):
        self.connected = False


# Mock Logger
class MockLogger:
    def __init__(self):
        self.messages = []

    def log(self, message):
        self.messages.append(message)

    def error(self, message):
        self.messages.append(f"ERROR: {message}")


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time
sys.modules["ads1x15"] = mock_ads1x15
# Create umqtt.simple module with MQTTClient
mock_umqtt_simple = type("MockUMQTT", (), {"MQTTClient": MockMQTTClient})()


# Create umqtt module
class MockUMQTTModule:
    simple = mock_umqtt_simple


sys.modules["umqtt"] = MockUMQTTModule()
sys.modules["umqtt.simple"] = mock_umqtt_simple

# Now import the modules to test
from mqtt_hass_entities import MqttHassSensor, MqttHassValve, MessagerParams  # type: ignore

import unittest


class TestMqttHassEntities(unittest.TestCase):
    """Test mqtt_hass_entities.py using unittest framework."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_client = MockMQTTClient()
        self.mock_logger = MockLogger()

        # Create mock irrigation point config
        self.point_config = type(
            "MockPointConfig",
            (),
            {
                "name": "Test Location",
                "valve_pin": 2,
                "mosfet_pin": 21,
                "ads_address": "0x48",
                "ads_channel": 0,
            },
        )()

        # Create device info
        self.device_info = {
            "identifiers": ["test_station_123"],
            "name": "Test Station",
            "manufacturer": "DIY",
            "model": "Irrigation Controller",
        }

        # Create MessagerParams
        self.params = MessagerParams(
            mqtt_client=self.mock_client,
            station_id="test_station",
            point_id="point_1",
            point_config=self.point_config,
            device_info=self.device_info,
            availability_topic="irrigation/test_station/availability",
            logger=self.mock_logger,
        )

    def test_mqtt_hass_sensor_creation(self) -> None:
        """Test MqttHassSensor creation and discovery message."""
        sensor = MqttHassSensor(self.params)

        # Check that sensor was created
        self.assertIsNotNone(sensor)
        self.assertEqual(sensor._station_id, "test_station")
        self.assertEqual(sensor._point_id, "point_1")

        # Check that discovery message was published
        self.assertEqual(len(self.mock_client.published_messages), 1)

        topic, message, retain, qos = self.mock_client.published_messages[0]

        # Check topic format
        self.assertTrue(topic.startswith("homeassistant/sensor/test_station-point_1"))
        self.assertTrue(topic.endswith("/config"))

        # Parse and check message content
        config = json.loads(message)

        self.assertEqual(config["name"], "Test Location Moisture")
        self.assertEqual(config["device_class"], "moisture")
        self.assertEqual(config["unit_of_measurement"], "%")
        self.assertEqual(
            config["state_topic"], "irrigation/test_station/point_1/sensor"
        )
        self.assertEqual(
            config["availability_topic"], "irrigation/test_station/availability"
        )
        self.assertEqual(config["unique_id"], "point_1_sensor")

        # Check device info
        self.assertEqual(config["device"]["identifiers"], ["test_station_123"])
        self.assertEqual(config["device"]["name"], "Test Station")

    def test_mqtt_hass_sensor_publish_moisture_level(self) -> None:
        """Test MqttHassSensor publish_moisture_level method."""
        sensor = MqttHassSensor(self.params)
        self.mock_client.published_messages.clear()

        sensor.publish_moisture_level(0.65)

        self.assertEqual(len(self.mock_client.published_messages), 1)
        topic, message, retain, qos = self.mock_client.published_messages[0]
        self.assertEqual(topic, "irrigation/test_station/point_1/sensor")
        self.assertIn('"moisture": 65.0', message)
        self.assertTrue(retain)

    def test_mqtt_hass_valve_creation(self) -> None:
        """Test MqttHassValve creation and discovery message."""
        valve = MqttHassValve(self.params)

        # Check that valve was created
        self.assertIsNotNone(valve)
        self.assertEqual(valve._station_id, "test_station")
        self.assertEqual(valve._point_id, "point_1")

        # Check that discovery message was published
        self.assertEqual(len(self.mock_client.published_messages), 1)

        topic, message, retain, qos = self.mock_client.published_messages[0]

        # Check topic format
        self.assertTrue(topic.startswith("homeassistant/valve/test_station-point_1"))
        self.assertTrue(topic.endswith("/config"))

        # Parse and check message content
        config = json.loads(message)

        self.assertEqual(config["name"], "Test Location Valve")
        self.assertEqual(
            config["command_topic"], "irrigation/test_station/point_1/valve/set"
        )
        self.assertEqual(
            config["state_topic"], "irrigation/test_station/point_1/valve/state"
        )
        self.assertEqual(
            config["availability_topic"], "irrigation/test_station/availability"
        )
        self.assertEqual(config["unique_id"], "point_1_valve")

        # Check device info
        self.assertEqual(config["device"]["identifiers"], ["test_station_123"])
        self.assertEqual(config["device"]["name"], "Test Station")

    def test_mqtt_hass_valve_publish_valve_state(self) -> None:
        """Test MqttHassValve publish_valve_state method."""
        valve = MqttHassValve(self.params)
        self.mock_client.published_messages.clear()

        valve.publish_valve_state("open")

        self.assertEqual(len(self.mock_client.published_messages), 1)
        topic, message, retain, qos = self.mock_client.published_messages[0]
        self.assertEqual(topic, "irrigation/test_station/point_1/valve/state")
        self.assertEqual(message, "open")
        self.assertTrue(retain)

    def test_messager_params_creation(self) -> None:
        """Test MessagerParams namedtuple creation."""
        params = MessagerParams(
            mqtt_client=self.mock_client,
            station_id="test_station",
            point_id="point_1",
            point_config=self.point_config,
            device_info=self.device_info,
            availability_topic="irrigation/test_station/availability",
            logger=self.mock_logger,
        )

        # Check all fields
        self.assertEqual(params.mqtt_client, self.mock_client)
        self.assertEqual(params.station_id, "test_station")
        self.assertEqual(params.point_id, "point_1")
        self.assertEqual(params.point_config, self.point_config)
        self.assertEqual(params.device_info, self.device_info)
        self.assertEqual(
            params.availability_topic, "irrigation/test_station/availability"
        )
        self.assertEqual(params.logger, self.mock_logger)


if __name__ == "__main__":
    unittest.main()
