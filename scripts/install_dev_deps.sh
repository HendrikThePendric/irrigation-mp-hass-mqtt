#!/bin/bash

# Quick and dirty way to ensure the script is being executed from the root dir
SCRIPTS_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
cd "$SCRIPTS_DIR" || return
cd ..

pip install -r requirements.txt
pip install -U micropython-rp2-pico_w-stubs --target typings --no-user --no-cache-dir

# Manually get typings for umqtt.simple because this is not included in the
# micropython-rp2-pico_w-stubs stubs. See this discussion for details:
# https://github.com/Josverl/micropython-stubs/discussions/821
mkdir typings/umqtt
curl -H 'Accept: application/vnd.github.v3.raw' -O -L \
  --output-dir typings/umqtt \
  https://api.github.com/repos/Josverl/micropython-stubs/contents/stubs/micropython-v1_25_0-frozen/esp32/GENERIC/umqtt/simple.pyi
