from machine import Pin
from ads1x15 import ADS1115
from time import sleep_ms
from logger import Logger


class Sensor:
    """Represents a soil moisture sensor with MOSFET power control."""
    
    def __init__(self, name: str, mosfet_pin: int, ads_module: ADS1115, ads_channel: int, logger: Logger) -> None:
        """Initialize the sensor with power control and ADC configuration."""
        self.name = name
        self._mosfet = Pin(mosfet_pin, Pin.OUT)
        self._ads = ads_module
        self._ads_channel = ads_channel
        self._logger = logger
        self._sensor_value = 0.5
        
        # Ensure sensor is powered off initially
        self._mosfet.value(0)
    
    def read_value(self) -> float:
        """Read the current soil moisture sensor value (0.0-1.0) using ADS1115."""
        # Power on the sensor
        self._mosfet.value(1)
        
        # Wait for sensor to stabilize
        sleep_ms(100)
        
        try:
            # Read from ADS1115
            raw_value = self._ads.read(self._ads_channel)
            
            # Convert to 0.0-1.0 range (ADS1115 is 16-bit signed: -32768 to 32767)
            # For single-ended measurement, we expect values in the range 0 to 32767
            if raw_value < 0:
                raise ValueError(f"Unexpected negative ADC reading: {raw_value}")
            
            # Calculate normalized value
            normalized_value = raw_value / 32767.0
            
            # Validate the computed value is in expected range
            if not (0.0 <= normalized_value <= 1.0):
                raise ValueError(f"Computed sensor value {normalized_value} is outside valid range [0.0, 1.0]")
            
            self._sensor_value = normalized_value
            
        except Exception as e:
            self._logger.log(f"[Sensor] {self.name}: Error reading sensor - {e}")
            self._logger.log(f"[Sensor] {self.name}: Using last known value {self._sensor_value}")
            # Keep the last known value on error
            
        finally:
            # Always power off the sensor
            self._mosfet.value(0)
        
        return self._sensor_value