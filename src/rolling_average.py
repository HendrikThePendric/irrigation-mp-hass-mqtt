from typing import List


class RollingAverage:
    """A class to compute rolling averages for smoothing sensor readings."""

    def __init__(self, window_size: int = 5, alpha: float = 0.2) -> None:
        """
        Initialize the rolling average.

        Args:
            window_size: Number of readings to average for SMA. Ignored for EMA.
            alpha: Smoothing factor for EMA (0 < alpha <= 1). Higher values give more weight to recent readings.
        """
        self._window_size = window_size
        self._alpha = alpha
        self._values: List[float] = []
        self._ema_value: float = None  # type: ignore

    def add_reading(self, value: float) -> None:
        """Add a new reading to the rolling average."""
        if self._ema_value is None:
            # Initialize EMA with the first value
            self._ema_value = value
        else:
            # Update EMA
            self._ema_value = self._alpha * value + (1 - self._alpha) * self._ema_value

        # Maintain SMA buffer
        self._values.append(value)
        if len(self._values) > self._window_size:
            self._values.pop(0)

    def get_average(self) -> float:
        """Get the current averaged value. Returns EMA if available, otherwise SMA."""
        if self._ema_value is not None:
            return self._ema_value
        elif self._values:
            return sum(self._values) / len(self._values)
        else:
            return 0.0  # Default if no readings

    def get_sma(self) -> float:
        """Get the simple moving average."""
        if not self._values:
            return 0.0
        return sum(self._values) / len(self._values)

    def get_ema(self) -> float:
        """Get the exponential moving average."""
        return self._ema_value if self._ema_value is not None else 0.0
