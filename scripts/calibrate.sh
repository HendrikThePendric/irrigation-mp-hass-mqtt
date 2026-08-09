#!/usr/bin/env bash
# calibrate.sh - Remote sensor calibration via MQTT
#
# Usage:
#   ./scripts/calibrate.sh                    Interactive wizard (guide through dry/wet calibration)
#   ./scripts/calibrate.sh voltage <pid>      Measure live voltage (10 samples, averaged)
#   ./scripts/calibrate.sh get <pid>          Read current calibration values
#   ./scripts/calibrate.sh set-dry <pid> <V>   Set dry voltage
#   ./scripts/calibrate.sh set-wet <pid> <V>   Set wet voltage
#
# Prerequisites: mosquitto-clients, TLS certs in certs/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CACHE_FILE="$PROJECT_DIR/.station_id_cache"
CONFIG_FILE="$PROJECT_DIR/config.json"

BROKER="192.168.2.201"
PORT="${MQTT_PORT:-8883}"
CA_CERT="$PROJECT_DIR/certs/ca_crt.der"
CLIENT_CERT="$PROJECT_DIR/certs/irrigationbackyard_crt.der"
CLIENT_KEY="$PROJECT_DIR/certs/irrigationbackyard_key.der"

TLS_OPTS=(--cafile "$CA_CERT" --cert "$CLIENT_CERT" --key "$CLIENT_KEY")
SID=""

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

discover_station_id() {
    if [ -n "$SID" ]; then
        echo "$SID"
        return
    fi
    if [ -f "$CACHE_FILE" ]; then
        SID=$(cat "$CACHE_FILE")
        echo "$SID"
        return
    fi
    echo "Discovering station_id..." >&2
    local result
    result=$(mosquitto_cmd sub -t "irrigation/+/availability" -C 1 --retained-only 2>/dev/null || true)
    if [ -z "$result" ]; then
        echo "ERROR: Could not discover station_id. Is the Pico online?" >&2
        exit 1
    fi
    SID=$(echo "$result" | head -1 | awk '{print $1}' | cut -d'/' -f2)
    if [ -z "$SID" ]; then
        echo "ERROR: Could not parse station_id from MQTT message" >&2
        exit 1
    fi
    echo "Discovered station_id: $SID" >&2
    echo "$SID" > "$CACHE_FILE"
    echo "$SID"
}

