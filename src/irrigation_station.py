from machine import ADC, Pin
from config import Config, IrrigationPointConfig


from logger import Logger


class IrrigationPoint:
    STATE_OPEN = "open"
    STATE_CLOSED = "closed"

    def __init__(self, config: IrrigationPointConfig, logger: Logger) -> None:
        """Initialize an irrigation point with its configuration."""
        self.config = config
        self._valve_state: str = IrrigationPoint.STATE_CLOSED
        self._sensor = ADC(config.sensor_pin)
        self._valve = Pin(config.valve_pin, Pin.OUT)
        self._sensor_value = 0.5
        self._logger = logger

    def get_sensor_value(self) -> float:
        """Simulate and return the current soil moisture sensor value (0.0-1.0)."""
        conversion_factor = 1 / (65535)
        self._sensor_value = self._sensor.read_u16() * conversion_factor
        self._logger.log(
            f"[Sensor] {self.config.name}: Moisture level is {self._sensor_value * 100:.1f}%"
        )
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

        for point_id, point_conf in self._config.irrigation_points.items():
            self._points[point_id] = IrrigationPoint(point_conf, self._logger)

    def get_point(self, point_id: str) -> IrrigationPoint:
        """Return the IrrigationPoint instance for the given point_id."""
        if point_id not in self._points:
            raise ValueError(f"Irrigation point '{point_id}' not found.")
        return self._points[point_id]
