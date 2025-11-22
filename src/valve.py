from machine import Pin
from config import IrrigationPointConfig
from logger import Logger


class Valve:
    """Represents an irrigation valve controlled by a binary GPIO pin."""

    STATE_OPEN = "open"
    STATE_CLOSED = "closed"

    def __init__(self, config: IrrigationPointConfig, logger: Logger) -> None:
        """Initialize the valve with its GPIO pin configuration."""
        self._name = config.name
        self._valve = Pin(config.valve_pin, Pin.OUT)
        self._pin = config.valve_pin
        self._state = Valve.STATE_CLOSED
        self._logger = logger

        # Ensure valve is closed initially
        self._valve.value(0)

    def open(self) -> None:
        """Open the irrigation valve."""
        self._valve.on()
        self._state = Valve.STATE_OPEN
        self._logger.log(
            f"[Valve] {self._name}: Valve opened, sent value 1 to pin {self._pin}"
        )

    def close(self) -> None:
        """Close the irrigation valve."""
        self._valve.off()
        self._state = Valve.STATE_CLOSED
        self._logger.log(
            f"[Valve] {self._name}: Valve closed, sent value 0 to pin {self._pin}"
        )

    def get_state(self) -> str:
        """Return the current state (open/closed) of the valve."""
        self._logger.log(f"[Valve] {self._name}: Valve state is {self._state}")
        return self._state
