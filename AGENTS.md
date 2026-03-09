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
├── opencode.json          # OpenCode MCP configuration
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

This project includes a comprehensive testing framework that allows **Test-Driven Development (TDD)** on your development machine using mocked hardware modules. Tests run in actual MicroPython interpreter.

### Test-Driven Development (TDD) Approach

1. **Write test first**: Create test for new functionality before implementation
2. **Run test**: Verify it fails (red)
3. **Implement**: Write minimal code to make test pass
4. **Refactor**: Clean up code while keeping tests green
5. **Repeat**: Add more tests for edge cases and new features

### Running Tests

#### Setup MicroPython Runtime (first time)
```bash
./scripts/setup_micropython_test_env.sh
```

#### Run All Tests
```bash
python3 tests/run_tests.py
```

#### Run Individual Tests
```bash
# Run specific test file
./micropython-local tests/unit/test_rolling_average.py

# Run test with CPython (for debugging)
python3 tests/unit/test_valve.py
```

#### Hardware Tests (on actual device)
```bash
mpremote run src/hardware_tests/sensor_test.py
mpremote run src/hardware_tests/valve_test.py
```

### Writing Tests

#### 1. Test Hardware-Free Modules
Start with modules that don't need hardware mocks:
```python
# tests/unit/test_example.py
import sys
sys.path.insert(0, "src")
from example import Example

def test_example() -> bool:
    example = Example()
    result = example.calculate()
    if result == expected:
        print("✅ Test passed")
        return True
    else:
        print(f"❌ Expected {expected}, got {result}")
        return False
```

#### 2. Test Hardware-Dependent Modules
Use simple mocks from `tests/simple_mocks.py`:
```python
# tests/unit/test_hardware.py
import sys
sys.path.insert(0, "tests")
from simple_mocks import MockPin, mock_machine, mock_os

# Create mock modules before importing hardware-dependent code
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id

sys.modules['machine'] = MachineModule()
sys.modules['os'] = mock_os

# Now import and test
from hardware_module import HardwareClass

def test_hardware() -> bool:
    hardware = HardwareClass()
    hardware.do_something()
    
    # Assert mock state
    if mock_machine.pins_created[0]._value == 1:
        print("✅ Hardware test passed")
        return True
    else:
        print("❌ Hardware test failed")
        return False
```

#### 3. Mock Design Principles
- **Keep it simple**: Mock only what's needed for the test
- **Track state**: Use attributes like `_value`, `calls` for assertions
- **Incremental**: Add mock functionality as tests need it
- **Test mocks first**: Write unit tests for mocks before using them

### Test Framework Components

1. **Test Runner** (`tests/run_tests.py`):
   - Discovers and runs all test files
   - Runs tests in MicroPython interpreter
   - Provides clear pass/fail output with ✅/❌ indicators

2. **Simple Mocks** (`tests/simple_mocks.py`):
   - Minimal mock classes for hardware modules (`machine`, `os`, `datetime`, `time`, `ntptime`)
   - Tracks state for assertions
   - Easy to extend for new tests

3. **Test Files** (`tests/unit/*.py`):
   - Self-contained test scripts
   - Print results with ✅/❌ indicators
   - Can run standalone in MicroPython

### Current Test Coverage

#### ✅ Test Framework

All test files use MicroPython's unittest framework:

- `test_config.py`: Configuration parsing and validation
- `test_logger.py`: Logging utilities with file I/O mocking
- `test_rolling_average.py`: Rolling average and EMA calculations
- `test_valve.py`: Valve control with mocked `machine.Pin`
- `test_sensor.py`: Soil moisture sensor with ADS1115 mock
- `test_irrigation_point.py`: Complete irrigation point logic
- `test_irrigation_station.py`: Station management with multiple points
- `test_time_keeper.py`: Time synchronization and scheduling
- `test_watchdog.py`: System watchdog with timer mocking

### unittest Framework Support

The project uses **MicroPython's unittest framework** exclusively. The `setup_micropython_test_env.sh` script automatically installs it.

