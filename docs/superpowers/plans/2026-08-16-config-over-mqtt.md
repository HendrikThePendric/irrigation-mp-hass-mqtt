# Config-over-MQTT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow pushing a full `config.json` to the device over MQTT, overwrite it atomically, reboot, and verify from the dev machine that the device loaded exactly what was sent.

**Architecture:** The device subscribes to `irrigation/{station_id}/config/set`, atomically writes the payload to `config.json`, and reboots. On boot it publishes the loaded config to a retained `irrigation/{station_id}/config/current` topic. A dev-machine helper script (`scripts/send_config.sh`) publishes the config, waits for the reboot, and diffs the echoed config against the sent file.

**Tech Stack:** MicroPython (Pico W), `umqtt.simple` via `MqttRobustClient`, bash + `mosquitto_pub`/`mosquitto_sub` (helper), MicroPython `unittest` (tests).

## Global Constraints

- MicroPython-compatible Python only (no f-strings with `=` specifier, no walrus in complex expressions, no `list[str]` in runtime-evaluated positions — note existing code already uses `float | None` and `list[str]` in type hints, which MicroPython tolerates since they are annotations).
- Type hints required on function signatures and class attributes.
- No validation of the incoming config before reboot (explicit user decision).
- Tests run in the MicroPython interpreter via `./micropython-local <test_file>`; the full suite via `python3 tests/run_tests.py`.
- Never commit `config.json` or `certs/*`.
- `station_id` derives from `machine.unique_id()` and is stable across config overwrites.

---

### Task 1: Boot echo + config topic subscription (device side)

**Files:**
- Modify: `src/mqtt_hass_manager.py`
- Modify: `src/firmware_controller.py`
- Modify: `tests/simple_mocks.py`
- Modify: `tests/unit/test_mqtt_hass_manager.py`

**Interfaces:**
- Consumes: `MqttHassManager(config, logger)` — existing constructor; `Config`, `Logger` from existing modules.
- Produces: `MqttHassManager(config, logger, config_path="./config.json")`; `self._config_path`; methods `_subscribe_config_topic()`, `_publish_config_current()`; `setup()` now publishes `irrigation/{station_id}/config/current` (retained) and subscribes `irrigation/{station_id}/config/set`. `FirmwareController` now passes `config_path` to `MqttHassManager`.

- [ ] **Step 1: Extend mocks to track `reset` and `rename`**

In `tests/simple_mocks.py`, update `MockMachine`:

```python
class MockMachine:
    """Mock machine module."""

    def __init__(self):
        self.pins_created = []
        self.Pin = PinFactory(self)
        self.I2C = type("MockI2C", (), {"init": lambda self, **kwargs: None})
        self.Timer = TimerFactory(self)
        self.timers_created = []
        self.reset_calls = []

    def unique_id(self) -> bytes:
        """Return a mock unique ID."""
        return b"mock-device-id-12345"

    def reset(self) -> None:
        """Mock reset function."""
        self.reset_calls.append(())
```

In the same file, add an `__init__` to `MockOS` and track `rename`:

```python
# Mock os module
class MockOS:
    _files = {}
    """Mock os module."""

    def __init__(self):
        self.rename_calls = []

    # ... existing attributes unchanged ...
```

And change the existing `rename` method (currently `def rename(self, old: str, new: str) -> None: pass`) to:

```python
    def rename(self, old: str, new: str) -> None:
        self.rename_calls.append((old, new))
```

- [ ] **Step 2: Write the failing test**

In `tests/unit/test_mqtt_hass_manager.py`:

2a. Replace `reset = lambda: None` (line 29) with the tracked bound method:

```python
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id
    RTC = type("MockRTC", (), {"datetime": lambda self: (2024, 1, 1, 0, 0, 0, 0, 0)})
    I2C = type("MockI2C", (), {"__init__": lambda self, *args, **kwargs: None})
    reset = mock_machine.reset
```

2b. After `import unittest` (line 61), add file-I/O mocking (same pattern as `test_logger.py`):

```python
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
```

2c. Update `setUp` to clear all mock state:

```python
    def setUp(self) -> None:
        """Reset mock state before each test."""
        from simple_mocks import MockMQTTClient

        MockMQTTClient.reset_instances()
        file_writes.clear()
        file_opens.clear()
        mock_machine.reset_calls.clear()
        mock_os.rename_calls.clear()
```

2d. Add the two new test methods inside `TestMqttHassManagerNew` (after `test_mqtt_hass_manager_setup`):

