from machine import Pin, I2C
from ads1x15 import ADS1115
from time import sleep_ms
from config import IrrigationPointConfig
from logger import Logger


class Sensor:
    """Represents a soil moisture sensor with MOSFET power control."""
    
    def __init__(self, config: IrrigationPointConfig, logger: Logger) -> None:
        """Initialize the sensor with power control and ADC configuration."""
        self._name = config.name
        self._mosfet = Pin(config.mosfet_pin, Pin.OUT) 
        self._ads_address = config.ads_address
        self._ads_channel = config.ads_channel
        self._logger = logger
        self._value = 0.5
        self._ads = None
        
        # Initialize I2C and ADS1115 for this sensor
        self._i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
        try:
            self._ads = ADS1115(self._i2c, address=self._ads_address)
            self._logger.log(f"[ADS1115] Sensor {self._name}: Initialized module at address {hex(self._ads_address)}")
        except Exception as e:
            self._logger.log(f"[ADS1115] Sensor {self._name}: Failed to initialize module at address {hex(self._ads_address)}: {e}")
            raise
        
        # Ensure sensor is powered off initially
        self._mosfet.value(0)
    
    def read_value(self) -> float:
        """Read the current soil moisture sensor value (0.0-1.0) using ADS1115."""
        # Power on the sensor
        self._mosfet.value(1)
        
        # Wait for sensor to stabilize
        sleep_ms(150)
        
        try:
            # Read from ADS1115 and convert to 0.0-1.0 range 
            # (ADS1115 is 16-bit signed: -32768 to 32767, single-ended: 0 to 32767)
            normalized_value = self._ads.read(self._ads_channel) / 32767.0
            
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
            self._mosfet.value(0)
        
        return self._value