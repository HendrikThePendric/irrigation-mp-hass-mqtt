from machine import Pin, I2C
from config import Config, IrrigationPointConfig
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


class IrrigationStation:
    """Manages multiple irrigation points and their shared resources."""
    
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
