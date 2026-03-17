from machine import I2C, Pin
from ads1x15 import ADS1115
from config import Config
from irrigation_point import IrrigationPoint
from valve import Valve
from logger import Logger
from irrigation_states import ValveState, SensorState
import time


class IrrigationStation:
    MAX_VALVE_OPEN_TIME = 45 * 60  # 45 minutes
    """Manages multiple irrigation points and their shared resources."""

    def __init__(self, config: Config, logger: Logger) -> None:
        """Initialize the irrigation station with all configured points."""
        self._config = config
        self._points: dict[str, IrrigationPoint] = {}
        self._logger = logger
        # Valve auto-close tracking
        self._last_valve_open_time: float | None = None
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
            if point.get_valve_state() == Valve.STATE_OPEN:
                current_open_point_id = pid
                break

        # Helpers for computing state updates
        valve_updates: list[ValveState] = []
        last_command_opened_point_id: str | None = current_open_point_id
        valve_states = {}

        for command in instructions:
            if command.point_id not in self._points:
                self._logger.log(f"Unknown irrigation point: {command.point_id}")
                continue

            if (
                command.state != Valve.STATE_OPEN
                and command.state != Valve.STATE_CLOSED
            ):
                self._logger.log(
                    f"Unknown valve command: {command.state} for {command.point_id}"
                )
                continue

            # Opening a new valve
            if (
                command.state == Valve.STATE_OPEN
                and command.point_id != last_command_opened_point_id
            ):
                # Close other if present
                if last_command_opened_point_id:
                    valve_states[last_command_opened_point_id] = Valve.STATE_CLOSED
                # Update last_command_opened_point_id
                last_command_opened_point_id = command.point_id

            # Unset open_point_id when all valves are closed
            if (
                command.state == Valve.STATE_CLOSED
                and command.point_id == last_command_opened_point_id
            ):
                last_command_opened_point_id = None

            valve_states[command.point_id] = command.state

        if (
            current_open_point_id
            and current_open_point_id != last_command_opened_point_id
        ):
            self._points[current_open_point_id].close_valve()
            # Reset auto-close tracking (only one valve can be open at a time)
            self._last_valve_open_time = None
            valve_states[current_open_point_id] = Valve.STATE_CLOSED

        if (
            last_command_opened_point_id
            and current_open_point_id != last_command_opened_point_id
        ):
            self._points[last_command_opened_point_id].open_valve()
            # Update auto-close tracking
            self._last_valve_open_time = time.time()

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

    def check_valve_timeout(self) -> ValveState | None:
        """Check if currently open valve has exceeded 45-minute timeout.

        Returns:
            ValveState for auto-closed valve, or None if no action needed
        """
        # Find which valve is currently open (only one can be open at a time)
        open_point_id: str | None = None
        for pid, point in self._points.items():
            if point.get_valve_state() == Valve.STATE_OPEN:
                open_point_id = pid
                break

        # No valve open → ensure tracking is reset
        if open_point_id is None:
            self._last_valve_open_time = None
            return None

        # Valve is open but we aren’t tracking it (e.g., opened externally)
        # Start tracking now to prevent indefinite opening
        if self._last_valve_open_time is None:
            self._last_valve_open_time = time.time()
            return None

        elapsed = time.time() - self._last_valve_open_time
        if elapsed >= self.MAX_VALVE_OPEN_TIME:
            self._points[open_point_id].close_valve()
            self._last_valve_open_time = None
            self._logger.log(
                f"[Auto-Close] {open_point_id}: Valve closed after {elapsed / 60:.1f} minutes"
            )
            return ValveState(open_point_id, Valve.STATE_CLOSED)

        return None

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
