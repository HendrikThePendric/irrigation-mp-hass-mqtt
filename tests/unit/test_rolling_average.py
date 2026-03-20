"""Test rolling_average.py using unittest framework."""

# pyright: basic
import sys

# For MicroPython compatibility, use simple path manipulation
# MicroPython doesn't have os.path, so we'll add src directory directly
sys.path.insert(0, "src")

# Import unittest - this should work since we installed it via mip
import unittest

# Import the module to test
from rolling_average import RollingAverage


class TestRollingAverage(unittest.TestCase):
    """Test RollingAverage class using unittest framework."""

    def test_basic_average(self) -> None:
        """Test RollingAverage basic functionality."""
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

        # Use assertAlmostEqual for floating point comparison
        self.assertAlmostEqual(avg, 15.6, places=3)

    def test_window_overflow(self) -> None:
        """Test RollingAverage with window overflow."""
        ra = RollingAverage(window_size=3)

        # Add initial values
        ra.add_reading(10)
        ra.add_reading(20)
        ra.add_reading(30)

        # Add fourth value (window overflow)
        ra.add_reading(40)  # EMA continues: 0.2*40 + 0.8*15.6 = 8 + 12.48 = 20.48
        avg = ra.get_average()

        self.assertAlmostEqual(avg, 20.48, places=3)

    def test_exponential_moving_average(self) -> None:
        """Test EMA functionality in RollingAverage class."""
        # Test with alpha 0.5 (window_size ignored for EMA)
        ra = RollingAverage(window_size=3, alpha=0.5)

        # Add values using add_reading
        ra.add_reading(10)
        ra.add_reading(20)
        ra.add_reading(30)

        # Calculate expected:
        # ema1 = 10 (first value)
        # ema2 = 0.5*20 + 0.5*10 = 15
        # ema3 = 0.5*30 + 0.5*15 = 22.5
        avg = ra.get_average()

        self.assertAlmostEqual(avg, 22.5, places=3)

    def test_empty_average(self) -> None:
        """Test RollingAverage with no readings."""
        ra = RollingAverage(window_size=3)

        # Should return 0 when no readings
        avg = ra.get_average()
        self.assertEqual(avg, 0.0)

    def test_single_reading(self) -> None:
        """Test RollingAverage with single reading."""
        ra = RollingAverage(window_size=3)

        ra.add_reading(42.5)
        avg = ra.get_average()

        # With EMA, first value is the average
        self.assertAlmostEqual(avg, 42.5, places=3)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
