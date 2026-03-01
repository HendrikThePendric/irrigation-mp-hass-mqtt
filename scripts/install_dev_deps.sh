#!/bin/bash

# Quick and dirty way to ensure the script is being executed from the root dir
SCRIPTS_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
cd "$SCRIPTS_DIR" || return
cd ..

PROJECT_ROOT=$(pwd)
VENV_DIR="$PROJECT_ROOT/.venv"

# Function to create virtual environment if it doesn't exist
create_venv_if_needed() {
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
}

# Function to get the venv pip path
get_venv_pip() {
    echo "$VENV_DIR/bin/pip"
}

# Function to get the venv python path
get_venv_python() {
    echo "$VENV_DIR/bin/python"
}

# Create virtual environment if needed
create_venv_if_needed

VENV_PIP=$(get_venv_pip)
VENV_PYTHON=$(get_venv_python)

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

echo ""
echo "Development dependencies installed successfully!"
echo ""
echo "To activate the virtual environment:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "Or use the helper script:"
echo "  source ./scripts/activate_venv.sh"
