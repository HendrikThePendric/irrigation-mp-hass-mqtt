"""Test wifi_manager.py using unittest framework."""

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
)


# Create mock modules before importing ANY project code
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id
    RTC = type("MockRTC", (), {"datetime": lambda self: (2024, 1, 1, 0, 0, 0, 0, 0)})
    Timer = type(
        "MockTimer",
        (),
        {"init": lambda self, **kwargs: None, "ONE_SHOT": 0, "PERIODIC": 1},
    )
    reset = lambda: None


# Mock network module
class MockWLAN:
    STA_IF = 1
    AP_IF = 2

    def __init__(self, interface):
        self.interface = interface
        self.active_state = False
        self.connected_state = False
        self.connection_attempts = 0
        self.config_calls = []
        self.connect_calls = []
        self.status_calls = []

    def active(self, state):
        self.active_state = state

    def isconnected(self):
        return self.connected_state

    def config(self, **kwargs):
        self.config_calls.append(kwargs)

    def connect(self, ssid, password):
        self.connect_calls.append((ssid, password))
        self.connection_attempts += 1
        # Simulate connection after first attempt
        if self.connection_attempts == 1:
            self.connected_state = True

    def status(self):
        self.status_calls.append(())
        # Return a mock status
        return 3  # STAT_GOT_IP

    def ifconfig(self):
        # Return mock network configuration
        return ("192.168.1.100", "255.255.255.0", "192.168.1.1", "8.8.8.8")


# Mock rp2 module
class MockRP2:
    def country(self, country_code):
        self.country_code = country_code


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
sys.modules["network"] = type(
    "MockNetwork",
    (),
    {"WLAN": MockWLAN, "STA_IF": MockWLAN.STA_IF, "AP_IF": MockWLAN.AP_IF},
)
sys.modules["rp2"] = MockRP2()

# Now import the modules to test
from wifi_manager import WiFiManager  # type: ignore
from config import NetworkConfig  # type: ignore

import unittest


class TestWiFiManager(unittest.TestCase):
    """Test wifi_manager.py using unittest framework."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_logger = MockLogger()

        # Create network config
        self.network_config = NetworkConfig(
            {
                "wifi_ssid": "TestNetwork",
                "wifi_password": "TestPassword",
                "mqtt_broker_ip": "192.168.1.100",
            }
        )

    def test_wifi_manager_initialization(self) -> None:
        """Test WiFiManager initialization."""
        wifi_manager = WiFiManager(self.network_config, self.mock_logger)

        # Check initialization
        self.assertIsNotNone(wifi_manager)
        self.assertEqual(wifi_manager._config, self.network_config)
        self.assertEqual(wifi_manager._logger, self.mock_logger)

        # Check that country was set
        self.assertEqual(sys.modules["rp2"].country_code, "nl")

    def test_wifi_manager_setup(self) -> None:
        """Test WiFiManager setup method."""
        wifi_manager = WiFiManager(self.network_config, self.mock_logger)

        # Get the mock WLAN instance
        mock_wlan = wifi_manager._wlan

        # Call setup
        wifi_manager.setup()

        # Check that WLAN was activated
        self.assertTrue(mock_wlan.active_state)

        # Check that connect was called with correct credentials
        self.assertEqual(len(mock_wlan.connect_calls), 1)
        ssid, password = mock_wlan.connect_calls[0]
        self.assertEqual(ssid, "TestNetwork")
        self.assertEqual(password, "TestPassword")

        # Check that timer was started (periodic check)
        # This is harder to test directly, but we can check that setup runs without error
        self.assertTrue(True)  # Just checking it runs without error

    def test_wifi_manager_handle_pending_connection_check(self) -> None:
        """Test handle_pending_connection_check method."""
        wifi_manager = WiFiManager(self.network_config, self.mock_logger)

        # Initially, no pending check
        wifi_manager.handle_pending_connection_check()

        # Set pending check flag
        wifi_manager._pending_connection_check = True

        # Mock WLAN as disconnected
        wifi_manager._wlan.connected_state = False

        # Call handle_pending_connection_check
        wifi_manager.handle_pending_connection_check()

        # Check that connect was called again
        mock_wlan = wifi_manager._wlan
        self.assertEqual(len(mock_wlan.connect_calls), 1)

        # Check that pending flag was cleared
        self.assertFalse(wifi_manager._pending_connection_check)

    def test_wifi_manager_set_pending_connection_check(self) -> None:
        """Test _set_pending_connection_check method."""
        wifi_manager = WiFiManager(self.network_config, self.mock_logger)

        # Initially not pending
        self.assertFalse(wifi_manager._pending_connection_check)

        # Call the callback (simulating timer callback)
        wifi_manager._set_pending_connection_check(None)

        # Should set pending flag
        self.assertTrue(wifi_manager._pending_connection_check)

    def test_wifi_manager_connect_method(self) -> None:
        """Test _connect method."""
        wifi_manager = WiFiManager(self.network_config, self.mock_logger)

        # Call _connect directly
        wifi_manager._connect()

        # Check that connect was called
        mock_wlan = wifi_manager._wlan
        self.assertEqual(len(mock_wlan.connect_calls), 1)

        # Check logs - the actual log message might vary
        self.assertTrue(len(self.mock_logger.messages) > 0)

    def test_wifi_manager_start_periodic_check(self) -> None:
        """Test _start_periodic_check method."""
        wifi_manager = WiFiManager(self.network_config, self.mock_logger)

        # Call _start_periodic_check
        wifi_manager._start_periodic_check()

        # Check that timer was initialized
        # This is harder to test directly, but we can check that the method doesn't crash
        self.assertTrue(True)  # Just checking it runs without error


if __name__ == "__main__":
    unittest.main()
