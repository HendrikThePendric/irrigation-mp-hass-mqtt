from machine import I2C, Pin
from ads1x15 import ADS1115
from config import Config
from irrigation_point import IrrigationPoint
from logger import Logger


class IrrigationStation:
    """Manages multiple irrigation points and their shared resources."""
    
    def __init__(self, config: Config, logger: Logger) -> None:
        """Initialize the irrigation station with all configured points."""
        self._config = config
        self._points: dict[str, IrrigationPoint] = {}
        self._logger = logger
        
        # Initialize I2C bus (shared for all ADS modules)
        self._i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
        
        # Set up ADS modules
        self._setup_ads_modules()
        
        # Initialize irrigation points with their corresponding ADS modules
        for point_id, point_conf in self._config.irrigation_points.items():
            ads = self._ads_modules[point_conf.ads_address]
            self._points[point_id] = IrrigationPoint(point_conf, ads, self._logger)

    def _setup_ads_modules(self) -> None:
        """Deduplicate ADS addresses and initialize ADS modules."""
        unique_addresses = set(point_conf.ads_address for point_conf in self._config.irrigation_points.values())
        self._ads_modules: dict[int, ADS1115] = {}
        for address in unique_addresses:
            try:
                self._ads_modules[address] = ADS1115(self._i2c, address=address)
                self._logger.log(f"[ADS1115] Initialized module at address {hex(address)}")
            except Exception as e:
                self._logger.log(f"[ADS1115] Failed to initialize module at address {hex(address)}: {e}")
                raise

    def get_point(self, point_id: str) -> IrrigationPoint:
        """Return the IrrigationPoint instance for the given point_id."""
        if point_id not in self._points:
            raise ValueError(f"Irrigation point '{point_id}' not found.")
        return self._points[point_id]