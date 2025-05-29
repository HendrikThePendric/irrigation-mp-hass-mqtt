from machine import Timer
from os import rename, stat
from time_keeper import TimeKeeper


LOG_FILE_PATH = "./log.txt"
LOG_FILE_PATH_OLD = "./log-old.txt"
# Storage capicity is 4MB, 4194304 bytes
# Max capicity dedicated to logging 25%
# This is distrubuted over 2 files
# MAX_FILE_SIZE = (4194304 * 0.25) / 2
MAX_FILE_SIZE = 500


class Logger:
    def __init__(self, time_keeper: TimeKeeper, should_print=False) -> None:
        self._tk = time_keeper
        self._should_print = should_print
        self._retry_timer: Timer = Timer(-1)

    def log(self, msg: str) -> None:
        dt_str = self._tk.get_current_cet_datetime_str()
        log_msg = (
            f"{dt_str} {msg}"
            if msg.count("\n") == 0
            else f"{dt_str}============\n{msg}\n-----------------------"
        )
        with open(LOG_FILE_PATH, "a") as curr_file:
            curr_file.write(log_msg + "\n")
            curr_file.close()

        if self._should_print:
            print(log_msg)

        self._rotate_file_if_needed()

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
            dt_str = self._tk.get_current_cet_datetime_str()

            def callback(_: Timer):
                self.log(f"Log file rotation failed at {dt_str}")

            self._retry_timer.init(mode=Timer.ONE_SHOT, period=500, callback=callback)
