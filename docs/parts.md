# Parts

## Core components

| Part | Quantity | Notes |
|------|----------|-------|
| Raspberry Pi Pico W | 1 | RP2040 microcontroller with WiFi |
| Perfboard | 1 | Large enough for all components |
| Pico header rails | 2 | Male or female, for socketing the Pico |

## Power supply

| Part | Quantity | Notes |
|------|----------|-------|
| 220V AC to 12V DC converter | 1 | |
| 12V to 5V USB stepdown converter | 1 | Powers the Pico and sensors |
| 2-pin screw terminal | 1 | Connects to 12V DC output |

## Analog signal readings (I2C)

| Part | Quantity | Notes |
|------|----------|-------|
| ADS1115 ADC module | 2 | I2C addresses 0x48 and 0x49, 4 channels each |
| I2C level shifter | 1 | 3.3V (Pico) to 5V (ADS1115) |
| 0.1μF ceramic capacitor | 4 | Decoupling: 2 for level shifter (HV + LV), 2 for ADS1115 modules |

## Sensors

| Part | Quantity | Notes |
|------|----------|-------|
| Capacitive soil moisture sensor | up to 8 | Must be capacitive (not resistive) |
| 3-pin screw terminal | up to 8 | VCC, GND, AOUT per sensor location |

## Valves

| Part | Quantity | Notes |
|------|----------|-------|
| Solenoid valve | up to 4 | 12V or as required |
| Relay module | up to 4 | Controlled by Pico GPIO |

## Wiring

| Part | Notes |
|------|-------|
| Jump wires | For connections on the perfboard |
| Solder wire | For soldering components to perfboard |
| 3-core cable | Connects sensors to screw terminals (VCC, GND, AOUT) |
