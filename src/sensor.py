from ads1x15 import ADS1115
from config import IrrigationPointConfig
from logger import Logger
from rolling_average import RollingAverage

# Calibration constants for soil moisture sensor.
# These are normalized voltage values (voltage / 5.0) defining the sensor's
# operating range. Adjust these based on your sensor's observed readings.
# SENSOR_DRY: normalized voltage in dry soil (packed in pots, not in open air)
# SENSOR_WET: normalized voltage in fully watered/saturated soil
SENSOR_DRY = 0.48  # Normalized voltage when sensor is in dry soil
SENSOR_WET = 0.19  # Normalized voltage when sensor is in wet soil


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
        self._rolling_avg = RollingAverage(
            window_size=config.rolling_window, alpha=config.ema_alpha
        )

    def measure(self) -> None:
        """Measure the sensor and update the rolling average without returning the value."""
        try:
            # Read from ADS1115
            raw = self._ads.read(0, self._ads_channel)
            voltage = self._ads.raw_to_v(raw)

            # Normalize voltage to 0.0-1.0 range (assuming 0-5V sensor)
            normalized_voltage = round(voltage / 5.0, 2)

            # Convert to moisture: 0.0 = dry, 1.0 = wet
            # The sensor outputs lower voltage when wet and higher when dry,
            # so we invert and remap from the calibrated range to 0.0-1.0.
            moisture = (SENSOR_DRY - normalized_voltage) / (SENSOR_DRY - SENSOR_WET)
            normalized_value = round(min(1.0, max(0.0, moisture)), 2)

            # Validate the computed value is in expected range
            if not (0.0 <= normalized_value <= 1.0):
                raise ValueError(
                    f"Computed sensor value {normalized_value} is outside valid range [0.0, 1.0]"
                )

            self._rolling_avg.add_reading(normalized_value)
            self._value = self._rolling_avg.get_average()

        except Exception as e:
            self._logger.log(f"[Sensor] {self._name}: Error reading sensor - {e}")
            self._logger.log(
                f"[Sensor] {self._name}: Using last known averaged value {self._value}"
            )
            # Keep the last averaged value on error

    def get_value(self) -> float:
        """Get the current averaged sensor value without measuring."""
        return self._value
