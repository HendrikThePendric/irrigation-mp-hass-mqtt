#!/bin/bash

# Quick and dirty way to ensure the script is being executed from the root dir
SCRIPTS_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
cd "$SCRIPTS_DIR" || exit 1
cd .. || exit 1

PROJECT_ROOT=$(pwd)

# Version of picotool to install (release tag from https://github.com/raspberrypi/pico-sdk-tools/releases)
PICOTOOL_VERSION="v2.2.0-3"

# Check for required commands
for cmd in curl mktemp; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: $cmd is required but not installed."
        exit 1
    fi
done

echo "Installing picotool..."

# Check if picotool already installed
if command -v picotool >/dev/null 2>&1; then
    echo "picotool is already installed."
    exit 0
fi

echo "picotool not found. Installing from pre-built binaries..."

# Detect OS and architecture
arch=$(uname -m)
os_type=""
platform=""
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    platform="linux"
    if [[ -f /etc/os-release ]]; then
        os_type=$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
    else
        os_type="linux"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    platform="macos"
    os_type="macos"
else
    platform="unknown"
    os_type="unknown"
fi

echo "Detected OS: $os_type, architecture: $arch"

# Determine appropriate binary URL
# Note: Filenames may change with new releases; check GitHub releases page
asset_url=""
asset_name=""
extract_cmd=""
binary_path=""

if [[ "$platform" == "linux" && "$arch" == "x86_64" ]]; then
    asset_url="https://github.com/raspberrypi/pico-sdk-tools/releases/download/${PICOTOOL_VERSION}/picotool-2.2.0-a4-x86_64-lin.tar.gz"
    asset_name="picotool-2.2.0-a4-x86_64-lin.tar.gz"
    extract_cmd="tar xzf"
    binary_path="picotool/picotool"
elif [[ "$platform" == "linux" && "$arch" == "aarch64" ]]; then
    asset_url="https://github.com/raspberrypi/pico-sdk-tools/releases/download/${PICOTOOL_VERSION}/picotool-2.2.0-a4-aarch64-lin.tar.gz"
    asset_name="picotool-2.2.0-a4-aarch64-lin.tar.gz"
    extract_cmd="tar xzf"
    binary_path="picotool/picotool"
elif [[ "$platform" == "macos" ]]; then
    asset_url="https://github.com/raspberrypi/pico-sdk-tools/releases/download/${PICOTOOL_VERSION}/picotool-2.2.0-a4-mac.zip"
    asset_name="picotool-2.2.0-a4-mac.zip"
    extract_cmd="unzip -q"
    binary_path="picotool/picotool"
else
    echo "Error: No pre-built binary available for $os_type $arch"
    echo "Please install picotool manually from: https://github.com/raspberrypi/picotool"
    exit 1
fi

# Create temporary directory
temp_dir=$(mktemp -d)
cd "$temp_dir" || exit 1

echo "Downloading pre-built picotool: $asset_name"
if ! curl -L -s -o "$asset_name" "$asset_url"; then
    echo "Error: Failed to download binary"
    cd "$PROJECT_ROOT"
    rm -rf "$temp_dir"
    exit 1
fi

echo "Extracting..."
if ! $extract_cmd "$asset_name"; then
    echo "Error: Failed to extract archive"
    cd "$PROJECT_ROOT"
    rm -rf "$temp_dir"
    exit 1
fi

# Find the picotool binary
found_binary=""
if [[ -f "$binary_path" ]]; then
    found_binary="$binary_path"
else
    # Search for picotool in extracted files
    found_binary=$(find . -name "picotool" -type f -executable 2>/dev/null | head -1)
fi

if [[ -z "$found_binary" || ! -f "$found_binary" ]]; then
    echo "Error: Could not find picotool binary in archive"
    cd "$PROJECT_ROOT"
    rm -rf "$temp_dir"
    exit 1
fi

echo "Installing picotool binary..."
chmod +x "$found_binary"

# Install to appropriate location
if command -v sudo >/dev/null 2>&1 && sudo -v >/dev/null 2>&1; then
    echo "Installing to /usr/local/bin..."
    if sudo cp "$found_binary" /usr/local/bin/picotool; then
        echo "picotool installed successfully to /usr/local/bin"
    else
        echo "Failed to install to /usr/local/bin, trying ~/.local/bin..."
        mkdir -p ~/.local/bin
        cp "$found_binary" ~/.local/bin/picotool
        echo "picotool installed to ~/.local/bin"
        echo "Add ~/.local/bin to your PATH if not already"
    fi
else
    echo "Installing to ~/.local/bin (sudo not available)..."
    mkdir -p ~/.local/bin
    cp "$found_binary" ~/.local/bin/picotool
    echo "picotool installed to ~/.local/bin"
    echo "Add ~/.local/bin to your PATH if not already"
fi

# Clean up
cd "$PROJECT_ROOT"
rm -rf "$temp_dir"

# Verify installation
if command -v picotool >/dev/null 2>&1; then
    echo "picotool installation verified."
    
    # Test if picotool works without sudo
    echo "Testing picotool permissions..."
    if picotool --help >/dev/null 2>&1; then
        echo "picotool works correctly."
    else
        echo "Warning: picotool may have permission issues."
        echo "You might need to use 'sudo picotool' or install udev rules."
    fi
    
    # Linux udev rules suggestion
    if [[ "$platform" == "linux" ]]; then
        echo ""
        echo "IMPORTANT: To use picotool without sudo, install udev rules:"
        echo "  sudo ./scripts/install_picotool_udev_rules.sh"
        echo ""
        echo "Or manually:"
        echo "  curl -L -o /tmp/60-picotool.rules \\"
        echo "    https://raw.githubusercontent.com/raspberrypi/picotool/master/udev/60-picotool.rules"
        echo "  sudo cp /tmp/60-picotool.rules /etc/udev/rules.d/"
        echo "  sudo udevadm control --reload"
        echo "  sudo udevadm trigger"
        echo ""
        echo "After installing rules, unplug and replug your Pico device."
    fi
    exit 0
else
    echo "Error: picotool installation failed."
    echo "If picotool is in ~/.local/bin, ensure it's in your PATH."
    exit 1
fi