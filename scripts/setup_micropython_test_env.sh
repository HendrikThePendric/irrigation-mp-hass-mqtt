#!/bin/bash

# Setup script for MicroPython test environment (UNIX port)
# Installs MicroPython and required packages for testing
# Run this from the project root directory

set -e  # Exit on error

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MICROPYTHON_BUILD_DIR="$PROJECT_ROOT/micropython-build"
MICROPYTHON_BINARY="$MICROPYTHON_BUILD_DIR/micropython/ports/unix/build-standard/micropython"
LOCAL_SYMLINK="$PROJECT_ROOT/micropython-local"

echo "=== Setting up MicroPython UNIX port ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# Check for build dependencies at the start
echo "Checking build dependencies..."
MISSING_DEPS=0

if ! command -v gcc &> /dev/null; then
    echo "❌ gcc not found"
    MISSING_DEPS=1
fi

if ! command -v git &> /dev/null; then
    echo "❌ git not found"
    MISSING_DEPS=1
fi

if [ $MISSING_DEPS -eq 1 ]; then
    echo ""
    echo "Please install missing dependencies:"
    echo ""
    echo "Ubuntu/Debian:"
    echo "  sudo apt update"
    echo "  sudo apt install -y build-essential git python3 python3-pip python3-venv pkg-config"
    echo ""
    echo "Arch Linux:"
    echo "  sudo pacman -S --needed base-devel git python python-pip python-venv pkg-config"
    echo ""
    echo "macOS (with Homebrew):"
    echo "  brew install python3 git pkg-config"
    exit 1
fi

echo "✓ Build dependencies available"
echo ""

# Test if existing MicroPython works (not just file existence)
BUILD_NEEDED=true
if [ -f "$MICROPYTHON_BINARY" ] && [ -x "$MICROPYTHON_BINARY" ]; then
    echo "MicroPython binary exists at: $MICROPYTHON_BINARY"
    echo "Testing if it works..."
    
    if "$MICROPYTHON_BINARY" -c "print('MicroPython test successful')" 2>&1 | grep -q "MicroPython test successful"; then
        echo "✓ MicroPython is working"
        BUILD_NEEDED=false
    else
        echo "❌ MicroPython exists but doesn't work, cleaning up..."
        rm -rf "$MICROPYTHON_BUILD_DIR"
        BUILD_NEEDED=true
    fi
    echo ""
fi

# Build MicroPython if needed
if [ "$BUILD_NEEDED" = true ]; then
    echo "Building MicroPython from source..."
    echo ""
    
    # Clean up any previous failed build
    if [ -d "$MICROPYTHON_BUILD_DIR" ]; then
        echo "Cleaning up previous build directory..."
        rm -rf "$MICROPYTHON_BUILD_DIR"
    fi
    
    # Create build directory
    mkdir -p "$MICROPYTHON_BUILD_DIR"
    cd "$MICROPYTHON_BUILD_DIR"
    
    # Clone MicroPython
    echo "Cloning MicroPython repository..."
    git clone https://github.com/micropython/micropython.git
    
    cd micropython
    
    # Build mpy-cross
    echo "Building mpy-cross..."
    cd mpy-cross
    make -j$(nproc)
    echo "✓ mpy-cross built successfully"
    cd ..
    
    # Build Unix port
    echo "Building Unix port..."
    cd ports/unix
    make submodules
    make -j$(nproc)
    echo "✓ Unix port built successfully"
    
    # Verify build
    if [ -f "build-standard/micropython" ]; then
        echo "Testing MicroPython binary..."
        if ./build-standard/micropython -c "print('MicroPython build successful!')" 2>&1 | grep -q "MicroPython build successful"; then
            echo "✓ MicroPython binary is working"
        else
            echo "❌ Error: MicroPython binary exists but doesn't work"
            echo ""
            echo "Cleaning up failed build..."
            cd "$PROJECT_ROOT"
            rm -rf "$MICROPYTHON_BUILD_DIR"
            exit 1
        fi
    else
        echo "❌ Error: MicroPython binary not found at expected location"
        echo "  Expected: build-standard/micropython"
        echo ""
        echo "Cleaning up failed build..."
        cd "$PROJECT_ROOT"
        rm -rf "$MICROPYTHON_BUILD_DIR"
        exit 1
    fi
    
    # Return to project root
    cd "$PROJECT_ROOT"
fi

# Create/update symlink
ln -sf "$MICROPYTHON_BINARY" "$LOCAL_SYMLINK"
echo "✓ Created symlink: $LOCAL_SYMLINK -> $MICROPYTHON_BINARY"
echo ""

# Install required packages via mip
echo "Installing required packages..."
PACKAGES=("unittest" "collections" "datetime" "typing")

for pkg in "${PACKAGES[@]}"; do
    echo "  Installing $pkg..."
    # Run mip.install and capture output
    INSTALL_OUTPUT=$("$MICROPYTHON_BINARY" -c "import mip; mip.install('$pkg')" 2>&1)
    
    # Check for success indicators in output
    if echo "$INSTALL_OUTPUT" | grep -q "Exists\|Done\|Package may be partially installed"; then
        echo "  ✓ $pkg installed/available"
    else
        echo "❌ Failed to install $pkg"
        echo "  Output: $INSTALL_OUTPUT"
        exit 1
    fi
done
echo ""

# Validate all packages import successfully
echo "Validating package imports..."
VALIDATION_SCRIPT="
import sys
errors = []
for pkg in ['unittest', 'collections', 'datetime', 'typing']:
    try:
        __import__(pkg)
        print(f'✓ {pkg} importable')
    except ImportError as e:
        errors.append(f'{pkg}: {e}')

if errors:
    print('❌ Package import validation failed:')
    for error in errors:
        print(f'  - {error}')
    sys.exit(1)
"

if ! "$MICROPYTHON_BINARY" -c "$VALIDATION_SCRIPT"; then
    echo "❌ Package validation failed"
    exit 1
fi

echo ""
echo "=== MicroPython setup complete ==="
echo "✓ MicroPython binary: $MICROPYTHON_BINARY"
echo "✓ Symlink: $LOCAL_SYMLINK"
echo "✓ Packages installed: unittest, collections, datetime, typing"
echo "✓ All packages validated"