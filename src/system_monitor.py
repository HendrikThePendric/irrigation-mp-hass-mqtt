from time import ticks_ms
import gc

class SystemMonitor:
    def __init__(self, logger):
        self._logger = logger
        self._mem_before = None
        self._mem_after = None
        self._loop_start = None
        self._loop_end = None
        self._exception = None
        self._loop_counter = 0

    def loop_started(self):
        gc.collect()
        self._mem_before = gc.mem_free()
        self._loop_start = ticks_ms()
        self._exception = None
        self._loop_counter += 1

    def loop_ended(self, exception=None):
        gc.collect()
        self._mem_after = gc.mem_free()
        self._loop_end = ticks_ms()
        self._exception = exception
        duration_ms = self._loop_end - self._loop_start if self._loop_start is not None else None
        duration_s = round(duration_ms / 1000, 2) if duration_ms is not None else None
        mem_delta = self._mem_after - self._mem_before if self._mem_before is not None else None
        msg = (
            f"loop={self._loop_counter} "
            f"duration={duration_s}s "
            f"mem_before={self._mem_before} "
            f"mem_after={self._mem_after} "
            f"mem_delta={mem_delta}"
        )
        if exception:
            msg += f" exception={exception}"
        self._logger.log(msg)
