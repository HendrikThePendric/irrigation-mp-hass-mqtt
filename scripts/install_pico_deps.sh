#!/bin/bash

# Script to install MicroPython dependencies on the Pico device
# Usage: ./scripts/install_pico_deps.sh

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "$SCRIPT_DIR/common.sh"

# Setup environment (activates venv, checks project root)
setup_environment

print_info "Installing MicroPython dependencies on device..."

# Check if device is connected
verify_device_connected

# Get path to mpremote
MPREMOTE="$(get_mpremote_path)"

# Install required packages
print_info "Installing datetime..."
"$MPREMOTE" mip install datetime

print_info "Installing ntptime..."
"$MPREMOTE" mip install ntptime

print_info "Installing typing stubs..."
"$MPREMOTE" mip install github:josverl/micropython-stubs/mip/typing.mpy

print_info "Installing umqtt.simple..."
"$MPREMOTE" mip install umqtt.simple

print_info "Installing ADS1x15 driver..."
"$MPREMOTE" mip install github:robert-hh/ads1x15

print_success "All dependencies installed successfully!"

