# Diagnostics

Scripts for verifying physical wiring on the actual Pico device. Run them with `mpremote` to check that sensors and valves are connected correctly and to discover the terminal-to-pin mappings for your `config.json`.

These are **not** automated tests — they run interactively on the device and print output to the serial console.

## Usage

```bash
mpremote run diagnostics/check_sensors.py
mpremote run diagnostics/check_valves.py
```

`check_breadboard_sensor.py` is a standalone debugging script for isolating sensor issues with a breadboard setup. You probably don't need it unless you're troubleshooting a specific sensor problem.

## Terminal mappings

The tables below describe how the various terminals are mapped. Use the check scripts to populate them, then use the tables to populate `config.json`.

### Sensors

| Terminal | Address | Channel |
|----------|---------|---------|
| Left-1   | 0x48    | 0       |
| Left-2   | 0x48    | 1       |
| Left-3   | 0x48    | 2       |
| Left-4   | 0x48    | 3       |
| Left-5   | 0x49    | 0       |
| Right-1  | 0x49    | 1       |
| Right-2  | 0x49    | 2       |
| Right-3  | 0x49    | 3       |

### Valves

| Terminal | GPIO Pin |
|----------|----------|
| Left-1   | 9        |
| Left-2   | 8        |
| Left-3   | 7        |
| Left-4   | 6        |
| Right-1  | 2        |
| Right-2  | 3        |
| Right-3  | 4        |
| Right-4  | 5        |
