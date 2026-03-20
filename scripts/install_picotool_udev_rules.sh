#!/bin/bash

# Install udev rules for picotool to allow non-root access to Pico devices

set -e

echo "Installing udev rules for picotool..."

# Check if running as root or with sudo
if [[ "$EUID" -ne 0 ]]; then
    echo "This script needs root privileges to install udev rules."
    echo "Please run with sudo:"
    echo "  sudo $0"
    exit 1
fi

RULES_URL="https://raw.githubusercontent.com/raspberrypi/picotool/master/udev/60-picotool.rules"
RULES_FILE="/etc/udev/rules.d/60-picotool.rules"

echo "Downloading udev rules from $RULES_URL..."
if ! curl -L -s -o "$RULES_FILE" "$RULES_URL"; then
    echo "Error: Failed to download udev rules"
    exit 1
fi

# Modify rules to use uucp group instead of plugdev (better for Arch Linux)
sed -i 's/GROUP="plugdev"/GROUP="uucp"/g' "$RULES_FILE" 2>/dev/null || true

# Check if user is in uucp group
CURRENT_USER="${SUDO_USER:-$USER}"
if ! groups "$CURRENT_USER" | grep -q '\buucp\b'; then
    echo "Adding user '$CURRENT_USER' to 'uucp' group..."
    if usermod -a -G uucp "$CURRENT_USER" 2>/dev/null; then
        echo "User added to uucp group. Log out and back in for changes to take effect."
    else
        echo "Warning: Could not add user to uucp group."
        echo "You may need to manually run: sudo usermod -a -G uucp $CURRENT_USER"
    fi
fi

echo "Udev rules installed to $RULES_FILE"
echo "Reloading udev rules..."
udevadm control --reload
udevadm trigger

echo ""
echo "Udev rules installed successfully!"
echo "You may need to unplug and replug your Pico device for changes to take effect."
echo ""
echo "To verify, run:"
echo "  picotool info"
echo "Without sudo, you should see:"
echo "  No accessible RP-series devices in BOOTSEL mode were found."
echo "(which is normal when no device is connected or in BOOTSEL mode)"