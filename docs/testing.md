# Testing

Tests run in a MicroPython unix port interpreter with mocked hardware modules, using the standard `unittest.TestCase` framework.

## Setup

Install the MicroPython unix port and unittest framework (first time only):

```bash
./scripts/setup_micropython_test_env.sh
```

This builds MicroPython from source and installs the `unittest` package into it. The resulting binary is `./micropython-local` in the project root.

## Running tests

Run all tests:

```bash
python3 tests/run_tests.py
```

Run a single test file in MicroPython:

```bash
./micropython-local tests/unit/test_rolling_average.py
```

The test runner (`tests/run_tests.py`) automatically discovers all `test_*.py` files under `tests/` recursively, runs each one in the MicroPython interpreter, and reports pass/fail based on unittest output.

## Writing tests

### Basic test (no hardware mocks)

For modules that don't touch hardware (e.g., `rolling_average.py`):

```python
import sys
sys.path.insert(0, "src")
import unittest

from rolling_average import RollingAverage

class TestRollingAverage(unittest.TestCase):
    def test_basic_average(self) -> None:
        ra = RollingAverage(window_size=3)
        ra.add_reading(10)
        ra.add_reading(20)
        ra.add_reading(30)
        self.assertAlmostEqual(ra.get_average(), 15.6, places=1)

if __name__ == "__main__":
    unittest.main()
```

### Test with hardware mocks

For modules that depend on `machine`, `os`, `time`, etc., mock those modules in `sys.modules` **before** importing the code under test:

```python
import sys
sys.path.insert(0, "src")
sys.path.insert(0, "tests")
import unittest

from simple_mocks import mock_machine, mock_os, mock_time

# Create a module-like object for machine
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id
    Timer = mock_machine.Timer
    reset = lambda: None

sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["time"] = mock_time

# Now safe to import hardware-dependent code
from valve import Valve

class TestValve(unittest.TestCase):
    def test_open_sets_pin_high(self) -> None:
        pin = mock_machine.pins_created[-1] if mock_machine.pins_created else None
        valve = Valve(pin_number=2)
        valve.open()
        self.assertEqual(valve.get_state(), "open")

if __name__ == "__main__":
    unittest.main()
```

The key pattern: set up `sys.modules` with mocks at the top of the file, then import project code below that.

## Mock system

All mocks live in `tests/simple_mocks.py`. Available mock classes:

| Mock | What it replaces | Key features |
|------|-----------------|--------------|
| `MockMachine` / `MockPin` | `machine.Pin` | Tracks pin state (`_value`), records calls |
| `MockTimer` / `TimerFactory` | `machine.Timer` | Simulates timer expiration, one-shot and periodic modes |
| `MockOS` | `os` | File system stubs, `stat()`, `path` submodule |
| `MockTime` | `time` | Controllable `ticks_ms()`, `time()`, `sleep()` with `advance()` and `set_time()` |
| `MockNTPTime` | `ntptime` | No-op `settime()` |
| `MockADS1115` / `MockADS1x15Module` | `ads1x15` | Configurable `read()` and `raw_to_v()` return values |
| `MockMQTTClient` | `umqtt.simple.MQTTClient` | Tracks published messages, subscriptions, connection state |
| `MockNetwork` | `network` | Mock WLAN with connect/disconnect tracking |
| `MockGC` | `gc` | Tracks `collect()` calls |

Global pre-built instances are available at the bottom of the file (`mock_machine`, `mock_os`, `mock_time`, etc.).

### Adding a new mock

1. Add the mock class to `tests/simple_mocks.py`
2. Create a global instance if needed
3. In your test file, inject it into `sys.modules` before importing project code

## Test coverage

### Unit tests (`tests/unit/`)

| Test file | Module under test |
|-----------|-------------------|
| `test_config.py` | Configuration parsing and validation |
| `test_logger.py` | Logging utilities with file I/O mocking |
| `test_rolling_average.py` | Rolling average and EMA calculations |
| `test_valve.py` | Valve control with mocked GPIO pins |
| `test_sensor.py` | Soil moisture sensor with ADS1115 mock |
| `test_irrigation_point.py` | Individual irrigation point logic |
| `test_irrigation_station.py` | Station management with multiple points |
| `test_time_keeper.py` | NTP time synchronization and scheduling |
| `test_watchdog.py` | System watchdog with timer mocking |
| `test_mqtt_hass_manager.py` | MQTT Home Assistant integration |
| `test_mqtt_hass_entities.py` | HA entity discovery and state publishing |
| `test_mqtt_robust_client.py` | MQTT client with reconnection logic |
| `test_wifi_manager.py` | WiFi connection management |
| `test_task_scheduler.py` | Task scheduling |

### Integration tests (`tests/integration/`)

| Test file | What it tests |
|-----------|---------------|
| `test_firmware_controller.py` | End-to-end firmware controller flow |

### Hardware diagnostics (`diagnostics/`)

These run on the actual Pico device, not in the test runner:

```bash
mpremote run diagnostics/check_sensors.py
mpremote run diagnostics/check_valves.py
```

See `diagnostics/README.md` for terminal-to-GPIO/ADS mapping tables.
