"""Test mqtt_robust_client.py using unittest framework."""

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
    Timer = type("MockTimer", (), {"init": lambda self, **kwargs: None, "ONE_SHOT": 0})
    reset = lambda: None


# Mock MQTTClient base class
class MockMQTTClientBase:
    def __init__(
        self,
        client_id,
        server,
        port=0,
        user=None,
        password=None,
        keepalive=0,
        ssl=None,
        ssl_params={},
    ):
        self.client_id = client_id
        self.server = server
        self.port = port
        self.user = user
        self.password = password
        self.keepalive = keepalive
        self.ssl = ssl
        self.ssl_params = ssl_params
        self.connected = False
        self.published_messages = []
        self.subscribed_topics = []
        self.disconnect_called = False
        self.check_msg_called = False
        self.sock = type(
            "MockSocket", (), {"setblocking": lambda self, blocking: None}
        )()
        self.wait_msg_called = False

    def connect(self, *args, **kwargs):
        self.connected = True
        self.connect_args = args
        self.connect_kwargs = kwargs
        return True  # Simulate successful connection

    def set_last_will(self, topic, msg, retain=False, qos=0):
        self.last_will = (topic, msg, retain, qos)

    def disconnect(self):
        self.connected = False
        self.disconnect_called = True

    def publish(self, topic, msg, retain=False, qos=0):
        self.published_messages.append((topic, msg, retain, qos))

    def subscribe(self, topic):
        self.subscribed_topics.append(topic)

    def check_msg(self):
        self.check_msg_called = True
        return None  # No messages

    def wait_msg(self):
        self.wait_msg_called = True
        return None  # No messages


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
mock_umqtt_simple = type("MockUMQTT", (), {"MQTTClient": MockMQTTClientBase})()


# Create umqtt module
class MockUMQTTModule:
    simple = mock_umqtt_simple


sys.modules["umqtt"] = MockUMQTTModule()
sys.modules["umqtt.simple"] = mock_umqtt_simple

# Now import the modules to test
from mqtt_robust_client import MqttRobustClient  # type: ignore

import unittest


class TestMqttRobustClient(unittest.TestCase):
    """Test mqtt_robust_client.py using unittest framework."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_logger = MockLogger()

    def test_mqtt_robust_client_initialization(self) -> None:
        """Test MqttRobustClient initialization."""
        client = MqttRobustClient(
            client_id="test_client",
            server="test.broker.com",
            port=1883,
            user="test_user",
            password="test_password",
            keepalive=60,
            logger=self.mock_logger,
        )

        # Check initialization
        self.assertIsNotNone(client)
        self.assertEqual(client.client_id, "test_client")
        self.assertEqual(client.server, "test.broker.com")
        self.assertEqual(client.port, 1883)
        self.assertEqual(client.user, "test_user")
        self.assertEqual(client.password, "test_password")
        self.assertEqual(client.keepalive, 60)
        self.assertEqual(client._logger, self.mock_logger)
        self.assertIsNone(client._on_reconnect_callback)

    def test_mqtt_robust_client_with_on_reconnect_callback(self) -> None:
        """Test MqttRobustClient with on_reconnect_callback."""
        callback_called = []

        def test_callback():
            callback_called.append(True)

        client = MqttRobustClient(
            client_id="test_client",
            server="test.broker.com",
            logger=self.mock_logger,
            on_reconnect_callback=test_callback,
        )

        # Check callback was set
        self.assertEqual(client._on_reconnect_callback, test_callback)

    def test_mqtt_robust_client_connect(self) -> None:
        """Test MqttRobustClient connect method."""
        client = MqttRobustClient(
            client_id="test_client", server="test.broker.com", logger=self.mock_logger
        )

        # Initially not connected
        self.assertFalse(client.connected)

        # Call connect
        client.connect()

        # Should be connected now
        self.assertTrue(client.connected)

        # MqttRobustClient.connect() doesn't log on successful connection
        # It only logs on errors (reconnection attempts)
        # So no log check needed here

    def test_mqtt_robust_client_publish(self) -> None:
        """Test MqttRobustClient publish method."""
        client = MqttRobustClient(
            client_id="test_client", server="test.broker.com", logger=self.mock_logger
        )

        # Connect first
        client.connect()

        # Clear logs
        self.mock_logger.messages.clear()

        # Publish a message
        client.publish("test/topic", "test message", retain=True, qos=1)

        # Check that message was published
        self.assertEqual(len(client.published_messages), 1)
        topic, message, retain, qos = client.published_messages[0]

        self.assertEqual(topic, "test/topic")
        self.assertEqual(message, "test message")
        self.assertTrue(retain)
        self.assertEqual(qos, 1)

        # MqttRobustClient.publish() doesn't log on successful publish
        # It only logs on errors
        # So no log check needed here

    def test_mqtt_robust_client_subscribe(self) -> None:
        """Test MqttRobustClient subscribe method."""
        client = MqttRobustClient(
            client_id="test_client", server="test.broker.com", logger=self.mock_logger
        )

        # Connect first
        client.connect()

        # Clear logs
        self.mock_logger.messages.clear()

        # Subscribe to a topic
        client.subscribe("test/topic")

        # Check that topic was subscribed
        self.assertEqual(len(client.subscribed_topics), 1)
        self.assertEqual(client.subscribed_topics[0], "test/topic")

        # MqttRobustClient doesn't override subscribe, so no logging
        # Base class subscribe doesn't log
        # So no log check needed here

    def test_mqtt_robust_client_check_msg(self) -> None:
        """Test MqttRobustClient check_msg method."""
        client = MqttRobustClient(
            client_id="test_client", server="test.broker.com", logger=self.mock_logger
        )

        # Connect first
        client.connect()

        # Call check_msg
        result = client.check_msg()

        # Should return None (no messages)
        self.assertIsNone(result)

        # MqttRobustClient.check_msg() calls super().wait_msg()
        # So wait_msg_called should be True
        self.assertTrue(client.wait_msg_called)

    def test_mqtt_robust_client_wait_msg(self) -> None:
        """Test MqttRobustClient wait_msg method."""
        client = MqttRobustClient(
            client_id="test_client", server="test.broker.com", logger=self.mock_logger
        )

        # Connect first
        client.connect()

        # Call wait_msg (should just call check_msg in this implementation)
        result = client.wait_msg()

        # Should return None (no messages)
        self.assertIsNone(result)

        # wait_msg() should set wait_msg_called
        self.assertTrue(client.wait_msg_called)

    def test_mqtt_robust_client_disconnect(self) -> None:
        """Test MqttRobustClient disconnect method."""
        client = MqttRobustClient(
            client_id="test_client", server="test.broker.com", logger=self.mock_logger
        )

        # Connect first
        client.connect()
        self.assertTrue(client.connected)

        # Clear logs
        self.mock_logger.messages.clear()

        # Disconnect
        client.disconnect()

        # Should be disconnected
        self.assertFalse(client.connected)
        self.assertTrue(client.disconnect_called)

        # MqttRobustClient doesn't override disconnect, so no logging
        # Base class disconnect doesn't log
        # So no log check needed here


if __name__ == "__main__":
    unittest.main()
