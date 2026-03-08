"""Test rolling_average.py in MicroPython."""

import sys

# For MicroPython compatibility, use simple path manipulation
# MicroPython doesn't have os.path, so we'll add src directory directly
sys.path.insert(0, "src")

# Import the module to test
from rolling_average import RollingAverage


def test_rolling_average() -> bool:
    """Test RollingAverage class."""
    print("Testing RollingAverage...")

    # Test with window size 3 (default alpha=0.2)
    ra = RollingAverage(window_size=3)

    # Add values using add_reading
    ra.add_reading(10)
    ra.add_reading(20)
    ra.add_reading(30)

    # With default alpha=0.2, it's EMA not SMA:
    # ema1 = 10
    # ema2 = 0.2*20 + 0.8*10 = 4 + 8 = 12
    # ema3 = 0.2*30 + 0.8*12 = 6 + 9.6 = 15.6
    avg = ra.get_average()
    print(f"  RollingAverage(10,20,30) = {avg}")

    if abs(avg - 15.6) < 0.001:
        print("  ✅ RollingAverage basic test passed")
    else:
        print(f"  ❌ RollingAverage failed: expected 15.6, got {avg}")
        return False

    # Test window overflow (EMA continues, not SMA)
    ra.add_reading(40)  # EMA continues: 0.2*40 + 0.8*15.6 = 8 + 12.48 = 20.48
    avg = ra.get_average()
    print(f"  RollingAverage +40 = {avg}")

    if abs(avg - 20.48) < 0.001:
        print("  ✅ RollingAverage window overflow test passed")
    else:
        print(f"  ❌ RollingAverage window overflow failed: expected 20.48, got {avg}")
        return False

    return True


def test_exponential_moving_average() -> bool:
    """Test EMA functionality in RollingAverage class."""
    print("Testing Exponential Moving Average...")

    # Test with alpha 0.5 (window_size ignored for EMA)
    ra = RollingAverage(window_size=3, alpha=0.5)

    # Add values using add_reading (not add)
    ra.add_reading(10)
    ra.add_reading(20)
    ra.add_reading(30)

    # Calculate expected:
    # ema1 = 10 (first value)
    # ema2 = 0.5*20 + 0.5*10 = 15
    # ema3 = 0.5*30 + 0.5*15 = 22.5
    avg = ra.get_average()
    print(f"  EMA(10,20,30) = {avg}")

    if abs(avg - 22.5) < 0.001:
        print("  ✅ EMA test passed")
    else:
        print(f"  ❌ EMA failed: expected 22.5, got {avg}")
        return False

    return True


def main() -> None:
    """Run all rolling average tests."""
    print("=== Testing rolling_average.py ===")

    passed = 0
    total = 0

    # Run tests
    total += 1
    if test_rolling_average():
        passed += 1

    total += 1
    if test_exponential_moving_average():
        passed += 1

    # Summary
    print("=" * 40)
    if passed == total:
        print("✅ All rolling_average tests passed!")
    else:
        print(f"❌ {passed}/{total} tests passed")


if __name__ == "__main__":
    main()
