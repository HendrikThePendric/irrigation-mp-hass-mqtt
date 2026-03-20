#!/bin/bash

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "$SCRIPT_DIR/common.sh"

# Run from this dir
cd "$SCRIPT_DIR" || exit 1

print_info "Starting factory reset of Pico device..."
print_warning "⚠️  WARNING: This will erase ALL data on the device!"
print_info ""

# Check if device is in BOOTSEL mode
print_info "Checking if device is in BOOTSEL mode..."

# Get picotool path (handles sudo and user locations)
PICOTOOL_PATH="$(get_picotool_path)" || exit 1

# Try to run picotool to check permissions and device presence
output=$("$PICOTOOL_PATH" info 2>&1 || true)

# Check for permission denied message first (most specific)
if echo "$output" | grep -qi "appears to be in BOOTSEL mode, but.*unable to connect\|was unable to connect"; then
    print_error "Device detected but permission denied"
    print_info ""
    print_info "Your user may need to be in the 'uucp' group to access Pico in BOOTSEL mode."
    print_info "Try: sudo usermod -a -G uucp $USER (then log out and back in)"
    print_info "Or install udev rules: sudo ./scripts/install_picotool_udev_rules.sh"
    print_info ""
    print_info "Last resort: sudo $0"
    
    exit 1
fi

# Check for no device found
if echo "$output" | grep -qi "No accessible RP-series devices in BOOTSEL mode were found"; then
    print_error "No device found in BOOTSEL mode"
    print_info ""
    print_info "To enter BOOTSEL mode:"
    print_info "  1. Unplug the Pico"
    print_info "  2. Press and hold the BOOTSEL button (white button)"
    print_info "  3. While holding BOOTSEL, plug in USB"
    print_info "  4. Release BOOTSEL button"
    print_info "  5. Device should appear as mass storage device"
    print_info ""
    print_info "Then run this script again."
    exit 1
fi

print_success "Device found in BOOTSEL mode and accessible"

# File details
FILE_NAME="RPI_PICO2_W-20250415-v1.25.0.uf2"
BASE_URL="https://micropython.org/resources/firmware"
FILE_URL="$BASE_URL/$FILE_NAME"

print_info "Erasing flash with picotool..."
if ! "$PICOTOOL_PATH" erase; then
    print_error "Failed to erase flash"
    exit 1
fi

print_info "Downloading MicroPython firmware..."
if ! curl --progress-bar --output "$FILE_NAME" "$FILE_URL"; then
    print_error "Failed to download firmware"
    exit 1
fi

print_info "Loading firmware onto device..."
if ! "$PICOTOOL_PATH" load -v -x "$FILE_NAME" -f; then
    print_error "Failed to load firmware"
    print_info "Cleaning up downloaded file..."
    rm -f "$FILE_NAME"
    exit 1
fi

print_info "Cleaning up..."
rm -f "$FILE_NAME"

print_success "Factory reset completed successfully!"
print_info "The device will reboot automatically."
print_info ""
print_info "After reboot, the Pico will be in normal mode (not BOOTSEL)."
print_info ""
print_info "Next steps:"
print_info "  1. Install MicroPython dependencies: ./scripts/install_pico_deps.sh"
print_info "  2. Deploy code to device: ./scripts/run_on_device.sh"
print_info ""
print_info "Note: The dependencies (datetime, ntptime, umqtt.simple, ADS1x15 driver)"
print_info "must be installed before the irrigation system will work correctly."
