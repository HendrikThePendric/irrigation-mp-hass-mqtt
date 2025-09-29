from machine import Pin
from logger import Logger


class Valve:
    """Represents an irrigation valve controlled by a binary GPIO pin."""
    
    STATE_OPEN = "open"
    STATE_CLOSED = "closed"
    
    def __init__(self, name: str, valve_pin: int, logger: Logger) -> None:
        """Initialize the valve with its GPIO pin configuration."""
        self.name = name
        self._valve = Pin(valve_pin, Pin.OUT)
        self._valve_pin = valve_pin
        self._valve_state = Valve.STATE_CLOSED
        self._logger = logger
        
        # Ensure valve is closed initially
        self._valve.value(0)
    
    def open(self) -> None:
        """Open the irrigation valve."""
        self._valve.value(1)
        self._valve_state = Valve.STATE_OPEN
        self._logger.log(f"[Valve] {self.name}: Valve opened, sent value 1 to pin {self._valve_pin}")
    
    def close(self) -> None:
        """Close the irrigation valve."""
        self._valve.value(0)
        self._valve_state = Valve.STATE_CLOSED
        self._logger.log(f"[Valve] {self.name}: Valve closed, sent value 0 to pin {self._valve_pin}")
    
    def get_state(self) -> str:
        """Return the current state (open/closed) of the valve."""
        self._logger.log(f"[Valve] {self.name}: Valve state is {self._valve_state}")
        return self._valve_state