discover_points() {
    local sid="$1"
    # Subscribe to dry_v state topics to discover all points with calibration
    local result
    result=$(mosquitto_cmd sub -t "irrigation/${sid}/+/calibration/dry_v" -C 20 --retained-only -W 2 2>/dev/null || true)
    local points=()
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            local pid
            pid=$(echo "$line" | head -1 | awk '{print $1}' | cut -d'/' -f3)
            if [ -n "$pid" ] && [[ ! " ${points[*]} " =~ " ${pid} " ]]; then
                points+=("$pid")
            fi
        fi
    done <<< "$result"

    # Fallback: try sensor topics too
    if [ ${#points[@]} -eq 0 ]; then
        result=$(mosquitto_cmd sub -t "irrigation/${sid}/+/sensor" -C 20 --retained-only -W 2 2>/dev/null || true)
        while IFS= read -r line; do
            if [ -n "$line" ]; then
                local pid
                pid=$(echo "$line" | head -1 | awk '{print $1}' | cut -d'/' -f3)
                if [ -n "$pid" ] && [[ ! " ${points[*]} " =~ " ${pid} " ]]; then
                    points+=("$pid")
                fi
            fi
        done <<< "$result"
    fi

    printf '%s\n' "${points[@]}"
}

measure_voltage() {
    local sid="$1" pid="$2" label="$3"
    echo "Measuring $label voltage ($pid)..." >&2

    local total=0.0 count=0
    for i in $(seq 1 10); do
        mosquitto_cmd pub -t "irrigation/${sid}/${pid}/voltage/measure" -m "measure" 2>/dev/null
        local v
        v=$(mosquitto_cmd sub -t "irrigation/${sid}/${pid}/voltage" -C 1 --retained-only 2>/dev/null || true)
        if [ -z "$v" ]; then
            sleep 0.2
            continue
        fi
        local value
        value=$(echo "$v" | head -1 | awk '{print $NF}')
        if [[ "$value" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            total=$(python3 -c "print($total + $value)" 2>/dev/null || echo "$total")
            count=$((count + 1))
            printf "  %2d: %sV\r" "$count" "$value" >&2
        fi
        sleep 0.15
    done
    echo "" >&2

    if [ "$count" -eq 0 ]; then
        echo "ERROR: No valid readings" >&2
        return 1
    fi
    python3 -c "print(round($total / $count, 3))" 2>/dev/null
}

set_calibration() {
    local sid="$1" pid="$2" field="$3" value="$4"
    mosquitto_cmd pub -t "irrigation/${sid}/${pid}/calibration/${field}/set" -m "$value"
    echo "  Set ${field} = ${value}V" >&2
}

get_calibration() {
    local sid="$1" pid="$2"
    local dry wet
    dry=$(mosquitto_cmd sub -t "irrigation/${sid}/${pid}/calibration/dry_v" -C 1 --retained-only 2>/dev/null | head -1 | awk '{print $NF}' || echo "?")
    wet=$(mosquitto_cmd sub -t "irrigation/${sid}/${pid}/calibration/wet_v" -C 1 --retained-only 2>/dev/null | head -1 | awk '{print $NF}' || echo "?")
    echo "  dry_v: ${dry}V  wet_v: ${wet}V"
}

run_wizard() {
    local sid
    sid=$(discover_station_id)
    echo ""

    echo "Discovering irrigation points..."
    local points
    mapfile -t points < <(discover_points "$sid")

    if [ ${#points[@]} -eq 0 ]; then
        echo "ERROR: No irrigation points discovered. Is the Pico running?" >&2
        exit 1
    fi

    echo ""
    echo "Available irrigation points:"
    for i in "${!points[@]}"; do
        echo "  $((i+1)). ${points[$i]}"
    done
    echo ""

    local selection
    read -r -p "Select points to calibrate (e.g., 1 or 1,2,3 or all): " selection

    local selected=()
    if [ "$selection" = "all" ]; then
        selected=("${points[@]}")
    else
        IFS=',' read -ra indices <<< "$selection"
        for idx in "${indices[@]}"; do
            idx=$((idx - 1))
            if [ "$idx" -ge 0 ] && [ "$idx" -lt ${#points[@]} ]; then
                selected+=("${points[$idx]}")
            fi
        done
    fi

    if [ ${#selected[@]} -eq 0 ]; then
        echo "No valid points selected."
        exit 1
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Sensor Calibration Wizard"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "For each sensor you'll be asked to:"
    echo "  1. Place it in DRY soil, press Enter"
    echo "  2. Place it in WET soil, press Enter"
    echo ""

    for pid in "${selected[@]}"; do
        echo ──────────────────────────────────────────
        echo "  Calibrating: $pid"
        echo ──────────────────────────────────────────
        echo ""

        read -r -p "  [1/2] Put sensor in DRY soil, then press Enter... "

        local dry_v
        dry_v=$(measure_voltage "$sid" "$pid" "dry")
        if [ -z "$dry_v" ]; then
            echo "  SKIPPED: Could not measure dry voltage"
            continue
        fi
        set_calibration "$sid" "$pid" "dry_v" "$dry_v"

        echo ""
        read -r -p "  [2/2] Put sensor in WET soil, then press Enter... "

        local wet_v
        wet_v=$(measure_voltage "$sid" "$pid" "wet")
        if [ -z "$wet_v" ]; then
            echo "  SKIPPED: Could not measure wet voltage"
            continue
        fi
        set_calibration "$sid" "$pid" "wet_v" "$wet_v"

        echo ""
        echo "  Calibration result for $pid:"
        get_calibration "$sid" "$pid"
        echo ""
    done

    echo ──────────────────────────────────────────
    echo "  Calibration complete!"
    echo ──────────────────────────────────────────
}

do_voltage() {
    local sid="$1" pid="$2"
    measure_voltage "$sid" "$pid" ""
}

do_get() {
    local sid="$1" pid="$2"
    get_calibration "$sid" "$pid"
}

do_set() {
    local sid="$1" pid="$2" field="$3" value="$4"
    if ! [[ "$value" =~ ^[0-9]+\.?[0-9]*$ ]]; then
        echo "ERROR: Invalid voltage value: $value" >&2
        exit 1
    fi
    set_calibration "$sid" "$pid" "$field" "$value"
    get_calibration "$sid" "$pid"
}

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  (no args)                 Interactive calibration wizard"
    echo "  voltage <point_id>        Take 10 voltage readings and print average"
    echo "  get <point_id>            Show current dry/wet calibration values"
    echo "  set-dry <point_id> <V>    Set dry voltage"
    echo "  set-wet <point_id> <V>    Set wet voltage"
    exit 1
}

# --- main ---
require_mosquitto

if [ $# -eq 0 ]; then
    run_wizard
    exit 0
fi

COMMAND="$1"
[ "${COMMAND:0:1}" = "-" ] && usage
[ $# -lt 2 ] && usage

POINT_ID="$2"

# Discover station_id once (cached)
SID=$(discover_station_id)

case "$COMMAND" in
    voltage)
        do_voltage "$SID" "$POINT_ID"
        ;;
    get)
        do_get "$SID" "$POINT_ID"
        ;;
    set-dry)
        [ $# -lt 3 ] && usage
        do_set "$SID" "$POINT_ID" "dry_v" "$3"
        ;;
    set-wet)
        [ $# -lt 3 ] && usage
        do_set "$SID" "$POINT_ID" "wet_v" "$3"
        ;;
    *)
        usage
        ;;
esac
