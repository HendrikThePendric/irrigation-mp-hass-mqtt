#!/bin/bash

# Common functions and setup for irrigation-mp-hass-mqtt scripts
# Source this script in other bash scripts to get common functionality

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_error() {
    echo -e "${RED}❌ Error: $1${NC}" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠️  Warning: $1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "ℹ️  $1"
}

# Function to find project root
find_project_root() {
    local current_dir
    current_dir="$(pwd)"
    
    # Walk up the directory tree looking for scripts directory
    while [[ "$current_dir" != "/" ]]; do
        if [[ -d "$current_dir/scripts" ]]; then
            echo "$current_dir"
            return 0
        fi
        current_dir="$(dirname "$current_dir")"
    done
    
    print_error "Could not find project root directory"
    print_error "Make sure you're in the irrigation-mp-hass-mqtt project directory"
    return 1
}

# Function to activate virtual environment
activate_venv() {
    local project_root
    project_root="$(find_project_root)"
    local venv_dir="$project_root/.venv"
    
    if [[ ! -d "$venv_dir" ]]; then
        print_error "Virtual environment not found at $venv_dir"
        print_error "Run ./scripts/install_dev_deps.sh first to create the virtual environment"
        return 1
    fi
    
    if [[ ! -f "$venv_dir/bin/activate" ]]; then
        print_error "Virtual environment activation script not found"
        print_error "The virtual environment may be corrupted. Try deleting .venv and running install_dev_deps.sh again"
        return 1
    fi
    
    print_info "Activating virtual environment in $venv_dir"
    
    # shellcheck source=/dev/null
    source "$venv_dir/bin/activate"
    
    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        print_error "Failed to activate virtual environment"
        return 1
    fi
    
    print_success "Virtual environment activated"
    return 0
}

# Function to get the path to mpremote executable
get_mpremote_path() {
    if command -v mpremote >/dev/null 2>&1; then
        command -v mpremote
    else
        print_error "mpremote not found in PATH"
        print_error "Make sure virtual environment is activated"
        return 1
    fi
}

# Function to get the path to mpr executable
get_mpr_path() {
    if command -v mpr >/dev/null 2>&1; then
        command -v mpr
    else
        print_error "mpr not found in PATH"
        print_error "Make sure virtual environment is activated"
        return 1
    fi
}

# Function to get the path to picotool executable
get_picotool_path() {
    if command -v picotool >/dev/null 2>&1; then
        command -v picotool
    else
        print_error "picotool not found in PATH"
        print_error "Install it with: ./scripts/install_picotools.sh"
        return 1
    fi
}

# Simple check if device is connected and responsive
verify_device_connected() {
    print_info "Checking for connected MicroPython device..."
    
    MPREMOTE="$(get_mpremote_path)"
    
    local output
    output=$("$MPREMOTE" eval "1+1" 2>&1 || true)
    
    if echo "$output" | grep -q "^2$"; then
        print_success "Device found and responsive"
        return 0
    fi
    
    print_error "No MicroPython device found or device not responding"
    print_info "Make sure:"
    print_info "  - Pico is connected via USB"
    print_info "  - Device is not in BOOTSEL mode (flashing mode)"
    print_info "  - You have serial port permissions (may need to be in uucp group)"
    return 1
}

# Check if device is in BOOTSEL mode (flashing mode)
check_bootsel_mode() {
    if ! command -v picotool >/dev/null 2>&1; then
        print_warning "picotool not found, cannot check BOOTSEL mode"
        print_info "Assuming device is not in BOOTSEL mode"
        return 0
    fi
    
    local output
    output=$(picotool info 2>&1 || true)
    
    if echo "$output" | grep -qi "appears to be in BOOTSEL mode"; then
        print_error "Device is in BOOTSEL mode (flashing mode)"
        print_info "To use mpremote, exit BOOTSEL mode:"
        print_info "  1. Unplug the Pico"
        print_info "  2. Ensure BOOTSEL button is NOT pressed"
        print_info "  3. Replug USB"
        return 1
    fi
    
    print_success "Device is not in BOOTSEL mode"
    return 0
}

# Main setup function to be called by scripts
setup_environment() {
    print_info "Setting up environment..."
    
    # Find project root and set it
    PROJECT_ROOT="$(find_project_root)"
    export PROJECT_ROOT
    
    # Change to project root
    cd "$PROJECT_ROOT" || {
        print_error "Failed to change to project root: $PROJECT_ROOT"
        return 1
    }
    
    # Activate virtual environment
    activate_venv
    
    print_success "Environment setup complete"
    return 0
}

# If script is being run directly (not sourced), run setup_environment
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    setup_environment
fi