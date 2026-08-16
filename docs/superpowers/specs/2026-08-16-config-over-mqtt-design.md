# Config over MQTT — Design

**Date:** 2026-08-16
**Status:** Approved

## Problem

The irrigation system's `config.json` is flashed onto the Pico during deployment.
Once the system is installed in the garden, tweaking thresholds, timings, or point
names requires opening the enclosure and connecting a cable. We want to be able to
push a new `config.json` to the device over MQTT, have it overwrite the file, and
reboot to apply the new configuration.

## Goals

- Push a full `config.json` to the device over MQTT and reboot to apply it.
- Verify from the dev machine that the device loaded exactly what was sent.
- Keep the device-side implementation minimal.

## Non-goals

- No validation of the incoming config before reboot. A malformed config will cause
  the device to crash-loop at boot; recovery is "open the box, connect a cable, fix it."
- No partial/field-level updates. The whole file is always sent.
- No changes to device identity or MQTT topics (they derive from hardware `unique_id`).

## Design

### Device side (`src/`)

1. **Subscribe to `irrigation/{station_id}/config/set`.** The subscription is added
   to the existing reconnect flow in `MqttHassManager._resubscribe_after_reconnect`
   and to the initial setup, so it is restored automatically after reconnects.

2. **Handle `config/set`.** In `MqttHassManager._handle_message`, add a branch for
   `action == "config/set"`:
   - Write the payload atomically: write `config.json.tmp`, then rename over
     `config.json` (`os.rename`). This protects against a power cut mid-write leaving
     a truncated `config.json`.
   - Reboot via `machine.reset()`. The handler runs on the main loop (single-threaded),
     so the write + reset are safe in-place.

3. **Boot echo.** In `MqttHassManager.setup()`, after publishing availability, publish
   the raw text of the loaded `config.json` to the retained topic
   `irrigation/{station_id}/config/current`. This is the verification source the helper
   diffs against.

### Helper script (`scripts/send_config.sh`)

Follows the existing `scripts/calibrate.sh` conventions (`mosquitto_cmd`,
`require_mosquitto`, `discover_station_id`, `TLS_OPTS`, DER certs from `certs/`).

Flow:

1. Read local `config.json` to obtain `network.mqtt_broker_ip` (with an env-var
   override, mirroring `calibrate.sh`'s `MQTT_PORT` pattern).
2. Discover `station_id` (reuse the `irrigation/+/availability` retained subscribe and
   `.station_id_cache` pattern).
3. Publish the config file contents to `irrigation/{sid}/config/set`.
4. Wait for the `availability` topic to go offline (reboot) then online (reconnect).
5. Wait for a fresh retained `config/current`; `diff` it against the sent file and
   print the result, including the new `station_name` so renames are obvious.

## MQTT topic summary

| Topic | Direction | Retain | Purpose |
|-------|-----------|--------|---------|
| `irrigation/{sid}/config/set` | helper → device | no | Command to overwrite `config.json` and reboot |
| `irrigation/{sid}/config/current` | device → helper | yes | Echo of the loaded `config.json` after boot |
| `irrigation/{sid}/availability` | device | yes | Existing LWT online/offline signal |

## Key decisions

- **Atomic write** (tmp + rename) is retained despite the "keep it simple" preference,
  because a truncated `config.json` is the one failure mode that cannot be recovered
  by sending another config over MQTT (the device won't boot far enough to subscribe).
- **No validation** of incoming config (explicit user decision).
- **`station_id` is stable** — it derives from `machine.unique_id()`, which is permanent
  hardware identity and unaffected by config overwrites. Topics and Home Assistant
  entities survive config changes.
- **TLS**: the helper uses `mosquitto_pub`/`mosquitto_sub` with the existing DER certs
  (as `calibrate.sh` already does), so no certificate conversion is needed.

## Testing

- Unit tests (MicroPython `unittest`, mock `machine`) for the `config/set` message
  handler: valid payload writes atomically and triggers reset; the boot echo publishes
  the loaded config.
- Manual validation: run `send_config.sh` against the device, confirm the device
  reboots, and the helper reports a clean diff.
