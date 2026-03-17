"""E2E-style integration tests for irrigation system.

Tests key scenarios:
1. When a valve-open MQTT message is received → valve opens → status update sent
2. When a valve-open MQTT message is received while another valve is open →
   first valve closes → new valve opens → two MQTT updates sent
3. When publish interval elapses → MQTT sensor messages for all sensors are sent
4. When multiple rapid valve commands arrive → last command wins → appropriate valves closed
5. When WiFi drops and reconnects → system reconnects to MQTT → resumes operation
6. When sensor read fails → uses last valid reading → system continues
"""

# pyright: basic
import sys
import json

# Setup paths
sys.path.insert(0, "src")
sys.path.insert(0, "tests")

# Import simple mocks
from simple_mocks import (
    mock_machine,
    mock_os,
    mock_ntptime,
    mock_time,
    mock_ads1x15,
    mock_ssl_context,
    mock_umqtt_simple,
    mock_network,
    mock_rp2,
    mock_gc,
    MockMQTTClient,
)


# Create mock modules before importing ANY project code
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id
    RTC = type("MockRTC", (), {"datetime": lambda self: (2024, 1, 1, 0, 0, 0, 0, 0)})
    Timer = mock_machine.Timer
    I2C = type("MockI2C", (), {"__init__": lambda self, *args, **kwargs: None})
    reset = mock_machine.reset


# Mock SSL module
class MockSSLModule:
    SSLContext = mock_ssl_context
    PROTOCOL_TLS_CLIENT = 1


# Mock umqtt module
class MockUMQTTModule:
    simple = mock_umqtt_simple


# Mock network module
class MockNetworkModule:
    WLAN = mock_network.create_wlan
    STA_IF = mock_network.STA_IF
    AP_IF = mock_network.AP_IF


# Mock rp2 module
class MockRP2Module:
    country = mock_rp2.country


# Mock gc module
class MockGCModule:
    collect = mock_gc.collect


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time
sys.modules["ads1x15"] = mock_ads1x15
sys.modules["ssl"] = MockSSLModule()
sys.modules["umqtt"] = MockUMQTTModule()
sys.modules["umqtt.simple"] = mock_umqtt_simple
sys.modules["network"] = MockNetworkModule()
sys.modules["rp2"] = MockRP2Module()
sys.modules["gc"] = MockGCModule()

# Mock datetime module (used by time_keeper)
import datetime as real_datetime

sys.modules["datetime"] = real_datetime

# Now we can import the modules we need for testing
import unittest


