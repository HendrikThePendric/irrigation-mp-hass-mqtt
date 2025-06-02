from typing import Callable
from machine import Timer
from os import rename, stat


LOG_FILE_PATH = "./log.txt"
LOG_FILE_PATH_OLD = "./log-old.txt"
# Storage capicity is 4MB, 4194304 bytes
# Max capicity dedicated to logging 25%
# This is distrubuted over 2 files
MAX_FILE_SIZE = (4194304 * 0.25) / 2


def _return_empty_str() -> str:
    return ""


class Logger:
    def __init__(self, should_print=False) -> None:
        self._should_print: bool = should_print
        self._retry_timer: Timer = Timer(-1)
        self._get_timestamp: Callable = _return_empty_str

    def log(self, msg: str) -> None:
        log_msg = self._format_msg(msg)
        with open(LOG_FILE_PATH, "a") as curr_file:
            curr_file.write(log_msg + "\n")
            curr_file.close()

        if self._should_print:
            print(log_msg)

        self._rotate_file_if_needed()

    def enable_timestamp_prefix(self, get_timestamp: Callable) -> None:
        self._get_timestamp = get_timestamp

    def _format_msg(self, msg: str) -> str:
        is_single_line = msg.count("\n") == 0
        timestamp = self._get_timestamp()

        if is_single_line:
            if timestamp == "":
                return msg
            else:
                return f"{timestamp} {msg}"
        else:
            return f"===={timestamp}====\n{msg}\n-----------------------"

    def _rotate_file_if_needed(self) -> None:
        try:
            file_size_bytes = stat(LOG_FILE_PATH)[6]

            if file_size_bytes >= MAX_FILE_SIZE:
                rename(LOG_FILE_PATH, LOG_FILE_PATH_OLD)
                self.log("Rotated log file")
        except Exception as e:
            print(e)
            # This sometimes happens it is not a big deal because
            # the file will become available again
            dt_str = self._get_timestamp()

            def callback(_: Timer):
                self.log(f"Log file rotation failed at {dt_str}")

            self._retry_timer.init(mode=Timer.ONE_SHOT, period=500, callback=callback)
