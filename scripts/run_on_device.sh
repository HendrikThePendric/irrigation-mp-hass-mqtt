#!/bin/bash

# Script to deploy code to MicroPython device and start serial monitor
# Usage: ./scripts/run_on_device.sh

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "$SCRIPT_DIR/common.sh"

# Setup environment (activates venv, checks project root)
setup_environment

print_info "Starting deployment to MicroPython device..."

# Check if device is connected
verify_device_connected

# Get paths to mpremote and mpr
MPREMOTE="$(get_mpremote_path)"
MPR="$(get_mpr_path)"

# Check required files and directories
print_info "Checking required files..."
if [[ ! -d "src" ]]; then
    print_error "src/ directory not found"
    exit 1
fi

if [[ ! -f "config.json" ]]; then
    print_error "config.json not found"
    print_info "Create config.json from config.template.json"
    exit 1
fi

if [[ ! -d "certs" ]]; then
    print_warning "certs/ directory not found"
    print_info "MQTT TLS certificates are required for secure connection"
    print_info "Create certs/ directory and add certificate files:"
    print_info "  - ca_crt.der"
    print_info "  - irrigationbackyard_crt.der"
    print_info "  - irrigationbackyard_key.der"
    print_info "Continue without certificates? (MQTT connection will fail)"
    # Ask user to continue? For now, just warn but continue
    print_warning "Deploying without certificates - MQTT will fail"
fi

print_info "Deploying source files..."
if ! "$MPR" put -r -F src/* config.json certs/* /; then
    print_error "Failed to deploy files"
    print_info "Make sure:"
    print_info "  1. Device is connected and accessible"
    print_info "  2. Files exist (src/, config.json, certs/)"
    exit 1
fi

print_success "Files deployed successfully"

print_info "Rebooting device..."
if ! "$MPR" reboot; then
    print_warning "Reboot command failed (device may have disconnected)"
fi

print_info "Waiting for device to restart..."
sleep 2

print_info "Starting serial monitor (press Ctrl+X to exit)..."
"$MPREMOTE"