**Example unittest test:**
```python
import sys
sys.path.insert(0, "src")
import unittest

from rolling_average import RollingAverage

class TestRollingAverage(unittest.TestCase):
    def test_basic_average(self) -> None:
        ra = RollingAverage(window_size=3)
        ra.add_reading(10)
        ra.add_reading(20)
        ra.add_reading(30)
        self.assertAlmostEqual(ra.get_average(), 15.6, places=3)

if __name__ == "__main__":
    unittest.main()
```

The test runner (`tests/run_tests.py`) runs all tests in the MicroPython interpreter.

### Validation Steps (Hardware)
1. Run hardware tests to verify connections
2. Deploy config and certificates
3. Monitor serial output for errors
4. Check Home Assistant MQTT discovery

## Development Workflow

### Local Development
1. **Write test first** (TDD approach): Create test in `tests/unit/`
2. **Run test**: Verify it fails (red phase)
3. **Implement feature**: Write minimal code in `src/` to make test pass
4. **Run tests again**: Verify all tests pass (green phase)
5. **Run type checking** (optional): `pyright src/`
6. **Refactor**: Clean up code while keeping tests green
7. **Deploy to device** (optional): `./scripts/run_on_device.sh`
   - Copies `src/`, `config.json`, and `certs/` to Pico
   - Reboots device
   - Opens serial monitor
8. **Monitor output** via serial connection

### Common Commands
```bash
# Install dependencies
./scripts/install_dev_deps.sh
./scripts/install_pico_deps.sh

# Activate virtual environment for development
source ./scripts/activate_venv.sh

# Setup MicroPython for testing (first time)
./scripts/setup_micropython_test_env.sh

# Run tests
python3 tests/run_tests.py

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

### LSP Diagnostics via Neovim MCP
The project uses OpenCode's MCP (Model Context Protocol) integration with neovim to access LSP diagnostics directly. This enables AI agents to view real-time code analysis results.

**Configuration:**
- `opencode.json` enables `neovim_*` tools and permissions
- Uses global neovim MCP server configuration from `~/.config/opencode/opencode.json`
- Requires `NVIM_SOCKET_PATH` environment variable to be set

**Accessing LSP Information:**
```bash
# View current LSP clients and diagnostics
:lua print(vim.inspect(vim.lsp.get_active_clients()))
:lua print(vim.inspect(vim.diagnostic.get(bufnr)))
```

**Common LSP Servers in this project:**
- `pyright`: Python type checking and error detection
- `ruff`: Python linting, formatting, and code fixes
- `bashls`: Bash shell script analysis
- `jsonls`: JSON validation and formatting

**Best Practices for AI Agents:**
1. Always check LSP diagnostics before and after code changes
2. Address Pyright type errors first (most critical)
3. Fix Ruff linting issues (code quality)
4. Remove unused imports flagged by both Pyright and Ruff
5. Use neovim MCP to view specific buffer diagnostics

**Example workflow:**
```lua
-- Get current buffer number
:echo bufnr()

-- Get diagnostics for current buffer
:lua print(vim.inspect(vim.diagnostic.get(12)))
```

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
1. **Write test first** (TDD): Create test in `tests/unit/` before implementation
2. Understand hardware constraints (memory, timing)
3. Follow existing patterns in similar modules
4. Add type hints and docstrings
5. **Run tests**: Verify tests pass with `python3 tests/run_tests.py`
6. Test on actual hardware (optional, for validation)
7. Update documentation if needed

### Debugging Issues
1. **Run tests**: Check if tests pass with `python3 tests/run_tests.py`
2. **Check serial logs** via `mpremote`
3. **Verify hardware connections** with test scripts
4. **Review configuration** validity
5. **Monitor MQTT traffic** (e.g., with `mosquitto_sub`)
6. **Check LSP diagnostics** via neovim MCP for code errors and type issues

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

*Last updated: March 2026*
*Maintainer: Project maintainers*
