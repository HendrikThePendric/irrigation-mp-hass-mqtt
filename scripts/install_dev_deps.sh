#!/bin/bash

# Install development dependencies for irrigation-mp-hass-mqtt project
# Usage: ./scripts/install_dev_deps.sh

set -e

# Quick and dirty way to ensure the script is being executed from the root dir
SCRIPTS_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
cd "$SCRIPTS_DIR" || exit 1
cd ..

PROJECT_ROOT=$(pwd)
VENV_DIR="$PROJECT_ROOT/.venv"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment"
        echo "Make sure python3-venv is installed:"
        echo "  Ubuntu/Debian: sudo apt install python3-venv"
        echo "  Arch Linux: sudo pacman -S python-venv"
        echo "  macOS: python3 should include venv by default"
        exit 1
    fi
    echo "Virtual environment created successfully"
fi

VENV_PIP="$VENV_DIR/bin/pip"
VENV_PYTHON="$VENV_DIR/bin/python"

echo "Using virtual environment Python: $VENV_PYTHON"

# Install requirements
echo "Installing requirements from requirements.txt..."
"$VENV_PIP" install -r requirements.txt

# Install type stubs
echo "Installing MicroPython type stubs..."
"$VENV_PIP" install -U micropython-rp2-pico_w-stubs --target typings --no-user --no-cache-dir

# Manually get typings for umqtt.simple because this is not included in the
# micropython-rp2-pico_w-stubs stubs. See this discussion for details:
# https://github.com/Josverl/micropython-stubs/discussions/821
mkdir -p typings/umqtt
curl -H 'Accept: application/vnd.github.v3.raw' -O -L \
  --output-dir typings/umqtt \
  https://api.github.com/repos/Josverl/micropython-stubs/contents/stubs/micropython-v1_25_0-frozen/esp32/GENERIC/umqtt/simple.pyi

# Install picotool if not already installed
if ! ./scripts/install_picotools.sh; then
    echo "Warning: picotool installation failed. Factory reset script may not work."
fi

echo ""
echo "Development dependencies installed successfully!"
echo ""
echo "To use mpremote and mpr, activate the virtual environment:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "Or use the helper script:"
echo "  source ./scripts/activate_venv.sh"
echo ""
echo "After activation, verify with:"
echo "  mpremote --version"
echo "  mpr --version"