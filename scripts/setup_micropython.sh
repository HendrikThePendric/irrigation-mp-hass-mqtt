#!/bin/bash

# Setup script for MicroPython UNIX port installation
# Run this from the project root directory

set -e  # Exit on error

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MICROPYTHON_BUILD_DIR="$PROJECT_ROOT/micropython-build"
MICROPYTHON_BINARY="$MICROPYTHON_BUILD_DIR/micropython/ports/unix/build-standard/micropython"
LOCAL_SYMLINK="$PROJECT_ROOT/micropython-local"

echo "=== Setting up MicroPython UNIX port ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# Check if already installed
if [ -f "$MICROPYTHON_BINARY" ] && [ -x "$MICROPYTHON_BINARY" ]; then
    echo "✓ MicroPython binary already exists at: $MICROPYTHON_BINARY"
    echo "  Testing..."
    "$MICROPYTHON_BINARY" -c "print('MicroPython is working!')"
    echo ""
    
    # Create/update symlink
    ln -sf "$MICROPYTHON_BINARY" "$LOCAL_SYMLINK"
    echo "✓ Created symlink: $LOCAL_SYMLINK -> $MICROPYTHON_BINARY"
    echo ""
    echo "Setup complete! You can now run tests with:"
    echo "  python3 tests/run_tests.py"
    exit 0
fi

echo "MicroPython not found. Building from source..."
echo ""

# Check for build dependencies
echo "Checking build dependencies..."
if ! command -v gcc &> /dev/null; then
    echo "❌ gcc not found. Please install build dependencies:"
    echo "  sudo pacman -S --needed base-devel git python python-pip pkg-config"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "❌ git not found. Please install git."
    exit 1
fi

echo "✓ Build dependencies available"
echo ""

# Create build directory
mkdir -p "$MICROPYTHON_BUILD_DIR"
cd "$MICROPYTHON_BUILD_DIR"

# Clone MicroPython if not already cloned
if [ ! -d "micropython" ]; then
    echo "Cloning MicroPython repository..."
    git clone https://github.com/micropython/micropython.git
else
    echo "✓ MicroPython repository already cloned"
fi

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
    ./build-standard/micropython -c "print('MicroPython build successful!')"
    echo "✓ MicroPython binary is working"
else
    echo "❌ Error: MicroPython binary not found at expected location"
    echo "  Expected: build-standard/micropython"
    exit 1
fi

# Return to project root
cd "$PROJECT_ROOT"

# Create symlink
ln -sf "$MICROPYTHON_BINARY" "$LOCAL_SYMLINK"
echo "✓ Created symlink: $LOCAL_SYMLINK -> $MICROPYTHON_BINARY"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "You can now run tests using:"
echo "  python3 tests/run_tests.py"
echo ""
echo "Or run individual tests with:"
echo "  ./micropython-local tests/unit/test_rolling_average.py"
echo ""
echo "To clean up the build directory:"
echo "  rm -rf micropython-build/"