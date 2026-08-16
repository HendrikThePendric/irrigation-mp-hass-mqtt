#!/usr/bin/env bash
# send_config.sh - Send a new config.json to the irrigation station over MQTT.
#
# Usage:
#   ./scripts/send_config.sh [path-to-config.json]
#
# Publishes the config file to the station's config/set topic, then waits for
# the device to reboot and republish its config summary (config/current), and
# prints that summary so the change can be verified.
#
# Exit code 0 on success (sent + rebooted + summary printed), non-zero on
# failure. Output is deterministic so it can be driven by automation.
#
# Environment overrides:
#   MQTT_BROKER  - broker host (default: network.mqtt_broker_ip from config.json)
#   MQTT_PORT    - broker port (default: 8883)
#   STATION_ID   - station_id to target (default: auto-discovered)

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
    if ! command -v mosquitto_pub &> /dev/null || ! command -v mosquitto_sub &> /dev/null; then
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
    echo "Broker: $BROKER (from $CONFIG_FILE; set MQTT_BROKER to target a different broker)" >&2
}

discover_station_id() {
    if [ -n "${STATION_ID:-}" ]; then
        echo "$STATION_ID"
        return
    fi
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

show_config() {
    local sid="$1"
    mosquitto_cmd sub -t "irrigation/${sid}/config/current" -C 1 --retained-only -F '%p' 2>/dev/null || true
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

    local old
    old=$(show_config "$sid")

    echo "Sending $CONFIG_FILE to station $sid..."
    mosquitto_cmd pub -t "irrigation/${sid}/config/set" -f "$CONFIG_FILE"

    echo "Waiting for device to reboot and apply..."
    local new
    for _ in $(seq 1 60); do
        new=$(show_config "$sid")
        if [ -n "$new" ] && [ "$new" != "$old" ]; then
            echo "OK: device rebooted with the new config."
            echo "----------------------------------------"
            echo "$new"
            echo "----------------------------------------"
            exit 0
        fi
        sleep 1
    done

    echo "FAILED: device did not confirm the new config within 60s." >&2
    exit 1
}

main "$@"
