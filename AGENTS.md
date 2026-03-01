# AGENTS.md - Irrigation MicroPython HomeAssistant MQTT Project Guide

This document provides guidelines for AI agents working on the irrigation-mp-hass-mqtt project. It covers project-specific conventions, development workflow, testing, and deployment.

## Project Overview

This is an irrigation system built on Raspberry Pi Pico with MicroPython. Key components:

- **Microcontroller**: Raspberry Pi Pico W (RP2040)
- **Sensors**: Soil moisture sensors via ADS1115 ADC modules (I2C)
- **Actuators**: MOSFET switches for sensor power control, relays for valve control
- **Communication**: MQTT over TLS for Home Assistant integration
- **Power**: 12V DC to 5V USB step-down converter, 220V AC input

The system monitors soil moisture and controls irrigation valves based on configurable thresholds, with automatic discovery in Home Assistant via MQTT.

## Development Environment

### Prerequisites
- Python 3.9+ with pip and venv module
- `mpremote` and `mpr` tools (installed via requirements.txt)
- MicroPython firmware on Pico W
- Physical hardware setup (see `docs/assembly.md`)

**Platform-specific notes:**
- **Ubuntu/Debian**: `sudo apt install python3-venv`
- **Arch Linux**: `sudo pacman -S python-venv`
- **macOS**: venv is included by default with Python 3

### Setup Commands
```bash
# Install development dependencies (type stubs, etc.) into virtual environment
./scripts/install_dev_deps.sh

# Activate the virtual environment for development
source ./scripts/activate_venv.sh

# Install MicroPython dependencies on the device
./scripts/install_pico_deps.sh
```

### Project Structure
```
irrigation-mp-hass-mqtt/
├── src/                    # Main application source code
│   ├── main.py            # Entry point
│   ├── config.py          # Configuration parsing and validation
│   ├── irrigation_station.py # Core irrigation logic
│   ├── irrigation_point.py # Individual irrigation point management
│   ├── sensor.py          # Soil moisture sensor handling
│   ├── valve.py           # Valve control
│   ├── mqtt_robust_client.py # MQTT client with reconnection
│   ├── mqtt_hass_manager.py # Home Assistant MQTT integration
│   ├── mqtt_hass_entities.py # HA entity definitions
│   ├── wifi_manager.py    # WiFi connection management
│   ├── time_keeper.py     # NTP time synchronization
│   ├── watchdog.py        # System watchdog
│   ├── logger.py          # Logging utilities
│   ├── rolling_average.py # Signal smoothing algorithms
│   └── hardware_tests/    # Hardware validation scripts
├── scripts/               # Development and deployment scripts
├── docs/                  # Documentation
├── typings/               # MicroPython type stubs
├── config.template.json   # Configuration template
└── requirements.txt       # Python dependencies
```

## Code Conventions

### Language & Type Hints
- Use **MicroPython-compatible Python** (subset of Python 3.4+)
- **Type hints are required** for function signatures and class attributes
- Use `# type: ignore` only when necessary (e.g., MicroPython-specific imports)
- Import order: built-in, third-party, local modules (grouped with blank lines)

### Naming
- **Classes**: `PascalCase`
- **Functions/Methods**: `snake_case`
- **Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: prefix with underscore `_`
- **File names**: `snake_case.py`

### Documentation
- Document public APIs with docstrings (triple-quoted strings)
- Keep comments minimal; prefer self-documenting code
- Update documentation when changing behavior

### MicroPython-Specific Considerations
- **Memory is limited**: Avoid large data structures, recursion, or excessive string operations
- **Use `gc.collect()`** periodically in long-running loops (see `main.py:56`)
- **Hardware access**: Use `machine` module for GPIO, I2C, etc.
- **Exception handling**: Catch specific exceptions; log errors before resetting
- **No dynamic imports**: All imports must be at module level

## Configuration Management

### Configuration File
- Uses `config.json` (not tracked in git)
- Template: `config.template.json`
- Validated at startup by `Config` class

### Configuration Structure
```json
{
  "station_name": "Backyard irrigation station",
  "network": {
    "wifi_ssid": "...",
    "wifi_password": "...",
    "mqtt_broker_ip": "..."
  },
  "rolling_window": 3,
  "ema_alpha": 0.2,
  "publish_interval_minutes": 5,
  "irrigation_points": [
    {
      "name": "Location A",
      "valve_pin": 2,
      "mosfet_pin": 21,
      "ads_address": "0x48",
      "ads_channel": 0
    }
  ]
}
```

### Security Notes
- **Never commit** `config.json` or certificate files (`certs/`)
- Use environment variables for secrets in development (not implemented yet)
- TLS certificates are required for MQTT connection

## Testing

### Hardware Tests
Located in `src/hardware_tests/`:
- `sensor_test.py`: Test MOSFET switches and ADS1115 sensor readings
- `valve_test.py`: Test relay valve controls

**Usage**:
```bash
mpremote run src/hardware_tests/sensor_test.py
mpremote run src/hardware_tests/valve_test.py
```

### Software Testing
- No formal unit test framework due to MicroPython constraints
- Test by running on actual hardware
- Use `mpremote` for rapid iteration