```python
    def test_setup_subscribes_to_config_topic(self) -> None:
        """Test setup subscribes to the config/set topic."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore
        manager.setup()

        self.assertIn("irrigation/teststation/config/set", manager._client.subscribe_calls)

    def test_boot_echo_publishes_config_current(self) -> None:
        """Test setup publishes the loaded config to config/current (retained)."""
        config = MockConfig()
        logger = MockLogger()

        manager = MqttHassManager(config, logger)  # type: ignore

        file_writes["./config.json"] = '{"station_name": "Test Station"}'

        manager.setup()

        self.assertTrue(
            any(
                topic == "irrigation/teststation/config/current"
                and message == '{"station_name": "Test Station"}'
                and retain is True
                for topic, message, retain, qos in manager._client.published_messages
            )
        )
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./micropython-local tests/unit/test_mqtt_hass_manager.py`
Expected: FAIL — `test_setup_subscribes_to_config_topic` fails because `config/set` is never subscribed; `test_boot_echo_publishes_config_current` fails because no `config/current` message is published.

- [ ] **Step 4: Implement device-side changes**

In `src/mqtt_hass_manager.py`:

4a. Add imports (before `from ssl import ...` on line 15):

```python
from machine import reset
from os import rename
from ssl import SSLContext, PROTOCOL_TLS_CLIENT
```

4b. Change the constructor to accept and store `config_path`:

```python
    def __init__(
        self,
        config: Config,
        logger: Logger,
        config_path: str = "./config.json",
    ) -> None:
        self._config = config
        self._logger = logger
        self._config_path = config_path
        # ... rest of __init__ unchanged ...
```

4c. In `setup()` (lines 111-117), add the config subscription and boot echo:

```python
    def setup(self) -> None:
        """Connect to MQTT, publish availability, set up HA entities and subscriptions."""
        self._connect()
        self._client.set_callback(self._handle_message)
        self._set_online()
        self._publish_config_current()
        self._setup_entities()
        self._monitor_hass_status()
        self._subscribe_config_topic()
```

4d. In `_resubscribe_after_reconnect()` (lines 95-109), add `self._subscribe_config_topic()` after the calibration loop:

```python
            for point_id in self._config.irrigation_points:
                self._subscribe_calibration_topics(point_id)
            self._subscribe_config_topic()
            self._logger.log("Resubscribed to all command topics after reconnection")
```

4e. Add the new methods (place them after `_subscribe_calibration_topics`, around line 267):

```python
    def _subscribe_config_topic(self) -> None:
        """Subscribe to the config overwrite command topic."""
        topic = self._topic("config/set")
        try:
            self._client.subscribe(topic)
        except Exception as e:
            self._logger.log(f"Failed to subscribe to {topic}: {e}")

    def _publish_config_current(self) -> None:
        """Publish the loaded config file contents (retained) for verification."""
        try:
            with open(self._config_path) as f:
                config_text = f.read()
            self._client.publish(
                self._topic("config/current"),
                config_text,
                retain=True,
            )
        except Exception as e:
            self._logger.log(f"Failed to publish current config: {e}")
```

4f. In `src/firmware_controller.py` line 35, pass `config_path` through:

```python
        self._mqtt_manager = MqttHassManager(
            self._config, self._logger, config_path=config_path
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./micropython-local tests/unit/test_mqtt_hass_manager.py`
Expected: PASS (all tests in the file, including the two new ones and all existing ones).

- [ ] **Step 6: Run the full test suite**

Run: `python3 tests/run_tests.py`
Expected: `✅ All tests passed!`

- [ ] **Step 7: Type check**

Run: `.venv/bin/pyright src/mqtt_hass_manager.py src/firmware_controller.py` (or `pyright src/` if `pyright` is on PATH)
Expected: no new errors. Note the repo's `pyrightconfig.json` reports no unused-variable/import diagnostics.

- [ ] **Step 8: Commit**

```bash
git add src/mqtt_hass_manager.py src/firmware_controller.py tests/simple_mocks.py tests/unit/test_mqtt_hass_manager.py
git commit -m "feat: publish loaded config and subscribe to config/set topic"
```

---

### Task 2: Handle `config/set` — atomic write + reboot

**Files:**
- Modify: `src/mqtt_hass_manager.py`
- Modify: `tests/unit/test_mqtt_hass_manager.py`

