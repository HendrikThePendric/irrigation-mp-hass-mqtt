#!/bin/bash

# Script to activate the project's virtual environment
# Usage: source ./scripts/activate_venv.sh

# Find the project root by looking for the scripts directory
# This works whether the script is sourced from project root or elsewhere
if [ -d "scripts" ]; then
    # Already in project root
    PROJECT_ROOT="$(pwd)"
elif [ -f "activate_venv.sh" ]; then
    # In scripts directory
    PROJECT_ROOT="$(cd .. && pwd)"
else
    # Try to find project root by looking for scripts/ directory
    # Walk up the directory tree
    CURRENT_DIR="$(pwd)"
    while [ "$CURRENT_DIR" != "/" ]; do
        if [ -d "$CURRENT_DIR/scripts" ]; then
            PROJECT_ROOT="$CURRENT_DIR"
            break
        fi
        CURRENT_DIR="$(dirname "$CURRENT_DIR")"
    done
    
    if [ -z "$PROJECT_ROOT" ]; then
        echo "Error: Could not find project root directory"
        echo "Make sure you're in the irrigation-mp-hass-mqtt project directory"
        return 1 2>/dev/null || exit 1
    fi
fi

VENV_DIR="$PROJECT_ROOT/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Virtual environment not found at $VENV_DIR"
    echo "Run ./scripts/install_dev_deps.sh first to create the virtual environment"
    return 1 2>/dev/null || exit 1
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Error: Virtual environment activation script not found"
    echo "The virtual environment may be corrupted. Try deleting .venv and running install_dev_deps.sh again"
    return 1 2>/dev/null || exit 1
fi

echo "Activating virtual environment in $VENV_DIR"
source "$VENV_DIR/bin/activate"

# Verify activation
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: Failed to activate virtual environment"
    return 1 2>/dev/null || exit 1
fi

echo "Virtual environment activated successfully"
echo "Python: $(which python)"
echo "Pip: $(which pip)"