"""Test wifi_manager.py using unittest framework with new API."""

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


# Mock network module
class MockWLAN:
    STA_IF = 0
    STATUS_CONNECTING = 1
    STATUS_CONNECTED = 3

    def __init__(self, interface):
        self.interface = interface
        self.active_calls = []
        self.connect_calls = []
        self.status_value = 0
        self.connected = False
        self.ifconfig_result = (
            "192.168.1.100",
            "255.255.255.0",
            "192.168.1.1",
            "8.8.8.8",
        )

    def active(self, value):
        self.active_calls.append(value)

    def connect(self, ssid, password):
        self.connect_calls.append((ssid, password))
        self.status_value = self.STATUS_CONNECTING
        # Simulate connection succeeding after connect is called
        # This allows the _connect() method to break out of its loop
        self.connected = True
        self.status_value = self.STATUS_CONNECTED

    def status(self):
        return self.status_value

    def isconnected(self):
        return self.connected

    def ifconfig(self):
        return self.ifconfig_result


# Mock network module
class MockNetworkModule:
    WLAN = MockWLAN
    STA_IF = 0


sys.modules["network"] = MockNetworkModule()


# Mock rp2 module
class MockRP2Module:
    def country(self, country):
        pass


sys.modules["rp2"] = MockRP2Module()

# Now import the modules to test
from wifi_manager import WiFiManager  # type: ignore

import unittest


class MockNetworkConfig:
    """Mock network configuration."""

    def __init__(self) -> None:
        self.wifi_ssid = "TestNetwork"
        self.wifi_password = "password"
        self.mqtt_broker_ip = "192.168.1.100"


class MockLogger:
    """Mock logger for testing."""

    def __init__(self) -> None:
        self.messages = []

    def log(self, message: str) -> None:
        self.messages.append(message)


class TestWiFiManagerNew(unittest.TestCase):
    """Test WiFiManager class with new API."""

    def test_wifi_manager_initialization(self) -> None:
        """Test WiFiManager initialization."""
        config = MockNetworkConfig()
        logger = MockLogger()

        manager = WiFiManager(config, logger)  # type: ignore

        # Check that WLAN was created
        self.assertIsNotNone(manager._wlan)
        self.assertEqual(manager._config, config)
        self.assertEqual(manager._logger, logger)

    def test_wifi_manager_setup(self) -> None:
        """Test WiFiManager setup method."""
        config = MockNetworkConfig()
        logger = MockLogger()

        manager = WiFiManager(config, logger)  # type: ignore
        manager.setup()

        # Check that WLAN was activated
        self.assertEqual(len(manager._wlan.active_calls), 1)
        self.assertTrue(manager._wlan.active_calls[0])

        # Check that connect was called
        self.assertEqual(len(manager._wlan.connect_calls), 1)
        self.assertEqual(manager._wlan.connect_calls[0][0], "TestNetwork")
        self.assertEqual(manager._wlan.connect_calls[0][1], "password")

    def test_wifi_manager_check_connection_connected(self) -> None:
        """Test check_connection method when already connected."""
        config = MockNetworkConfig()
        logger = MockLogger()

        manager = WiFiManager(config, logger)  # type: ignore

        # Set WLAN to connected state
        manager._wlan.connected = True
        manager._wlan.status_value = manager._wlan.STATUS_CONNECTED

        # Clear connect calls
        manager._wlan.connect_calls.clear()

        # Check connection
        manager.check_connection()

        # Should not try to reconnect
        self.assertEqual(len(manager._wlan.connect_calls), 0)

    def test_wifi_manager_check_connection_disconnected(self) -> None:
        """Test check_connection method when disconnected."""
        config = MockNetworkConfig()
        logger = MockLogger()

        manager = WiFiManager(config, logger)  # type: ignore

        # Set WLAN to disconnected state
        manager._wlan.connected = False
        manager._wlan.status_value = 0

        # Clear connect calls
        manager._wlan.connect_calls.clear()

        # Check connection
        manager.check_connection()

        # Should try to reconnect
        self.assertEqual(len(manager._wlan.connect_calls), 1)
        self.assertEqual(manager._wlan.connect_calls[0][0], "TestNetwork")
        self.assertEqual(manager._wlan.connect_calls[0][1], "password")

    def test_wifi_manager_connect_method(self) -> None:
        """Test WiFiManager _connect method."""
        config = MockNetworkConfig()
        logger = MockLogger()

        manager = WiFiManager(config, logger)  # type: ignore

        # Clear any existing calls
        manager._wlan.connect_calls.clear()
        logger.messages.clear()

        # Call _connect
        manager._connect()

        # Should call connect
        self.assertEqual(len(manager._wlan.connect_calls), 1)

        # Should log connection attempt
        self.assertTrue(
            any("Attempting to connect to WiFi" in msg for msg in logger.messages)
        )


if __name__ == "__main__":
    # Run the tests
    unittest.main()
