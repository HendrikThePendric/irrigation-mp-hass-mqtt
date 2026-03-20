from valve import Valve


class ValveState:
    """Valve command (what we want) or status (what happened)."""

    VALID_STATES = {Valve.STATE_OPEN, Valve.STATE_CLOSED}

    def __init__(self, point_id: str, state: str) -> None:
        self.point_id = point_id
        state_lower = state.lower()
        if state_lower not in self.VALID_STATES:
            raise ValueError(
                f"Invalid valve state: {state}. Must be 'open' or 'closed'."
            )
        self.state = state_lower

    def __repr__(self) -> str:
        return f"ValveState(point_id={self.point_id!r}, state={self.state!r})"

    def __str__(self) -> str:
        return f"{self.point_id}: {self.state}"


class SensorState:
    """Soil moisture reading."""

    def __init__(self, point_id: str, moisture: float) -> None:
        self.point_id = point_id
        if not 0.0 <= moisture <= 1.0:
            raise ValueError(f"Moisture value {moisture} out of range [0.0, 1.0]")
        self.moisture = moisture  # 0.0-1.0

    def __repr__(self) -> str:
        return f"SensorState(point_id={self.point_id!r}, moisture={self.moisture:.3f})"

    def __str__(self) -> str:
        return f"{self.point_id}: {self.moisture:.1%}"
