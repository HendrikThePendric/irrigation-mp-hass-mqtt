from machine import I2C, Pin, Timer
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
        self._measurement_timer = Timer(-1)
        self._pending_measurement = False
        
        # Initialize I2C bus (shared for all ADS modules)
        self._i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
        
        # Set up ADS modules
        self._setup_ads_modules()
        
        # Initialize irrigation points with their corresponding ADS modules
        for point_id, point_conf in self._config.irrigation_points.items():
            ads = self._ads_modules[point_conf.ads_address]
            self._points[point_id] = IrrigationPoint(point_conf, ads, self._logger)

        # Start periodic measurements
        self._start_measurement_timer()

    def _setup_ads_modules(self) -> None:
        """Deduplicate ADS addresses and initialize ADS modules."""
        unique_addresses = set(point_conf.ads_address for point_conf in self._config.irrigation_points.values())
        self._ads_modules: dict[int, ADS1115] = {}
        for address in unique_addresses:
            try:
                self._ads_modules[address] = ADS1115(self._i2c, address=address, gain=0)
                self._logger.log(f"[ADS1115] Initialized module at address {hex(address)}")
            except Exception as e:
                self._logger.log(f"[ADS1115] Failed to initialize module at address {hex(address)}: {e}")
                raise

    def get_point(self, point_id: str) -> IrrigationPoint:
        """Return the IrrigationPoint instance for the given point_id."""
        if point_id not in self._points:
            raise ValueError(f"Irrigation point '{point_id}' not found.")
        return self._points[point_id]

    def _start_measurement_timer(self) -> None:
        """Start the periodic measurement timer."""
        # Calculate interval to collect rolling_window samples over the publish interval
        interval_ms = self._config.publish_interval_ms // self._config.rolling_window
        self._measurement_timer.init(
            period=interval_ms,
            mode=Timer.PERIODIC,
            callback=self._set_pending_measurement,
        )
        self._logger.log(f"Periodic sensor measurement started (every {interval_ms} ms)")

    def _set_pending_measurement(self, _=None) -> None:
        self._pending_measurement = True

    def handle_pending_measurement(self) -> None:
        if self._pending_measurement:
            self._measure_all_sensors()
            self._pending_measurement = False

    def _measure_all_sensors(self) -> None:
        """Measure all sensors to update their rolling averages."""
        for point in self._points.values():
            point.measure_sensor()