**Interfaces:**
- Consumes: `self._config_path`, `rename` (imported from `os`), `reset` (imported from `machine`), `self._topic(...)` — all produced by Task 1.
- Produces: `_handle_config_set(msg: str)` method; `_handle_message` now routes `config/set` to it. After handling, the device writes `config.json.tmp` then renames over `config.json` and calls `reset()`.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_mqtt_hass_manager.py`, inside `TestMqttHassManagerNew`:

```python
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

        self.assertNotIn("./config.json.tmp", file_writes)
        self.assertEqual(len(mock_machine.reset_calls), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./micropython-local tests/unit/test_mqtt_hass_manager.py`
Expected: FAIL — `config/set` messages are currently ignored (the existing `_handle_message` returns early because `action` resolves to `"set"`, which has no branch).

- [ ] **Step 3: Implement the handler**

In `src/mqtt_hass_manager.py`, add the branch to `_handle_message` (after the `homeassistant/status` check at lines 286-288):

```python
        if topic == "homeassistant/status":
            self._handle_ha_status_message(msg)
            return

        if topic == self._topic("config/set"):
            self._handle_config_set(msg)
            return
```

Add the handler method (next to `_handle_ha_status_message`, around line 329):

```python
    def _handle_config_set(self, msg: str) -> None:
        """Overwrite config.json with the received payload, then reboot."""
        tmp_path = self._config_path + ".tmp"
        try:
            with open(tmp_path, "w") as f:
                f.write(msg)
            rename(tmp_path, self._config_path)
            self._logger.log("Config updated via MQTT - rebooting")
        except Exception as e:
            self._logger.log(f"Failed to write config: {e}")
            return
        reset()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./micropython-local tests/unit/test_mqtt_hass_manager.py`
Expected: PASS.

- [ ] **Step 5: Run the full test suite**

Run: `python3 tests/run_tests.py`
Expected: `✅ All tests passed!`

- [ ] **Step 6: Type check**

Run: `.venv/bin/pyright src/mqtt_hass_manager.py`
Expected: no new errors.

- [ ] **Step 7: Commit**

```bash
git add src/mqtt_hass_manager.py tests/unit/test_mqtt_hass_manager.py
git commit -m "feat: overwrite config.json from MQTT and reboot"
```

---

### Task 3: Helper script `scripts/send_config.sh`

**Files:**
- Create: `scripts/send_config.sh`

**Interfaces:**
- Consumes: `certs/ca_crt.der`, `certs/irrigationbackyard_crt.der`, `certs/irrigationbackyard_key.der`; `mosquitto_pub`/`mosquitto_sub`; `python3`; `config.json` in the project root.
- Produces: a standalone bash script (no args, or an optional config path) that publishes a config file and verifies it was applied.

- [ ] **Step 1: Create the script**

Create `scripts/send_config.sh` with this content:

```bash
#!/usr/bin/env bash
# send_config.sh - Send a new config.json to the irrigation station over MQTT.
#
# Usage:
#   ./scripts/send_config.sh [path-to-config.json]
#
# Publishes the config file to the station's config/set topic, waits for the
# device to reboot, and verifies the device loaded the exact file by comparing
# the retained config/current echo.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CACHE_FILE="$PROJECT_DIR/.station_id_cache"
CONFIG_FILE="${1:-$PROJECT_DIR/config.json}"

PORT="${MQTT_PORT:-8883}"
BROKER="${MQTT_BROKER:-}"
CA_CERT="$PROJECT_DIR/certs/ca_crt.der"
CLIENT_CERT="$PROJECT_DIR/certs/irrigationbackyard_crt.der"
CLIENT_KEY="$PROJECT_DIR/certs/irrigationbackyard_key.der"

TLS_OPTS=(--cafile "$CA_CERT" --cert "$CLIENT_CERT" --key "$CLIENT_KEY")

mosquitto_cmd() {
    local cmd="$1"
    shift
    if [ "$cmd" = "sub" ]; then
        mosquitto_sub -h "$BROKER" -p "$PORT" "${TLS_OPTS[@]}" "$@" 2>/dev/null
    else
        mosquitto_pub -h "$BROKER" -p "$PORT" "${TLS_OPTS[@]}" "$@"
    fi
}

require_mosquitto() {
    if ! command -v mosquitto_pub &> /dev/null; then
        echo "ERROR: mosquitto-clients not installed." >&2
        echo "Run: sudo apt install mosquitto-clients" >&2
        exit 1
    fi
}

get_broker() {
    if [ -n "$BROKER" ]; then
        return
    fi
    BROKER=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['network']['mqtt_broker_ip'])" "$CONFIG_FILE" 2>/dev/null || true)
    if [ -z "$BROKER" ]; then
        echo "ERROR: Could not determine broker from $CONFIG_FILE." >&2
        echo "Set MQTT_BROKER to override." >&2
        exit 1
    fi
}

discover_station_id() {
    if [ -f "$CACHE_FILE" ]; then
        cat "$CACHE_FILE"
        return
    fi
    echo "Discovering station_id..." >&2
    local topic
    topic=$(mosquitto_cmd sub -t "irrigation/+/availability" -C 1 --retained-only -F '%t' 2>/dev/null || true)
    if [ -z "$topic" ]; then
        echo "ERROR: Could not discover station_id. Is the Pico online?" >&2
        exit 1
    fi
    local sid
    sid=$(echo "$topic" | head -1 | cut -d'/' -f2)
    if [ -z "$sid" ]; then
        echo "ERROR: Could not parse station_id from topic: $topic" >&2
        exit 1
    fi
    echo "Discovered station_id: $sid" >&2
    echo "$sid" > "$CACHE_FILE"
    echo "$sid"
}

