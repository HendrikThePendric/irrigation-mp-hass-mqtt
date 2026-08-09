"""check_sensors.py — Scan all ADS1115 channels across all modules to find sensors.

Scans I2C for ADS1115 modules (0x48-0x4B), reads all channels for 15s,
then prints a summary table showing mean/min/max/std per channel.
Low std dev = working sensor. High std dev = floating/unconnected.

Usage: mpremote run diagnostics/check_sensors.py
"""

import time
from machine import I2C, Pin  # type: ignore

try:
    from ads1x15 import ADS1115  # type: ignore
except ImportError:
    import ads1x15  # type: ignore
    ADS1115 = ads1x15.ADS1115  # type: ignore


DURATION_S = 15
FULL_SCALE_V = 6.144


def raw_to_v(raw: int) -> float:
    return raw * FULL_SCALE_V / 32767.0


def main() -> None:
    i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
    found = i2c.scan()
    print(f"I2C scan: {[hex(a) for a in found]}")

    ads_addrs = [a for a in found if a in (0x48, 0x49, 0x4A, 0x4B)]
    if not ads_addrs:
        print("No ADS1115 modules found")
        return

    modules = {}
    for addr in ads_addrs:
        modules[addr] = ADS1115(i2c, address=addr, gain=0)
        print(f"ADS1115 at {hex(addr)} ready")

    channels = [(addr, ch) for addr in ads_addrs for ch in range(4)]
    samples = {k: [] for k in channels}

    print(f"Scanning {len(channels)} channels for {DURATION_S}s...")
    print()

    t_start = time.ticks_ms()
    iteration = 0

    while time.ticks_diff(time.ticks_ms(), t_start) / 1000.0 < DURATION_S:
        elapsed = time.ticks_diff(time.ticks_ms(), t_start) / 1000.0
        parts = [f"T={elapsed:.1f}"]
        for addr, ch in channels:
            raw = modules[addr].read(0, ch)
            v = raw_to_v(raw)
            samples[(addr, ch)].append(v)
            parts.append(f"{hex(addr)}/ch{ch}={raw} {v:.3f}V")
        print("  ".join(parts))
        iteration += 1

    print()
    print("=" * 50)
    print(f"SUMMARY ({iteration} samples/channel)")
    print("=" * 50)
    for addr in ads_addrs:
        print(f"\n--- ADS {hex(addr)} ---")
        for ch in range(4):
            key = (addr, ch)
            vals = samples[key]
            n = len(vals)
            mean = sum(vals) / n
            sv = sorted(vals)
            mn, mx = sv[0], sv[-1]
            variance = sum((v - mean) ** 2 for v in vals) / n
            std = variance ** 0.5
            print(
                f"  ch{ch}: mean={mean:.3f}V min={mn:.3f}V max={mx:.3f}V"
                f" std={std:.3f}V"
            )

    print()
    print(
        "Tip: ch1 on 0x48 has std=0.000V (= working sensor). "
        "Channels with std > 0.01V are likely floating/unconnected."
    )


if __name__ == "__main__":
    main()
