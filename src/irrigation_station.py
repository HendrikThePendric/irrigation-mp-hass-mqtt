from machine import ADC, Pin, Timer
from config import Config, IrrigationPointConfig
from rolling_average import RollingAverage
from logger import Logger


class IrrigationPoint:
    STATE_OPEN = "open"
    STATE_CLOSED = "closed"
    SENSOR_READ_INTERVAL = 20_000  # 20 seconds in milliseconds (3 times per publish interval)

    def __init__(self, config: IrrigationPointConfig, logger: Logger) -> None:
        """Initialize an irrigation point with its configuration."""
        self.config = config
        self._valve_state: str = IrrigationPoint.STATE_CLOSED
        self._sensor = ADC(config.sensor_pin)
        self._valve = Pin(config.valve_pin, Pin.OUT)
        self._logger = logger
        self._rolling_average = RollingAverage(10)
        self._sensor_timer = Timer(-1)
        self._pending_sensor_reading = False
        
    def start_sensor_readings(self) -> None:
        """Start periodic sensor readings."""
        self._sensor_timer.init(
            period=self.SENSOR_READ_INTERVAL,
            mode=Timer.PERIODIC,
            callback=self._set_pending_sensor_reading,
        )
        # Take initial reading
        self._take_sensor_reading()
        
    def _set_pending_sensor_reading(self, _=None) -> None:
        """Set the pending sensor reading flag. Called by timer."""
        self._pending_sensor_reading = True
        
    def handle_pending_sensor_reading(self) -> None:
        """Handle pending sensor reading if one is scheduled."""
        if self._pending_sensor_reading:
            self._take_sensor_reading()
            self._pending_sensor_reading = False
            
    def _take_sensor_reading(self) -> None:
        """Take a sensor reading and add it to the rolling average."""
        conversion_factor = 1 / (65535)
        raw_value = self._sensor.read_u16() * conversion_factor
        self._rolling_average.add_value(raw_value)
        # self._logger.log(
        #     f"[Sensor] {self.config.name}: Raw reading {raw_value * 100:.1f}%, Average: {self.get_sensor_value() * 100:.1f}%"
        # )

    def get_sensor_value(self) -> float:
        """Return the stabilized sensor value using rolling average (0.0-1.0)."""
        return self._rolling_average.get_average()

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

        for point_id, point_conf in self._config.irrigation_points.items():
            self._points[point_id] = IrrigationPoint(point_conf, self._logger)

    def get_point(self, point_id: str) -> IrrigationPoint:
        """Return the IrrigationPoint instance for the given point_id."""
        if point_id not in self._points:
            raise ValueError(f"Irrigation point '{point_id}' not found.")
        return self._points[point_id]
        
    def start_sensor_readings(self) -> None:
        """Start periodic sensor readings for all irrigation points."""
        for point in self._points.values():
            point.start_sensor_readings()
            
    def handle_pending_sensor_readings(self) -> None:
        """Handle pending sensor readings for all irrigation points."""
        for point in self._points.values():
            point.handle_pending_sensor_reading()
