from machine import I2C, Pin
from ads1x15 import ADS1115
from config import Config
from irrigation_point import IrrigationPoint
from logger import Logger
from irrigation_states import ValveState, SensorState


class IrrigationStation:
    """Manages multiple irrigation points and their shared resources."""

    def __init__(self, config: Config, logger: Logger) -> None:
        """Initialize the irrigation station with all configured points."""
        self._config = config
        self._points: dict[str, IrrigationPoint] = {}
        self._logger = logger
        self._pending_instructions: list[ValveState] = []
        self._valve_states: list[ValveState] = []
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
        unique_addresses = set(
            point_conf.ads_address
            for point_conf in self._config.irrigation_points.values()
        )
        self._ads_modules: dict[int, ADS1115] = {}
        for address in unique_addresses:
            try:
                self._ads_modules[address] = ADS1115(self._i2c, address=address, gain=0)
                self._logger.log(
                    f"[ADS1115] Initialized module at address {hex(address)}"
                )
            except Exception as e:
                self._logger.log(
                    f"[ADS1115] Failed to initialize module at address {hex(address)}: {e}"
                )
                raise

    def get_point(self, point_id: str) -> IrrigationPoint:
        """Return the IrrigationPoint instance for the given point_id."""
        if point_id not in self._points:
            raise ValueError(f"Irrigation point '{point_id}' not found.")
        return self._points[point_id]

    def process_instructions(self, instructions: list[ValveState]) -> None:
        """Process valve commands from MQTT manager."""
        self._pending_instructions = instructions
        if self._pending_instructions:
            self._process_valve_commands(self._pending_instructions)
            self._pending_instructions = []

    def take_measurements(self) -> None:
        """Take sensor measurements for all points."""
        self._measure_all_sensors()

    def get_valve_states(self) -> list[ValveState]:
        """Return and clear the list of valve state updates."""
        states = self._valve_states[:]
        self._valve_states.clear()
        return states

    def get_sensor_states(self) -> list[SensorState]:
        """Return sensor readings for all points."""
        sensor_states: list[SensorState] = []
        for point_id, point in self._points.items():
            moisture = point.get_sensor_value()
            sensor_states.append(SensorState(point_id, moisture))
        return sensor_states

    def _process_valve_commands(self, commands: list[ValveState]) -> None:
        """Process valve commands with exclusivity."""
        for command in commands:
            if command.point_id in self._points:
                if command.state == IrrigationPoint.STATE_OPEN:
                    self._open_valve_exclusive(command.point_id)
                elif command.state == IrrigationPoint.STATE_CLOSED:
                    self._points[command.point_id].close_valve()
                    self._add_valve_state(
                        command.point_id, IrrigationPoint.STATE_CLOSED
                    )
                else:
                    self._logger.log(
                        f"Unknown valve command: {command.state} for {command.point_id}"
                    )

    def _open_valve_exclusive(self, point_id: str) -> None:
        """Open the specified valve, closing all others first."""
        # Close all other open valves
        for pid, point in self._points.items():
            if (
                pid != point_id
                and point.get_valve_state() == IrrigationPoint.STATE_OPEN
            ):
                point.close_valve()
                self._add_valve_state(pid, IrrigationPoint.STATE_CLOSED)

        # Open the requested valve
        self._points[point_id].open_valve()
        self._add_valve_state(point_id, IrrigationPoint.STATE_OPEN)

    def _add_valve_state(self, point_id: str, state: str) -> None:
        """Add a valve state update."""
        self._valve_states.append(ValveState(point_id, state))

    def _measure_all_sensors(self) -> None:
        """Measure all sensors to update their rolling averages."""
        for point_id, point in self._points.items():
            try:
                point.measure_sensor()
            except Exception as e:
                self._logger.log(
                    "Failed to measure sensor for point " + point_id + ": " + str(e)
                )
