from config import Config, IrrigationPointConfig


class IrrigationPoint:
    def __init__(self, config: IrrigationPointConfig) -> None:
        self._config = config
        self._valve_state: str = "CLOSED"
        self._sensor_value = 0.5

    def get_sensor_value(self) -> float:
        self._sensor_value += 0.1
        if self._sensor_value > 1:
            self._sensor_value = 0
        print(
            f"[Sensor] {self._config.name}: Moisture level is {self._sensor_value * 100:.1f}%"
        )
        return self._sensor_value

    def open_valve(self) -> None:
        self._valve_state = "OPEN"
        print(f"[Valve] {self._config.name}: Valve opened.")

    def close_valve(self) -> None:
        self._valve_state = "CLOSED"
        print(f"[Valve] {self._config.name}: Valve closed.")

    def get_valve_state(self) -> str:
        print(f"[Valve] {self._config.name}: Valve state is {self._valve_state}")
        return self._valve_state


class IrrigationStation:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._points: dict[str, IrrigationPoint] = {}

        for point_id, point_conf in self._config.irrigation_points.items():
            self._points[point_id] = IrrigationPoint(point_conf)

    def get_point(self, point_id: str) -> IrrigationPoint:
        if point_id not in self._points:
            raise ValueError(f"Irrigation point '{point_id}' not found.")
        return self._points[point_id]
