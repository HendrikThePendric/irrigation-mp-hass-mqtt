# Irrigation MicroPython HomeAssistant MQTT

This repo contains both the code and the assembly instructions for an irrigation system.

## Quick Start

```bash
# Install development dependencies and type stubs
./scripts/install_dev_deps.sh

# Setup MicroPython test environment (includes unittest framework)
./scripts/setup_micropython_test_env.sh

# Run tests
python3 tests/run_tests.py
```

The setup automatically:
1. Installs Python dev dependencies and type stubs
2. Builds MicroPython from source (if needed)
3. Installs unittest framework and other required packages into MicroPython

## Project Overview

This is an irrigation system built on Raspberry Pi Pico with MicroPython. Key components:

- **Microcontroller**: Raspberry Pi Pico W (RP2040)
- **Sensors**: Soil moisture sensors via ADS1115 ADC modules (I2C)
- **Actuators**: Relays for valve control
- **Communication**: MQTT over TLS for Home Assistant integration
- **Power**: 12V DC to 5V USB step-down converter, 220V AC input

The system monitors soil moisture and controls irrigation valves based on configurable thresholds, with automatic discovery in Home Assistant via MQTT.
