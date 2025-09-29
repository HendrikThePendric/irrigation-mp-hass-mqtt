from config import IrrigationPointConfig
from ads1x15 import ADS1115
from sensor import Sensor
from valve import Valve
from logger import Logger


class IrrigationPoint:
    """Represents a single irrigation point with sensor and valve components."""
    
    def __init__(self, config: IrrigationPointConfig, ads_modules: dict[int, ADS1115], logger: Logger) -> None:
        """Initialize an irrigation point with its sensor and valve components."""
        self.config = config
        self._logger = logger
        
        # Initialize sensor and valve components
        self._sensor = Sensor(
            name=config.name,
            mosfet_pin=config.mosfet_pin,
            ads_module=ads_modules[config.ads_address],
            ads_channel=config.ads_channel,
            logger=logger
        )
        
        self._valve = Valve(
            name=config.name,
            valve_pin=config.valve_pin,
            logger=logger
        )

    def get_sensor_value(self) -> float:
        """Read the current soil moisture sensor value (0.0-1.0)."""
        return self._sensor.read_value()

    def open_valve(self) -> None:
        """Open the irrigation valve for this point."""
        self._valve.open()

    def close_valve(self) -> None:
        """Close the irrigation valve for this point."""
        self._valve.close()

    def get_valve_state(self) -> str:
        """Return the current state (open/closed) of the valve."""
        return self._valve.get_state()
