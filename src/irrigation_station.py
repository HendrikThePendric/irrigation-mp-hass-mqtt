from machine import Pin, I2C
from config import Config, IrrigationPointConfig
from ads1x15 import ADS1115
from time import sleep_ms

from logger import Logger


class IrrigationPoint:
    STATE_OPEN = "open"
    STATE_CLOSED = "closed"

    def __init__(self, config: IrrigationPointConfig, ads_modules: dict[int, ADS1115], logger: Logger) -> None:
        """Initialize an irrigation point with its configuration."""
        self.config = config
        self._valve_state: str = IrrigationPoint.STATE_CLOSED
        self._valve = Pin(config.valve_pin, Pin.OUT)
        self._mosfet = Pin(config.mosfet_pin, Pin.OUT)
        self._ads = ads_modules[config.ads_address]
        self._sensor_value = 0.5
        self._logger = logger
        
        # Ensure sensor is powered off initially
        self._mosfet.value(0)

    def get_sensor_value(self) -> float:
        """Read the current soil moisture sensor value (0.0-1.0) using ADS1115."""
        # Power on the sensor
        self._mosfet.value(1)
        
        # Wait for sensor to stabilize
        sleep_ms(100)
        
        try:
            # Read from ADS1115
            raw_value = self._ads.read(self.config.ads_channel)
            
            # Convert to 0.0-1.0 range (ADS1115 is 16-bit signed: -32768 to 32767)
            # Assuming single-ended measurement, values should be 0 to 32767
            self._sensor_value = max(0.0, min(1.0, raw_value / 32767.0))
            
        except Exception as e:
            self._logger.log(f"[Sensor] {self.config.name}: Error reading sensor: {e}")
            # Return last known value on error
        finally:
            # Always power off the sensor
            self._mosfet.value(0)
        
        return self._sensor_value

    def open_valve(self) -> None:
        """Open the irrigation valve for this point."""
        self._valve.value(1)
        self._valve_state = IrrigationPoint.STATE_OPEN
        self._logger.log(
            f"[Valve] {self.config.name}: Valve opened, sent value 1 to pin {str(self.config.valve_pin)}"
        )

    def close_valve(self) -> None:
        """Close the irrigation valve for this point."""
        self._valve.value(0)
        self._valve_state = IrrigationPoint.STATE_CLOSED
        self._logger.log(
            f"[Valve] {self.config.name}: Valve closed, sent value 0 to pin {str(self.config.valve_pin)}"
        )

    def get_valve_state(self) -> str:
        """Return the current state (open/closed) of the valve."""
        self._logger.log(
            f"[Valve] {self.config.name}: Valve state is {self._valve_state}"
        )
        return self._valve_state


class IrrigationStation:
    def __init__(self, config: Config, logger: Logger) -> None:
        """Initialize the irrigation station with all configured points."""
        self._config = config
        self._points: dict[str, IrrigationPoint] = {}
        self._logger = logger
        
        # Initialize I2C bus for ADS1115 modules
        # Using pins 0 (SDA) and 1 (SCL) as mentioned in assembly docs
        self._i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
        
        # Initialize ADS1115 modules based on configured addresses
        self._ads_modules: dict[int, ADS1115] = {}
        ads_addresses = {point.ads_address for point in config.irrigation_points.values()}
        
        for address in ads_addresses:
            try:
                self._ads_modules[address] = ADS1115(self._i2c, address=address)
                self._logger.log(f"[ADS1115] Initialized module at address {hex(address)}")
            except Exception as e:
                self._logger.log(f"[ADS1115] Failed to initialize module at address {hex(address)}: {e}")
                raise
        
        # Initialize irrigation points with ADS modules
        for point_id, point_conf in self._config.irrigation_points.items():
            self._points[point_id] = IrrigationPoint(point_conf, self._ads_modules, self._logger)

    def get_point(self, point_id: str) -> IrrigationPoint:
        """Return the IrrigationPoint instance for the given point_id."""
        if point_id not in self._points:
            raise ValueError(f"Irrigation point '{point_id}' not found.")
        return self._points[point_id]
