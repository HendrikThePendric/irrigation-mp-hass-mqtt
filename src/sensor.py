from machine import Pin
from ads1x15 import ADS1115
from time import sleep_ms
from config import IrrigationPointConfig
from logger import Logger
from rolling_average import RollingAverage


class Sensor:
    """Represents a soil moisture sensor with MOSFET power control."""

    def __init__(
        self, config: IrrigationPointConfig, ads: ADS1115, logger: Logger
    ) -> None:
        """Initialize the sensor with power control and ADC configuration."""
        self._name = config.name
        self._mosfet = Pin(config.mosfet_pin, Pin.OUT)
        self._ads_channel = config.ads_channel
        self._logger = logger
        self._value = 0.5  # Initial averaged value
        self._ads = ads
        self._rolling_avg = RollingAverage(
            window_size=config.rolling_window, alpha=config.ema_alpha
        )

        # Ensure sensor is powered off initially
        self._mosfet.off()

    def measure(self) -> None:
        """Measure the sensor and update the rolling average without returning the value."""
        # Power on the sensor
        self._mosfet.on()

        # Wait for sensor to stabilize
        sleep_ms(300)

        try:
            # Read from ADS1115
            raw = self._ads.read(0, self._ads_channel)
            voltage = self._ads.raw_to_v(raw)

            # Normalize to 0.0-1.0 range (assuming 0-5V sensor range)
            # Round to 2 decimal places to handle minor floating-point variations
            normalized_value = round(voltage / 5.0, 2)

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

        finally:
            # Always power off the sensor
            self._mosfet.off()

    def get_value(self) -> float:
        """Get the current averaged sensor value without measuring."""
        return self._value
