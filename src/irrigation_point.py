from ads1x15 import ADS1115
from config import IrrigationPointConfig
from sensor import Sensor
from valve import Valve
from logger import Logger


class IrrigationPoint:
    """Represents a single irrigation point with sensor and valve components."""
    
    def __init__(self, config: IrrigationPointConfig, ads: ADS1115, logger: Logger) -> None:
        """Initialize an irrigation point with its sensor and valve components."""
        self.config = config
        self._logger = logger
        
        # Initialize sensor and valve components
        self._sensor = Sensor(config, ads, logger)
        self._valve = Valve(config, logger)

    def get_sensor_value(self) -> float:
        """Get the current averaged soil moisture sensor value (0.0-1.0)."""
        return self._sensor.get_value()

    def measure_sensor(self) -> None:
        """Measure the sensor and update the rolling average without returning the value."""
        self._sensor.measure()

    def open_valve(self) -> None:
        """Open the irrigation valve for this point."""
        self._valve.open()

    def close_valve(self) -> None:
        """Close the irrigation valve for this point."""
        self._valve.close()

    def get_valve_state(self) -> str:
        """Return the current state (open/closed) of the valve."""
        return self._valve.get_state()
