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
        
        # Initialize irrigation points (each will handle their own ADS module)
        for point_id, point_conf in self._config.irrigation_points.items():
            self._points[point_id] = IrrigationPoint(point_conf, self._logger)

    def get_point(self, point_id: str) -> IrrigationPoint:
        """Return the IrrigationPoint instance for the given point_id."""
        if point_id not in self._points:
            raise ValueError(f"Irrigation point '{point_id}' not found.")
        return self._points[point_id]