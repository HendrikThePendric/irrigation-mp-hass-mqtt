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

        # Final updates list
        valve_updates: list[ValveState] = []
        # Track resolved action
        resolved_command_point_id: str | None = None
        resolved_command_state: str | None = None
        currently_open_point_is_among_commands = False

        # Identify which valve is currently open
        currently_open_point_id: str | None = None
        for pid, point in self._points.items():
            if point.get_valve_state() == IrrigationPoint.STATE_OPEN:
                currently_open_point_id = pid
                break

        for command in instructions:
            if command.point_id not in self._points:
                self._logger.log(f"Unknown irrigation point: {command.point_id}")

            if (
                command.state != IrrigationPoint.STATE_OPEN
                and command.state != IrrigationPoint.STATE_CLOSED
            ):
                self._logger.log(
                    f"Unknown valve command: {command.state} for {command.point_id}"
                )

            # New commands on the same point clear earlier ones
            if command.point_id == resolved_command_point_id:
                resolved_command_point_id = None
                resolved_command_state = None

            # A command is actionable if the command state differs from current state
            if command.state != self._points[command.point_id].get_valve_state():
                resolved_command_point_id = command.point_id
                resolved_command_state = command.state

            if command.point_id == currently_open_point_id:
                currently_open_point_is_among_commands = True

        if (
            resolved_command_state == IrrigationPoint.STATE_CLOSED
            and resolved_command_point_id != currently_open_point_id
        ):
            raise Exception(
                "Logic error: the only valve to close is the currently open one"
            )

        # If there is a valid command state there is something to do, which can be:
        # Opening a new valve, which means the current needs to be closed
        # Closing a valve and effectively this can only be the currently open valve
        if resolved_command_state and currently_open_point_id:
            self._points[currently_open_point_id].close_valve()

        # Open valve if needed
        if (
            resolved_command_state == IrrigationPoint.STATE_OPEN
            and resolved_command_point_id
        ):
            self._points[resolved_command_point_id].open_valve()

        for command in instructions:
            valve_state = (
                IrrigationPoint.STATE_OPEN
                if resolved_command_point_id == command.point_id
                and resolved_command_state == IrrigationPoint.STATE_OPEN
                else IrrigationPoint.STATE_CLOSED
            )
            valve_updates.append(ValveState(command.point_id, valve_state))

        if (
            resolved_command_state
            and currently_open_point_id
            and not currently_open_point_is_among_commands
        ):
            valve_updates.append(
                ValveState(currently_open_point_id, IrrigationPoint.STATE_CLOSED)
            )

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
