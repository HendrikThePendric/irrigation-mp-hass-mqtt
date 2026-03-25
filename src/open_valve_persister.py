"""Open valve persistence for irrigation system.

Persists the currently open valve to disk so state can be restored after restart.
"""

from json import dump, loads
from os import remove
import time
from typing import Any, Dict

from logger import Logger
from irrigation_states import ValveState
from valve import Valve


class OpenValvePersister:
    """Read/write open valve state to ./valve_state.json"""

    FILE_PATH = "./valve_state.json"
    MAX_RECOVERY_ATTEMPTS = 3

    def __init__(self, config, logger: Logger) -> None:
        """Initialize open valve store.

        Args:
            config: Config instance containing max_valve_open_time
            logger: Logger instance for error reporting
        """
        self._logger = logger
        self._max_valve_open_time = config.max_valve_open_time

    def _validate_and_get_data(
        self, skip_recovery_limit_check: bool = False
    ) -> Dict[str, Any] | None:
        """Validate valve state file and return data dict if valid, None otherwise.

        Args:
            skip_recovery_limit_check: If True, skip checking recovery_count >= MAX_RECOVERY_ATTEMPTS
                                      (used by increment_opened_valve_recovery_count)

        Returns:
            Validated data dict with keys: point_id, opened_timestamp, recovery_count
            or None if validation fails (file deleted on failure)
        """
        # Read file
        data = self._read_file()
        if data is None:
            return None

        # Get values
        point_id = data.get("point_id")
        opened_timestamp = data.get("opened_timestamp")
        recovery_count = data.get("recovery_count", 0)

        # Validate point_id
        if not isinstance(point_id, str) or not point_id:
            self._logger.log(f"Invalid point_id in valve state file: {point_id!r}")
            self._delete_file_silently()
            return None

        # Validate opened_timestamp
        if not isinstance(opened_timestamp, (int, float)):
            self._logger.log(
                f"Invalid opened_timestamp in valve state file: {opened_timestamp!r}"
            )
            self._delete_file_silently()
            return None

        # Validate recovery_count
        if not isinstance(recovery_count, int) or recovery_count < 0:
            self._logger.log(
                f"Invalid recovery_count in valve state file: {recovery_count!r}"
            )
            self._delete_file_silently()
            return None

        # Check timestamp range
        current_time = time.time()
        max_allowed_age = current_time - self._max_valve_open_time

        if not (max_allowed_age <= opened_timestamp <= current_time):
            self._logger.log(
                f"Persisted valve {point_id} timestamp {opened_timestamp} out of valid range "
                f"(must be between {max_allowed_age} and {current_time})"
            )
            self._delete_file_silently()
            return None

        # Check recovery attempts limit (unless skipped)
        if (
            not skip_recovery_limit_check
            and recovery_count >= self.MAX_RECOVERY_ATTEMPTS
        ):
            self._logger.log(
                f"Valve {point_id} recovery attempts exceeded ({recovery_count} >= {self.MAX_RECOVERY_ATTEMPTS}), "
                "not restoring. File deleted."
            )
            self._delete_file_silently()
            return None

        # Ensure recovery_count key exists in returned dict
        data["recovery_count"] = recovery_count

        # Return validated data
        return data

    def get(self) -> ValveState | None:
        """Return ValveState for valid open valve, or None.

        Validation logic:
        1. Read file, return None if missing or corrupted
        2. Validate point_id is non-empty string
        3. Validate opened_timestamp is int/float
        4. Check: current_time - max_valve_open_time <= opened_timestamp <= current_time
        5. Check recovery_count < MAX_RECOVERY_ATTEMPTS (default 0 if missing)
        6. Return ValveState if valid, None otherwise (delete file on any error)
        """
        data = self._validate_and_get_data(skip_recovery_limit_check=False)
        if data is None:
            return None

        # Valid - return ValveState with OPEN state
        return ValveState(data["point_id"], Valve.STATE_OPEN)

    def increment_opened_valve_recovery_count(self) -> None:
        """Increment recovery count after successful valve restoration.

        Should be called after get() returns a valid ValveState and the valve
        has been successfully restored/opened.
        """
        # Use shared validation but skip recovery limit check (we're about to increment)
        data = self._validate_and_get_data(skip_recovery_limit_check=True)
        if data is None:
            self._logger.log(
                "Cannot increment recovery count: valve state file missing or corrupted"
            )
            return

        point_id = data["point_id"]
        recovery_count = data["recovery_count"]

        # Increment recovery count
        data["recovery_count"] = recovery_count + 1

        # Check if we're exceeding limit (shouldn't happen if get() validated)
        if data["recovery_count"] > self.MAX_RECOVERY_ATTEMPTS:
            self._logger.log(
                f"Warning: valve {point_id} recovery count {data['recovery_count']} exceeds "
                f"limit {self.MAX_RECOVERY_ATTEMPTS} after increment"
            )

        # Write updated file
        try:
            with open(self.FILE_PATH, "w") as f:
                dump(data, f)
        except Exception as e:
            self._logger.log(
                f"Failed to increment recovery count in valve state file: {e}"
            )

    def set(self, point_id: str) -> None:
        """Persist open valve with current timestamp.

        Args:
            point_id: ID of open valve
        """
        data = {
            "point_id": point_id,
            "opened_timestamp": time.time(),
            "recovery_count": 0,
        }

        try:
            with open(self.FILE_PATH, "w") as f:
                dump(data, f)
        except Exception as e:
            self._logger.log(f"Failed to write valve state file: {e}")

    def clear(self) -> None:
        """Delete persistence file."""
        self._delete_file_silently()

    def _read_file(self) -> Dict[str, Any] | None:
        """Read persisted valve state file.

        Returns:
            Dictionary with keys:
            - point_id: str - ID of open valve
            - opened_timestamp: float - Unix timestamp when valve was opened
            - recovery_count: int - Number of successful restoration attempts (default 0)
            Returns None if file doesn't exist or is corrupted.
        """
        try:
            with open(self.FILE_PATH, "r") as f:
                data = loads(f.read())
            return data
        except Exception:
            # File doesn't exist, cannot be read, or JSON is invalid
            return None

    def _delete_file_silently(self) -> None:
        """Delete valve state file, ignoring any errors."""
        try:
            remove(self.FILE_PATH)
        except OSError:
            # File doesn't exist or cannot be deleted - ignore
            pass
        except Exception as e:
            self._logger.log(f"Failed to delete valve state file: {e}")