verify_config() {
    local sid="$1"
    local tmp
    tmp=$(mktemp)
    local current
    current=$(mosquitto_cmd sub -t "irrigation/${sid}/config/current" -C 1 --retained-only -F '%p' 2>/dev/null || true)
    if [ -z "$current" ]; then
        rm -f "$tmp"
        return 1
    fi
    printf '%s\n' "$current" > "$tmp"
    python3 -c "import json,sys; sent=json.load(open(sys.argv[1])); got=json.load(open(sys.argv[2])); sys.exit(0 if sent==got else 1)" "$CONFIG_FILE" "$tmp" 2>/dev/null
    rm -f "$tmp"
}

main() {
    require_mosquitto

    if [ ! -f "$CONFIG_FILE" ]; then
        echo "ERROR: Config file not found: $CONFIG_FILE" >&2
        exit 1
    fi

    get_broker
    local sid
    sid=$(discover_station_id)

    echo "Sending $CONFIG_FILE to station $sid..."
    mosquitto_cmd pub -t "irrigation/${sid}/config/set" -f "$CONFIG_FILE"

    echo "Waiting for device to reboot and confirm..."
    local confirmed=0
    for _ in $(seq 1 60); do
        if verify_config "$sid"; then
            confirmed=1
            break
        fi
        sleep 1
    done

    if [ "$confirmed" -eq 1 ]; then
        local station_name
        station_name=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['station_name'])" "$CONFIG_FILE" 2>/dev/null || echo "?")
        echo "OK: config applied and verified."
        echo "    station_name: $station_name"
        exit 0
    else
        echo "FAILED: device did not confirm the new config within 60s." >&2
        exit 1
    fi
}

main "$@"
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/send_config.sh`

- [ ] **Step 3: Syntax check**

Run: `bash -n scripts/send_config.sh`
Expected: no output (syntax OK).

- [ ] **Step 4: Commit**

```bash
git add scripts/send_config.sh
git commit -m "feat: add helper script to send config over MQTT"
```

---

### Task 4: Documentation

**Files:**
- Modify: `docs/mqtt-topics.md`
- Modify: `docs/config.md`

- [ ] **Step 1: Document the new topics**

In `docs/mqtt-topics.md`, add two rows to the topic-pattern table (after the `broker_connectivity` row):

```markdown
| `irrigation/{station_id}/config/set` | Subscribe | Command to overwrite `config.json` and reboot |
| `irrigation/{station_id}/config/current` | Publish | Echo of the loaded `config.json` after boot (retained) |
```

Add a new subsection under "## Subscriptions" (after "### Home Assistant status"):

```markdown
### Config overwrite

**Topic:** `irrigation/{station_id}/config/set`

Payload: the full `config.json` contents. On receipt, the station atomically overwrites `config.json` and reboots. After boot it republishes the loaded config to `config/current` (retained) for verification.
```

Add a bullet to "## Reconnection behavior":

```markdown
4. Re-subscribes to `irrigation/{station_id}/config/set`
```

- [ ] **Step 2: Document the helper script**

In `docs/config.md`, append a new section after "## Security":

```markdown
## Updating config over MQTT

Once the station is installed, you can push a new `config.json` over MQTT without opening the enclosure:

```bash
./scripts/send_config.sh [path-to-config.json]
```

The script publishes the config to `irrigation/{station_id}/config/set`, the station overwrites `config.json` and reboots, and the script verifies the device loaded the exact file by diffing the retained `config/current` echo. No validation is performed before reboot — a malformed config will prevent the station from booting, requiring a USB cable to fix.
```

- [ ] **Step 3: Commit**

```bash
git add docs/mqtt-topics.md docs/config.md
git commit -m "docs: document config-over-MQTT topics and helper script"
```

---

## Self-Review

**Spec coverage:**
- Subscribe `config/set` → Task 1.
- Atomic write + reboot → Task 2.
- Boot echo `config/current` → Task 1.
- Helper script (publish + verify) → Task 3.
- Docs → Task 4.
- No validation / no partial updates → enforced by design (whole-file write, no parsing).

**Placeholder scan:** none — all steps contain full code.

**Type consistency:** `config_path` (kwarg) is used consistently in `mqtt_hass_manager.py` and `firmware_controller.py`; `_config_path` attribute matches; `mock_os.rename_calls` and `mock_machine.reset_calls` names match between `simple_mocks.py` and the tests.
