# Development and Deployment

## Prerequisites

- Python 3.9+ with `venv` module
- A Raspberry Pi Pico W with MicroPython firmware
- USB connection to the Pico

Platform-specific venv packages:
- Ubuntu/Debian: `sudo apt install python3-venv`
- Arch Linux: `sudo pacman -S python-venv`
- macOS: included with Python 3

## Initial setup

### 1. Install development dependencies

```bash
./scripts/install_dev_deps.sh
```

This creates a `.venv` virtual environment and installs:
- `mpremote` and `mpr` for device communication
- `pyright` for type checking
- MicroPython type stubs (into `typings/`)
- `picotool` for factory reset

### 2. Activate the virtual environment

```bash
source ./scripts/activate_venv.sh
```

You need this active to use `mpremote`, `mpr`, and `pyright`.

### 3. Set up the test environment

```bash
./scripts/setup_micropython_test_env.sh
```

Builds the MicroPython unix port from source and installs the `unittest` package. See [testing.md](testing.md) for details.

### 4. Install MicroPython dependencies on the Pico

```bash
./scripts/install_pico_deps.sh
```

Installs required MicroPython packages (e.g., `umqtt.simple`, `ads1x15`) onto the device. Required after a factory reset or fresh firmware install.

## Development workflow

1. Edit code in `src/`
2. Run tests: `python3 tests/run_tests.py`
3. Optionally run type checking: `pyright src/`
4. Deploy to device and test on hardware

## Deploying to the device

```bash
./scripts/run_on_device.sh
```

This script:
1. Copies `src/*`, `config.json`, and `certs/*` to the Pico
2. Reboots the device
3. Opens a serial monitor (press Ctrl+X to exit)

Requirements before deploying:
- `config.json` exists (copy from `config.template.json`)
- `certs/` directory with TLS certificates (see below)
- Device connected via USB

### Manual file transfer

```bash
# Copy a single file
mpremote cp src/main.py :

# Run a script without deploying
mpremote run diagnostics/check_sensors.py
```

## TLS certificates

The MQTT connection requires TLS client certificates in DER format. Place these in the `certs/` directory:

| File | Description |
|------|-------------|
| `ca_crt.der` | CA certificate |
| `irrigationbackyard_crt.der` | Device certificate |
| `irrigationbackyard_key.der` | Device private key |

The `certs/` directory is excluded from git. The certificate file paths are defined in `src/mqtt_hass_manager.py`.

## Serial monitoring

Connect to the Pico's serial output:

```bash
mpremote
```

Press Ctrl+X to exit. Logs include timestamps when NTP is synchronized.

## Factory reset

Use this when the device filesystem is corrupted or you need a clean start.

1. Put the Pico into BOOTSEL mode (hold BOOTSEL button while plugging in USB)
2. Run the reset script:

```bash
./scripts/factory_reset.sh
```

This erases flash, downloads the latest MicroPython firmware, and flashes it.

After a factory reset:
1. Install MicroPython dependencies: `./scripts/install_pico_deps.sh`
2. Deploy your code: `./scripts/run_on_device.sh`

### picotool permissions (Linux)

If `picotool` requires sudo, install the udev rules:

```bash
sudo ./scripts/install_picotool_udev_rules.sh
```

## Type checking

```bash
pyright src/
```

Uses the config in `pyrightconfig.json` with MicroPython type stubs from `typings/`. Some false positives are expected due to MicroPython-specific APIs.
