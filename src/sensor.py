from machine import Pin
from ads1x15 import ADS1115
from time import sleep_ms
from config import IrrigationPointConfig
from logger import Logger


class Sensor:
    """Represents a soil moisture sensor with MOSFET power control."""
    
    def __init__(self, config: IrrigationPointConfig, ads: ADS1115, logger: Logger) -> None:
        """Initialize the sensor with power control and ADC configuration."""
        self._name = config.name
        self._mosfet = Pin(config.mosfet_pin, Pin.OUT) 
        self._ads_channel = config.ads_channel
        self._logger = logger
        self._value = 0.5
        self._ads = ads
        
        # Ensure sensor is powered off initially
        self._mosfet.value(0)
    
    def read_value(self) -> float:
        """Read the current soil moisture sensor value (0.0-1.0) using ADS1115."""
        # Power on the sensor
        self._mosfet.on()
        
        # Wait for sensor to stabilize
        sleep_ms(300)
        
        try:
            # Read from ADS1115
            raw = self._ads.read(0, self._ads_channel)
            voltage = self._ads.raw_to_v(raw)
            
            # Normalize to 0.0-1.0 range (assuming 0-5V sensor range)
            normalized_value = voltage / 5.0
            
            # Validate the computed value is in expected range
            if not (0.0 <= normalized_value <= 1.0):
                raise ValueError(f"Computed sensor value {normalized_value} is outside valid range [0.0, 1.0]")
            
            self._value = normalized_value
            
        except Exception as e:
            self._logger.log(f"[Sensor] {self._name}: Error reading sensor - {e}")
            self._logger.log(f"[Sensor] {self._name}: Using last known value {self._value}")
            # Keep the last known value on error
            
        finally:
            # Always power off the sensor
            self._mosfet.off()
        
        return self._value