"""Breadboard sensor test: isolate the root cause step by step.

Uses the Pico's built-in ADC on GP26 to read a capacitive soil moisture
sensor directly. Each step adds one variable from the main board setup.

Steps (set STEP below):
  1: 3.3V direct, no MOSFET                 (baseline - confirmed working)
  2: 3.3V via N-channel MOSFET high-side     (add MOSFET)
  3: 5V direct, voltage divider on AOUT      (add 5V, no MOSFET)
  4: 5V via N-channel MOSFET high-side       (add MOSFET on 5V)
  5: Same as 4, plus decoupling caps         (add caps)
  6: 5V + MOSFET LOW-SIDE + divider
  6b: Same as 6, with voltage monitoring     (add GP27 on MOSFET Drain)

Runs in a continuous loop. Press Ctrl+C to stop.
"""

from machine import Pin, ADC  # type: ignore
from time import sleep


# ---- Configuration ----
STEP = "6b"
MOSFET_PIN = 15  # GP15 — gate control
ADC_SIGNAL_PIN = 26  # GP26 = ADC0 — sensor AOUT (via voltage divider)
ADC_MONITOR_PIN = 27  # GP27 = ADC1 — MOSFET Drain (sensor GND side)
# -----------------------

USE_MOSFET = STEP in (2, 4, 5, 6, "6b")
USE_5V = STEP in (3, 4, 5, 6, "6b")
USE_MONITOR = STEP == "6b"
MAX_VOLTAGE = 5.0 if USE_5V else 3.3
DIVIDER_FACTOR = 2.0 if USE_5V else 1.0
BAR_WIDTH = 16

STEP_DESCRIPTIONS = {
    1: "3.3V direct (baseline)",
    2: "3.3V + MOSFET high-side",
    3: "5V direct + voltage divider",
    4: "5V + MOSFET high-side + divider",
    5: "5V + MOSFET + divider + caps",
    6: "5V + MOSFET LOW-SIDE + divider",
    "6b": "5V + MOSFET LOW-SIDE + divider + monitor",
}


def voltage_bar(voltage: float, max_v: float) -> str:
    """Return a 16-char bar graph for the given voltage."""
    ratio = max(0.0, min(1.0, voltage / max_v))
    filled = int(ratio * BAR_WIDTH)
    return "\u2588" * filled + "\u2591" * (BAR_WIDTH - filled)


def main() -> None:
    sleep(3)

    adc_signal = ADC(Pin(ADC_SIGNAL_PIN))
    adc_monitor = ADC(Pin(ADC_MONITOR_PIN)) if USE_MONITOR else None

    if USE_MOSFET:
        mosfet = Pin(MOSFET_PIN, Pin.OUT)
        mosfet.on()
        mosfet_status = f"GP{MOSFET_PIN} ON"
    else:
        mosfet_status = "none"

    desc = STEP_DESCRIPTIONS.get(STEP, "unknown")

    print("")
    print("=" * 58)
    print(f"  BREADBOARD SENSOR TEST — Step {STEP}")
    print(f"  {desc}")
    print(f"  MOSFET: {mosfet_status}  |  Signal: GP{ADC_SIGNAL_PIN}")
    if USE_MONITOR:
        print(f"  Monitor: GP{ADC_MONITOR_PIN} (MOSFET Drain = sensor GND)")
        print(f"  Sensor supply = 5.0V - Vdrain")
    print(f"  Voltage range: 0-{MAX_VOLTAGE}V")
    print("  Ctrl+C to stop")
    print("=" * 58)
    print("")

    sleep(2)

    t = 0
    while True:
        raw = adc_signal.read_u16()
        adc_voltage = raw / 65535 * 3.3
        actual_voltage = adc_voltage * DIVIDER_FACTOR
        bar = voltage_bar(actual_voltage, MAX_VOLTAGE)

        line = f"  t={t:4d}s: AOUT={actual_voltage:.3f}V [{bar}]"

        if adc_monitor is not None:
            mon_raw = adc_monitor.read_u16()
            mon_voltage = mon_raw / 65535 * 3.3
            supply = 5.0 - mon_voltage
            line += f"  Vdrain={mon_voltage:.3f}V  Supply={supply:.2f}V"

        print(line)

        t += 1
        sleep(1)


if __name__ == "__main__":
    main()
