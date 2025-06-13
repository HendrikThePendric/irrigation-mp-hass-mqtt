#!/bin/bash

set -e

# Run from this dir
SCRIPTS_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
cd "$SCRIPTS_DIR" || return

# BEFORE RUNNING THIS ENSURE THE DEVICE IS IN BOOTSEL MODE
FILE_NAME="RPI_PICO2_W-20250415-v1.25.0.uf2"
BASE_URL="https://micropython.org/resources/firmware"
FILE_URL="$BASE_URL/$FILE_NAME"

picotool erase
curl --output $FILE_NAME $FILE_URL
picotool load -v -x $FILE_NAME -f
rm $FILE_NAME
