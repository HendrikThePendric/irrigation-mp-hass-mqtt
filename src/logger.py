from typing import Callable
from os import rename, stat, sync
import sys


LOG_FILE_PATH = "./log.txt"
LOG_FILE_PATH_OLD = "./log-old.txt"
# Storage capicity is 4MB, 4194304 bytes
# Max capacity dedicated to logging 25%
# This is distributed over 2 files
MAX_FILE_SIZE = int((4194304 * 0.25) / 2)


def _return_empty_str() -> str:
    return ""


class Logger:
    def __init__(self, should_print: bool = False) -> None:
        self._should_print: bool = should_print
        self._get_timestamp: Callable[[], str] = _return_empty_str

    def log(self, msg: str) -> None:
        """Log a message to file and optionally print it."""
        log_msg: str = self._format_msg(msg)

        if self._should_print:
            print(log_msg)

        with open(LOG_FILE_PATH, "a") as curr_file:
            curr_file.write(log_msg + "\n")
            sync()

        self._rotate_file_if_needed()

    def enable_timestamp_prefix(self, get_timestamp: Callable[[], str]) -> None:
        """Enable timestamp prefix for log messages."""
        self._get_timestamp = get_timestamp

    def _format_msg(self, msg: str) -> str:
        """Format a log message with optional timestamp."""
        is_single_line: bool = msg.count("\n") == 0
        timestamp: str = self._get_timestamp()

        if is_single_line:
            if timestamp == "":
                return msg
            else:
                return f"{timestamp} {msg}"
        else:
            return f"===={timestamp}====\n{msg}\n-----------------------"

    def _rotate_file_if_needed(self) -> None:
        """Rotate log file if it exceeds the maximum allowed size."""
        try:
            file_size_bytes: int = stat(LOG_FILE_PATH)[6]
            if file_size_bytes >= MAX_FILE_SIZE:
                rename(LOG_FILE_PATH, LOG_FILE_PATH_OLD)
                # Avoid recursion: write directly to file instead of calling self.log
                msg = self._format_msg("Rotated log file")
                with open(LOG_FILE_PATH, "a") as curr_file:
                    curr_file.write(msg + "\n")
                    sync()
                if self._should_print:
                    print(msg)
        except OSError as e:
            print(
                self._format_msg(
                    f"Log file rotation failed, will try again on next log: {e}"
                )
            )
