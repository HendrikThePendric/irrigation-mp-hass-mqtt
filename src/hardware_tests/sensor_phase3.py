"""Phase 3: moisture response test for Location 1.

Sensor should start IN water.
~20s: pull sensor OUT of water
~40s: put sensor BACK IN water
"""

from machine import Pin, I2C
from time import sleep

from ads1x15 import ADS1115


MOSFET_PIN = 18  # Location 1
ALL_MOSFET_PINS = [18, 19, 20, 21, 22, 28, 26, 27]


def main() -> None:
    sleep(3)

    print("Initializing...")
    i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
    ads = ADS1115(i2c, address=0x48, gain=0)

    # All MOSFETs off
    mosfets = [Pin(p, Pin.OUT) for p in ALL_MOSFET_PINS]
    for m in mosfets:
        m.off()

    mosfet = Pin(MOSFET_PIN, Pin.OUT)
    mosfet.on()
    print(f"MOSFET pin {MOSFET_PIN} ON - stabilizing 5s...")
    sleep(5)

    print("")
    print("=" * 50)
    print("  MOISTURE RESPONSE TEST - Location 1 (v2.0)")
    print("  Sensor should be IN WATER now")
    print("")
    print("  At ~20s: PULL SENSOR OUT of water")
    print("  At ~40s: PUT SENSOR BACK IN water")
    print("=" * 50)
    print("")

    for t in range(0, 61):
        raw = ads.read(0, 0)
        voltage = raw * 6.144 / 32767

        marker = ""
        if t == 20:
            marker = "  <<< PULL OUT NOW >>>"
        elif t == 40:
            marker = "  <<< PUT BACK IN NOW >>>"

        print(f"  t={t:3d}s: Raw={raw:6d}, V={voltage:.3f}V{marker}")
        if t < 60:
            sleep(1)

    mosfet.off()
    print(f"\nMOSFET OFF. Done.")


if __name__ == "__main__":
    main()
