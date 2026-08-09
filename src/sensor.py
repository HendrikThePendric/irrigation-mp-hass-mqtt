from ads1x15 import ADS1115
from config import IrrigationPointConfig
from logger import Logger
from rolling_average import RollingAverage


class Sensor:
    """Represents a soil moisture sensor connected via ADS1115 ADC."""

    def __init__(
        self, config: IrrigationPointConfig, ads: ADS1115, logger: Logger
    ) -> None:
        """Initialize the sensor with ADC configuration."""
        self._name = config.name
        self._ads_channel = config.ads_channel
        self._logger = logger
        self._value = 0.5  # Initial averaged value
        self._ads = ads
        self._dry_v: float = config.dry_voltage  # type: ignore[assignment]
        self._wet_v: float = config.wet_voltage  # type: ignore[assignment]
        self._rolling_avg = RollingAverage(
            window_size=config.rolling_window, alpha=config.ema_alpha
        )

    def measure(self) -> None:
        """Measure the sensor and update the rolling average without returning the value."""
        try:
            raw = self._ads.read(0, self._ads_channel)
            voltage = self._ads.raw_to_v(raw)

            # Convert to moisture: 0.0 = dry, 1.0 = wet.
            # The sensor outputs lower voltage when wet and higher when dry,
            # so we invert and remap from the calibrated range to 0.0–1.0.
            denom = self._dry_v - self._wet_v
            if denom == 0:
                raise ValueError(
                    "Calibration range is zero"
                    f" (dry_v={self._dry_v}, wet_v={self._wet_v})"
                )

            moisture = (self._dry_v - voltage) / denom
            normalized_value = round(min(1.0, max(0.0, moisture)), 2)

            if not (0.0 <= normalized_value <= 1.0):
                raise ValueError(
                    f"Computed sensor value {normalized_value} is outside"
                    " valid range [0.0, 1.0]"
                )

            self._rolling_avg.add_reading(normalized_value)
            self._value = self._rolling_avg.get_average()

        except Exception as e:
            self._logger.log(f"[Sensor] {self._name}: Error reading sensor - {e}")
            self._logger.log(
                f"[Sensor] {self._name}: Using last known averaged value {self._value}"
            )

    def get_value(self) -> float:
        """Get the current averaged sensor value without measuring."""
        return self._value

    def get_raw_voltage(self) -> float:
        """Take a single raw voltage reading, bypassing the rolling average.

        Used for calibration: request via MQTT, response published immediately.
        """
        raw = self._ads.read(0, self._ads_channel)
        return self._ads.raw_to_v(raw)

    def update_calibration(self, dry_v: float, wet_v: float) -> None:
        """Update the per-sensor calibration voltages at runtime."""
        self._dry_v = dry_v
        self._wet_v = wet_v