### Validation Steps
1. Run hardware tests to verify connections
2. Deploy config and certificates
3. Monitor serial output for errors
4. Check Home Assistant MQTT discovery

## Development Workflow

### Local Development
1. **Edit code** in `src/`
2. **Run type checking** (optional): `pyright src/`
3. **Deploy to device**: `./scripts/run_on_device.sh`
   - Copies `src/`, `config.json`, and `certs/` to Pico
   - Reboots device
   - Opens serial monitor
4. **Monitor output** via serial connection

### Common Commands
```bash
# Install dependencies
./scripts/install_dev_deps.sh
./scripts/install_pico_deps.sh

# Activate virtual environment for development
source ./scripts/activate_venv.sh

# Deploy and run
./scripts/run_on_device.sh

# Manual file transfer
mpremote cp src/main.py :

# Run single script
mpremote run src/hardware_tests/sensor_test.py

# Serial monitor
mpremote
```

### Type Checking
- Uses Pyright with custom config (`pyrightconfig.json`)
- Type stubs in `typings/` (includes micropython-rp2-pico_w-stubs)
- Run: `pyright src/` (may have false positives due to MicroPython)

## Deployment

### Production Deployment
1. Ensure `config.json` and TLS certificates are in `certs/` directory
2. Run `./scripts/run_on_device.sh` to deploy
3. Device automatically starts main loop on boot

### Certificates
The MQTT connection requires TLS certificates in DER format:
- `ca_crt.der`: CA certificate
- `irrigationbackyard_crt.der`: Device certificate
- `irrigationbackyard_key.der`: Private key

These files must be placed in the `certs/` directory (excluded from git). The certificate paths are hardcoded in `mqtt_hass_manager.py:11-13`.

### Factory Reset
Use `./scripts/factory_reset.sh` to clear device filesystem and reinstall MicroPython firmware. **Note**: The device must be in BOOTSEL mode before running this script. The script:
1. Erases the flash with `picotool erase`
2. Downloads the latest MicroPython firmware for Raspberry Pi Pico W
3. Loads the firmware onto the device
4. Removes the downloaded firmware file

### Version Management
1. Update version in `config.template.json` (if version field added)
2. Tag git repository with semantic version
3. Document changes in `docs/`

## MQTT & Home Assistant Integration

### Topic Structure
- Discovery: `homeassistant/sensor/irrigation_{station_id}/{point_id}_moisture/config`
- State: `irrigation/{station_id}/{point_id}/moisture`
- Command: `irrigation/{station_id}/{point_id}/valve/set`

### Entity Types
- **Sensor**: Soil moisture percentage (0-100%)
- **Switch**: Valve control (ON/OFF)

### Auto-Discovery
- Implemented in `mqtt_hass_entities.py`
- Uses MQTT discovery protocol
- Entities appear automatically in Home Assistant

## Common Tasks for AI Agents

### Adding New Features
1. Understand hardware constraints (memory, timing)
2. Follow existing patterns in similar modules
3. Add type hints and docstrings
4. Test on actual hardware
5. Update documentation if needed

### Debugging Issues
1. **Check serial logs** via `mpremote`
2. **Verify hardware connections** with test scripts
3. **Review configuration** validity
4. **Monitor MQTT traffic** (e.g., with `mosquitto_sub`)

### Performance Optimization
- Minimize memory allocations in loops
- Use `sleep_ms()` instead of `sleep()` for short delays
- Aggregate sensor readings (rolling average)
- Enable garbage collection periodically

### Safety Considerations
- **Always turn off MOSFETs** when not reading sensors
- **Limit valve activation time** to prevent flooding
- **Implement watchdog** to recover from hangs
- **Validate sensor readings** before acting

## Troubleshooting

### Common Problems
| Symptom | Possible Cause | Solution |
|---------|---------------|----------|
| No WiFi connection | Wrong SSID/password | Check `config.json` |
| MQTT connection failed | TLS certs missing | Ensure `certs/` files exist |
| Sensor readings erratic | Loose connections | Run hardware tests |
| Memory allocation errors | Memory leak | Add `gc.collect()` |

### Logging
- Logs output to serial (USB)
- Timestamp prefix when NTP synchronized
- Log level controlled by `PRINT_LOGS` in `main.py`

## Contributing Guidelines

### Commit Messages
Follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code restructuring
- `test:` Test additions/modifications
- `chore:` Maintenance tasks

### Code Review Checklist
- [ ] Type hints present
- [ ] No MicroPython-incompatible syntax
- [ ] Memory usage considered
- [ ] Hardware interactions safe
- [ ] Configuration changes documented
- [ ] Tests pass on hardware

## References

- [MicroPython Documentation](https://docs.micropython.org/)
- [Raspberry Pi Pico Datasheet](https://datasheets.raspberrypi.com/picow/pico-w-datasheet.pdf)
- [Home Assistant MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery)
- [ADS1115 Datasheet](https://www.ti.com/lit/ds/symlink/ads1115.pdf)

---

*Last updated: March 2025*
*Maintainer: Project maintainers*
