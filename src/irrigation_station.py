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
        # Initialize I2C bus (shared for all ADS modules)
        self._i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)

        # Set up ADS modules
        self._setup_ads_modules()

        # Initialize irrigation points with their corresponding ADS modules
        for point_id, point_conf in self._config.irrigation_points.items():
            ads = self._ads_modules[point_conf.ads_address]
            self._points[point_id] = IrrigationPoint(point_conf, ads, self._logger)

    def process_instructions(self, instructions: list[ValveState]) -> list[ValveState]:
        """Process valve commands from MQTT manager and return valve updates.

        While it is possible to receive a list of various instructions that possibly
        conflict with one another, the actions the irrigation station can take in
        response to these instructions is very limited. It can openn a single valve and
        optionally close the one that is currently open. Or it can close a valve that is
        currently open. We implement this behaviour by interprating the last command that
        causes an actual change as the actual command to take.
        We do however want to return a full list of updates for all instructions received
        even if some instructions are actually noops. Plus potentially 1 additional
        update for closing the currently open pin.
        """
        if not instructions:
            return []

        # Identify which valve is currently open
        current_open_point_id: str | None = None
        for pid, point in self._points.items():
            if point.get_valve_state() == IrrigationPoint.STATE_OPEN:
                current_open_point_id = pid
                break

        # Helpers for computing state updates
        valve_updates: list[ValveState] = []
        last_command_opened_point_id: str | None = None
        valve_states = {}

        for command in instructions:
            if command.point_id not in self._points:
                self._logger.log(f"Unknown irrigation point: {command.point_id}")
                continue

            if (
                command.state != IrrigationPoint.STATE_OPEN
                and command.state != IrrigationPoint.STATE_CLOSED
            ):
                self._logger.log(
                    f"Unknown valve command: {command.state} for {command.point_id}"
                )
                continue

            # Opening a new valve
            if (
                command.state == IrrigationPoint.STATE_OPEN
                and command.point_id != last_command_opened_point_id
            ):
                # Close other if present
                if last_command_opened_point_id:
                    valve_states[last_command_opened_point_id] = (
                        IrrigationPoint.STATE_CLOSED
                    )
                # Update last_command_opened_point_id
                last_command_opened_point_id = command.point_id

            # Unset open_point_id when all valves are closed
            if (
                command.state == IrrigationPoint.STATE_CLOSED
                and command.point_id == last_command_opened_point_id
            ):
                last_command_opened_point_id = None

            valve_states[command.point_id] = command.state

        if (
            current_open_point_id
            and current_open_point_id != last_command_opened_point_id
        ):
            self._points[current_open_point_id].close_valve()
            valve_states[current_open_point_id] = IrrigationPoint.STATE_CLOSED

        if (
            last_command_opened_point_id
            and current_open_point_id != last_command_opened_point_id
        ):
            self._points[last_command_opened_point_id].open_valve()

        for pid, state in valve_states.items():
            valve_updates.append(ValveState(pid, state))

        return valve_updates

    def take_measurements(self) -> None:
        """Take sensor measurements for all points."""
        for point_id, point in self._points.items():
            try:
                point.measure_sensor()
            except Exception as e:
                self._logger.log(
                    "Failed to measure sensor for point " + point_id + ": " + str(e)
                )

    def get_sensor_states(self) -> list[SensorState]:
        """Return sensor readings for all points."""
        sensor_states: list[SensorState] = []
        for point_id, point in self._points.items():
            moisture = point.get_sensor_value()
            sensor_states.append(SensorState(point_id, moisture))
        return sensor_states

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