class TestIrrigationSystemE2E(unittest.TestCase):
    """E2E integration tests for irrigation system."""

    def setUp(self) -> None:
        """Set up test environment."""
        # Reset mock states
        mock_time.reset_ticks()
        mock_time.reset_time()
        mock_machine.pins_created.clear()
        mock_machine.timers_created.clear()
        mock_network.reset()
        mock_gc.collect_calls.clear()

        # Reset MQTT mock
        MockMQTTClient.reset_instances()

        # Store original functions we might modify
        self.original_sleep = mock_time.sleep
        self.original_open = mock_os.open
        self.original_exists = mock_os.path.exists
        self.original_stat = mock_os.stat
        # Store original builtins.open and set default mock
        import builtins

        self.builtins = builtins
        self.original_builtins_open = builtins.open

        # Default mock that raises error if called without being mocked
        def default_open(*args, **kwargs):
            raise NotImplementedError("builtins.open not mocked for this test")

        builtins.open = default_open

        # Create a test configuration with three irrigation points
        self.test_config = {
            "station_name": "Test Station",
            "network": {
                "wifi_ssid": "TestNetwork",
                "wifi_password": "testpassword",
                "mqtt_broker_ip": "192.168.1.100",
            },
            "rolling_window": 3,
            "ema_alpha": 0.2,
            "publish_interval_minutes": 4,  # 4 minutes = 240 seconds
            "irrigation_points": [
                {
                    "name": "Location A",
                    "valve_pin": 2,
                    "mosfet_pin": 21,
                    "ads_address": "0x48",
                    "ads_channel": 0,
                },
                {
                    "name": "Location B",
                    "valve_pin": 3,
                    "mosfet_pin": 22,
                    "ads_address": "0x49",
                    "ads_channel": 1,
                },
                {
                    "name": "Location C",
                    "valve_pin": 4,
                    "mosfet_pin": 26,
                    "ads_address": "0x4A",
                    "ads_channel": 2,
                },
            ],
        }

        # Mock file operations (adapted from backup test)
        config_json = json.dumps(self.test_config)

        def mock_open(path: str, mode: str = "r"):
            if path == "./config.json" and "r" in mode:
                # Return a mock file object with our config
                class MockFile:
                    def __init__(self, content: str):
                        self.content = content
                        self.pos = 0

                    def read(self, size: int = -1) -> str:
                        if size == -1:
                            return self.content
                        # Return up to size characters
                        result = self.content[self.pos : self.pos + size]
                        self.pos += len(result)
                        return result

                    def seek(self, offset: int, whence: int = 0) -> None:
                        if whence == 0:
                            self.pos = offset
                        elif whence == 1:
                            self.pos += offset
                        elif whence == 2:
                            self.pos = len(self.content) + offset
                        self.pos = max(0, min(self.pos, len(self.content)))

                    def tell(self) -> int:
                        return self.pos

                    def close(self) -> None:
                        pass

                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc_val, exc_tb):
                        pass

                return MockFile(config_json)
            elif path == "./log.txt" and "a" in mode:
                # Return a mock file for logging
                class MockLogFile:
                    def write(self, data: str) -> None:
                        pass

                    def close(self) -> None:
                        pass

                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc_val, exc_tb):
                        pass

                return MockLogFile()
            elif path in [
                "./ca_crt.der",
                "./irrigationbackyard_crt.der",
                "./irrigationbackyard_key.der",
            ]:
                # Mock certificate files
                class MockCertFile:
                    def read(self) -> bytes:
                        return b"mock_cert_data"

                    def close(self) -> None:
                        pass

                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc_val, exc_tb):
                        pass

                return MockCertFile()
            else:
                # Fall back to original mock
                return self.original_open(path, mode)

        def mock_exists(path: str) -> bool:
            if path in ["./config.json", "./log.txt", "./log-old.txt"]:
                return True
            if path in [
                "./ca_crt.der",
                "./irrigationbackyard_crt.der",
                "./irrigationbackyard_key.der",
            ]:
                return True
            return self.original_exists(path)

        def mock_stat(path: str) -> tuple:
            if path == "./log.txt":
                # Return small file size to avoid rotation
                return (0, 0, 0, 0, 0, 0, 100)  # 100 bytes
            return self.original_stat(path)

        # Apply mocks
        mock_os.open = mock_open
        mock_os.path.exists = mock_exists
        mock_os.stat = mock_stat
        self.builtins.open = mock_open

        # Monkey-patch _load_json_file to avoid file reading issues
        import config as config_module

        self.original_load_json = config_module._load_json_file
        config_module._load_json_file = lambda file_path: self.test_config

        # Now import and create the irrigation system
        from irrigation_system import IrrigationSystem

        # Create the irrigation system (uses mocked dependencies via sys.modules)
        self.system = IrrigationSystem("./config.json", print_logs=True)

        # Get references to components for easier access in tests
        self.logger = self.system.logger
        self.config = self.system.config
        self.station = self.system.station
        self.mqtt_manager = self.system.mqtt_manager
        self.scheduler = self.system.scheduler
        self.time_keeper = self.system.time_keeper
        self.wifi_manager = self.system.wifi_manager
        self.watchdog = self.system.watchdog

        # Get the mock MQTT client instance for test inspection
        self.mock_mqtt_client = MockMQTTClient.instances[0]

        # Create mapping from point_id to pin_id for easier verification
        self.point_to_pin_map = {
            "locationa": 2,
            "locationb": 3,
            "locationc": 4,
        }

    def tearDown(self) -> None:
        """Restore original functions."""
        mock_time.sleep = self.original_sleep
        mock_os.open = self.original_open
        mock_os.path.exists = self.original_exists
        mock_os.stat = self.original_stat
        self.builtins.open = self.original_builtins_open
        # Restore _load_json_file
        import config as config_module

        config_module._load_json_file = self.original_load_json

    def _simulate_valve_command(self, point_id: str, state: str) -> None:
        """Simulate receiving a valve command via MQTT."""
        # Inject a message directly into the MQTT manager's pending commands
        from irrigation_states import ValveState

        self.mqtt_manager._pending_valve_commands.append(ValveState(point_id, state))

    def _get_valve_pin_state(self, pin_id: int) -> int:
        """Get the current value of a valve pin."""
        valve_pins = [p for p in mock_machine.pins_created if p.pin_id == pin_id]
        self.assertEqual(
            len(valve_pins), 1, f"Expected exactly one pin with id {pin_id}"
        )
        return valve_pins[0]._value

    def _get_published_valve_messages(self, point_id: str):
        """Get all published valve state messages for a point."""
        return [
            msg
            for msg in self.mock_mqtt_client.published_messages
            if f"{point_id}/valve/state" in msg[0]
        ]

    def _get_published_sensor_messages(self, point_id: str):
        """Get all published sensor messages for a point."""
        return [
            msg
            for msg in self.mock_mqtt_client.published_messages
            if f"{point_id}/sensor" in msg[0]
        ]

    def _verify_valve_state(self, point_id: str, expected_state: str) -> None:
        """Verify that a valve is in the expected state (open/closed)."""
        pin_id = self.point_to_pin_map.get(point_id)
        if pin_id is None:
            self.fail(f"Unknown point_id: {point_id}")

        actual_pin_value = self._get_valve_pin_state(pin_id)
        # open = pin value 1, closed = pin value 0
        expected_pin_value = 1 if expected_state == "open" else 0
        self.assertEqual(
            actual_pin_value,
            expected_pin_value,
            f"Valve {point_id} should be {expected_state} (pin {pin_id} value {expected_pin_value}), "
            f"but got pin value {actual_pin_value}",
        )

    def _simulate_wifi_drop(self) -> None:
        """Simulate WiFi disconnection."""
        if mock_network.wlan_instance:
            mock_network.wlan_instance._connected = False

    def _simulate_wifi_recovery(self) -> None:
        """Simulate WiFi reconnection."""
        if mock_network.wlan_instance:
            mock_network.wlan_instance._connected = True

    def test_valve_open_command_opens_valve_and_publishes_status(self) -> None:
        """Scenario 1: When a valve-open MQTT message is received,
        then the valve is opened and a status update is sent over MQTT."""

        # Initially all valves should be closed
        self._verify_valve_state("locationa", "closed")
        self._verify_valve_state("locationb", "closed")
        self._verify_valve_state("locationc", "closed")

        # Simulate receiving a valve-open command for Location A
        self._simulate_valve_command("locationa", "open")

        # Process the command by running system tick
        self.system.tick()

        # Verify valve A is now open
        self._verify_valve_state("locationa", "open")
        # Verify valve B and C remain closed
        self._verify_valve_state("locationb", "closed")
        self._verify_valve_state("locationc", "closed")

        # Verify MQTT status update was published
        valve_messages = self._get_published_valve_messages("locationa")
        self.assertTrue(len(valve_messages) > 0)
        last_message = valve_messages[-1]
        self.assertTrue("open" in last_message[1])

        print("✅ Test 1 passed: Valve opens and status published")

    def test_valve_open_while_another_open_closes_first_and_opens_second(self) -> None:
        """Scenario 2: When a valve-open MQTT message is received
        and there is already a valve open, then the open valve is closed,
        the closed valve is opened, and two MQTT messages are sent."""

        # First open valve A
        self._simulate_valve_command("locationa", "open")
        self.system.tick()

        # Verify valve A is open, valve B closed
        self.assertEqual(self._get_valve_pin_state(2), 1)
        self.assertEqual(self._get_valve_pin_state(3), 0)

        # Clear published messages to isolate this test
        self.mock_mqtt_client.published_messages.clear()

        # Now simulate opening valve B while A is still open
        self._simulate_valve_command("locationb", "open")
        self.system.tick()

        # Verify valve A is now closed, valve B is open
        self.assertEqual(
            self._get_valve_pin_state(2), 0, "Valve A should close when opening B"
        )
        self.assertEqual(self._get_valve_pin_state(3), 1, "Valve B should open")

        # Get published valve messages for both points
        valve_messages_a = self._get_published_valve_messages("locationa")
        valve_messages_b = self._get_published_valve_messages("locationb")

        # We should have at least one message for each valve
        self.assertTrue(len(valve_messages_a) > 0, "No status update for valve A")
        self.assertTrue(len(valve_messages_b) > 0, "No status update for valve B")

        # Verify the content
        last_message_a = valve_messages_a[-1]
        last_message_b = valve_messages_b[-1]
        self.assertTrue("closed" in last_message_a[1], "Valve A should be closed")
        self.assertTrue("open" in last_message_b[1], "Valve B should be open")

        print("✅ Test 2 passed: Valve switching works correctly")

    def test_publish_interval_elapses_triggers_sensor_messages(self) -> None:
        """Scenario 3: When publish interval (4 minutes) elapses,
        then MQTT sensor messages for all sensors are sent."""

        # Clear any initial messages
        self.mock_mqtt_client.published_messages.clear()

        # Mock sensor readings already return default values (1000 raw, 2.5V)
        # These will be converted to moisture percentage by irrigation_point

        # Take measurements first (so we have data to publish)
        self.station.take_measurements()

        # Advance time by more than the publish interval (4 minutes = 240 seconds)
        mock_time.advance(250)

        # Simulate the main loop running - this will update scheduler and execute due tasks
        self.system.tick()

        # Verify sensor messages were published for all points
        sensor_messages_a = self._get_published_sensor_messages("locationa")
        sensor_messages_b = self._get_published_sensor_messages("locationb")
        sensor_messages_c = self._get_published_sensor_messages("locationc")

        self.assertTrue(
            len(sensor_messages_a) > 0, "No sensor message published for Location A"
        )
        self.assertTrue(
            len(sensor_messages_b) > 0, "No sensor message published for Location B"
        )
        self.assertTrue(
            len(sensor_messages_c) > 0, "No sensor message published for Location C"
        )

        # Verify messages contain moisture data (as JSON)
        import json

        for messages in [sensor_messages_a, sensor_messages_b]:
            last_message = messages[-1]
            payload = last_message[1]
            # Payload should be a JSON object with "moisture" field
            try:
                data = json.loads(payload)
                moisture = data.get("moisture")
                if moisture is None:
                    self.fail(f"Sensor message missing 'moisture' field: {payload}")
                self.assertTrue(
                    0.0 <= moisture <= 100.0,
                    f"Moisture value {moisture} out of range 0-100%",
                )
            except (ValueError, TypeError) as e:
                self.fail(f"Sensor message payload invalid JSON: {payload} ({e})")

        print("✅ Test 3 passed: Sensor messages published after interval")

    def test_multiple_rapid_valve_commands_last_command_wins(self) -> None:
        """Scenario 4: When multiple rapid valve commands arrive (A, B, C),
        then only the last command (C) takes effect, appropriate valves are closed,
        and MQTT updates reflect final states."""

        # Clear any previous messages
        self.mock_mqtt_client.published_messages.clear()

        # Initially all valves closed
        self._verify_valve_state("locationa", "closed")
        self._verify_valve_state("locationb", "closed")
        self._verify_valve_state("locationc", "closed")

        # Simulate rapid commands for A, B, C (all "open")
        self._simulate_valve_command("locationa", "open")
        self._simulate_valve_command("locationb", "open")
        self._simulate_valve_command("locationc", "open")

        # Process all commands together (as they would be retrieved in one batch)
        self.system.tick()

        # Verify only valve C is open, A and B are closed
        self._verify_valve_state("locationa", "closed")
        self._verify_valve_state("locationb", "closed")
        self._verify_valve_state("locationc", "open")

        # Verify MQTT updates for each point reflect final states
        valve_messages_a = self._get_published_valve_messages("locationa")
        valve_messages_b = self._get_published_valve_messages("locationb")
        valve_messages_c = self._get_published_valve_messages("locationc")

        # Each point should have at least one update
        self.assertTrue(len(valve_messages_a) > 0, "No update for valve A")
        self.assertTrue(len(valve_messages_b) > 0, "No update for valve B")
        self.assertTrue(len(valve_messages_c) > 0, "No update for valve C")

        # Verify the final state in the last message for each point
        last_message_a = valve_messages_a[-1]
        last_message_b = valve_messages_b[-1]
        last_message_c = valve_messages_c[-1]

        # A and B should be closed, C open
        self.assertTrue("closed" in last_message_a[1], "Valve A should be closed")
        self.assertTrue("closed" in last_message_b[1], "Valve B should be closed")
        self.assertTrue("open" in last_message_c[1], "Valve C should be open")

        print("✅ Test 4 passed: Multiple rapid commands handled correctly")

    def test_wifi_reconnection_resumes_operation(self) -> None:
        """Scenario 5: When WiFi drops and reconnects,
        the system reconnects to MQTT and resumes operation."""

        # Clear any previous messages
        self.mock_mqtt_client.published_messages.clear()

        # Run one system tick to complete initial due tasks
        self.system.tick()

        # Clear messages after initial tick
        self.mock_mqtt_client.published_messages.clear()

        # Simulate WiFi drop
        self._simulate_wifi_drop()
        # WiFi manager detects disconnection on next check
        # (We call check_connection directly as scheduler would when task due)
        self.wifi_manager.check_connection()
        # At this point, WiFi manager should attempt reconnect but fail
        # (since _connected is False). We'll simulate that by leaving it False.

        # Simulate WiFi recovery
        self._simulate_wifi_recovery()
        # WiFi manager check again should succeed
        self.wifi_manager.check_connection()

        # Verify WiFi is connected
        self.assertTrue(
            mock_network.wlan_instance is not None, "WLAN instance should exist"
        )
        self.assertTrue(
            mock_network.wlan_instance._connected,
            "WiFi should be connected after recovery",
        )

        # Verify MQTT client is still connected
        self.assertTrue(
            self.mock_mqtt_client.connected,
            "MQTT client should be connected after WiFi recovery",
        )

        # Advance time for sensor measurement (80 seconds) and publish (240 seconds) tasks
        # We'll advance enough for both to be due
        mock_time.advance(250)  # > 240 seconds

        # Run system tick - should take measurements and publish sensor data
        self.system.tick()

        # Check that sensor messages were published (system resumed operation)
        sensor_messages_a = self._get_published_sensor_messages("locationa")
        self.assertTrue(
            len(sensor_messages_a) > 0,
            "Should be able to publish sensor data after WiFi reconnection",
        )

        print("✅ Test 5 passed: WiFi reconnection handled correctly")

    def test_sensor_read_failure_uses_last_valid_reading(self) -> None:
        """Scenario 6: When sensor read fails,
        the system uses last valid reading and continues operation."""

        # Clear previous messages
        self.mock_mqtt_client.published_messages.clear()

        # Run one system tick to complete initial due tasks (sensor measurement and publish)
        self.system.tick()
        # Clear messages after initial tick to isolate test
        self.mock_mqtt_client.published_messages.clear()

        # Get baseline sensor value for Location A from station sensor states
        sensor_states = self.station.get_sensor_states()
        baseline_state = next(
            (s for s in sensor_states if s.point_id == "locationa"), None
        )
        self.assertIsNotNone(baseline_state, "Should have sensor state for locationa")
        baseline_value = baseline_state.moisture
        self.assertTrue(baseline_value > 0.0, "Baseline moisture should be positive")

        # Get the ADS mock for Location A (address 0x48)
        ads_mock = self.station._ads_modules[0x48]
        original_read = ads_mock.read

        # Simulate sensor failure by making read raise OSError
        def failing_read(rate, channel):
            raise OSError("Mock ADC failure")

        ads_mock.read = failing_read

        try:
            # Advance time for sensor measurement interval (80 seconds)
            mock_time.advance(85)  # slightly more than interval
            # Run system tick - should attempt measurement, fail, and keep last value
            self.system.tick()

            # Verify sensor value is still the baseline (last known good)
            sensor_states_after = self.station.get_sensor_states()
            after_state = next(
                (s for s in sensor_states_after if s.point_id == "locationa"), None
            )
            self.assertIsNotNone(after_state, "Should have sensor state after failure")
            after_failure_value = after_state.moisture
            self.assertEqual(
                after_failure_value,
                baseline_value,
                "Sensor should use last known value after read failure",
            )

            # Advance time for publish interval (240 seconds)
            mock_time.advance(250)  # enough for publish task to be due
            # Run system tick - should publish sensor data using last known values
            self.system.tick()

            # Check that sensor messages were published
            sensor_messages_a = self._get_published_sensor_messages("locationa")
            self.assertTrue(
                len(sensor_messages_a) > 0,
                "Should be able to publish sensor data after sensor failure",
            )

            # Verify published moisture value matches last known value
            import json

            last_message = sensor_messages_a[-1]
            payload = last_message[1]
            data = json.loads(payload)
            published_moisture = data.get("moisture")
            self.assertIsNotNone(published_moisture, "Moisture field missing")
            expected_moisture = baseline_value * 100.0
            self.assertTrue(
                abs(published_moisture - expected_moisture) < 0.01,
                "Published moisture {} should match last known value {}".format(
                    published_moisture, expected_moisture
                ),
            )

        finally:
            # Restore original read method
            ads_mock.read = original_read

        print("✅ Test 6 passed: Sensor read failure handled correctly")


if __name__ == "__main__":
    unittest.main()
