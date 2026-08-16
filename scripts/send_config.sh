#!/usr/bin/env bash
# send_config.sh - Send a new config.json to the irrigation station over MQTT.
#
# Usage:
#   ./scripts/send_config.sh [path-to-config.json]
#
# Publishes the config file to the station's config/set topic, waits for the
# device to reboot, and verifies the device loaded the exact file by comparing
# the retained config/current echo (WiFi credentials are redacted in the echo).

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
    local current
    current=$(mosquitto_cmd sub -t "irrigation/${sid}/config/current" -C 1 --retained-only -F '%p' 2>/dev/null || true)
    if [ -z "$current" ]; then
        return 1
    fi
    local tmp
    tmp=$(mktemp)
    printf '%s\n' "$current" > "$tmp"
    if python3 -c '
import json, sys
def redact(conf):
    net = conf.get("network")
    if isinstance(net, dict):
        net["wifi_ssid"] = "REDACTED"
        net["wifi_password"] = "REDACTED"
    return conf
sent = redact(json.load(open(sys.argv[1])))
got = redact(json.load(open(sys.argv[2])))
sys.exit(0 if sent == got else 1)
' "$CONFIG_FILE" "$tmp" 2>/dev/null; then
        rm -f "$tmp"
        return 0
    else
        rm -f "$tmp"
        return 1
    fi
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
