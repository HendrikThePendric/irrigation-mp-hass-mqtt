"""Read all ADS1115 channels in a continuous loop.

Scans I2C for ADS1115 modules, then reads all 4 channels on each module
every second. Useful for verifying sensor wiring and checking voltage
readings.

Runs on the Pico W via: mpremote run diagnostics/check_sensors.py
Press Ctrl+C to stop.
"""

from machine import Pin, I2C  # type: ignore
from time import sleep
from ads1x15 import ADS1115  # type: ignore


# ADS1115 I2C addresses present on the board
ADS_ADDRESSES: list[int] = [0x48, 0x49]


def read_ads_channels(ads: ADS1115, address: int) -> None:
    """Read and print all 4 channels of a single ADS1115."""
    for ch in range(4):
        raw_value: int = ads.read(0, ch)
        voltage: float = raw_value * 6.144 / 32767
        print(
            f"  ADS@{hex(address)} CH{ch}: Raw={raw_value:6d}  Voltage={voltage:.3f}V"
        )


def main() -> None:
    # Wait so serial monitor can connect and catch all output
    sleep(5)

    # Initialize I2C
    i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
    found = i2c.scan()
    print(f"I2C addresses found: {[hex(a) for a in found]}")

    # Create ADS1115 objects for each address present on the bus
    ads_modules: list[tuple[int, ADS1115]] = []
    for addr in ADS_ADDRESSES:
        if addr in found:
            ads_modules.append((addr, ADS1115(i2c, address=addr, gain=0)))
            print(f"  ADS1115 @ {hex(addr)} — OK")
        else:
            print(f"  ADS1115 @ {hex(addr)} — NOT FOUND (skipping)")

    if not ads_modules:
        print("No ADS1115 modules found. Check wiring.")
        return

    print()
    print("Starting continuous sensor read (Ctrl+C to stop)...")
    print()

    t: int = 0
    while True:
        print(f"--- t={t}s ---")
        for addr, ads in ads_modules:
            read_ads_channels(ads, addr)
        print()
        t += 1
        sleep(1)


if __name__ == "__main__":
    main()
