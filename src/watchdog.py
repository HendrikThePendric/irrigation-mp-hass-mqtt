from machine import Timer, reset
from time import sleep
from logger import Logger


class Watchdog:
    def __init__(self, timeout_s: int, logger: Logger):
        self.timeout_ms = timeout_s * 1000
        self.logger = logger
        self.timer = Timer()
        self.timer.init(
            period=self.timeout_ms, mode=Timer.ONE_SHOT, callback=self._timeout_callback
        )
        self.logger.log(f"WatchDog initialized with timeout {timeout_s} s")

    def _timeout_callback(self, _):
        self.logger.log("WatchDog timeout occurred, restarting device")
        reset()

    def feed(self):
        self.timer.init(
            period=self.timeout_ms, mode=Timer.ONE_SHOT, callback=self._timeout_callback
        )
