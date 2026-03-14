import ntptime
from machine import RTC, reset
import datetime
from time import sleep
from logger import Logger

INITIAL_RETRY_DELAY = 2
MAX_INITIAL_RETRY_TIME = 30


class TimeKeeper:
    def __init__(
        self, logger: Logger, sync_interval: int = 7200, retry_interval: int = 60
    ) -> None:
        self._rtc: RTC = RTC()
        self._sync_interval: int = sync_interval
        self._retry_interval: int = retry_interval
        self._logger: Logger = logger
        ntptime.host = "nl.pool.ntp.org"

    def initialize_ntp_synchronization(self) -> None:
        """Start NTP sync with 2-hour default interval and 1-minute retries"""
        # Initial sync should be a blocking operation. Time must be accurate
        synced = False
        retry_time = 0
        while not synced and retry_time <= MAX_INITIAL_RETRY_TIME:
            try:
                ntptime.settime()
                self._logger.log("Initial NTP sync successful")
                synced = True
            except Exception:
                sleep(INITIAL_RETRY_DELAY)
                retry_time += INITIAL_RETRY_DELAY
                self._logger.log(f"Trying to sync NTP ({retry_time}s)")

        if not synced:
            self._logger.log("Failed to sync NTP, resetting")
            reset()

    def sync_time(self) -> bool:
        """Attempt to sync time with NTP server."""
        try:
            ntptime.settime()
            self._logger.log("NTP sync successful")
            return True
        except OSError:
            self._logger.log(f"NTP sync failed, will retry in {self._retry_interval}s")
            return False

    def get_current_cet_datetime_str(self) -> str:
        """Return formatted CET string"""
        u = self._get_utc_datetime()
        c = self._utc_to_cet(u)
        return (
            f"{c.year}/{c.month:02}/{c.day:02}-{c.hour:02}:{c.minute:02}:{c.second:02}"
        )

    # Removed duplicate/legacy _sync_ntp, _schedule_normal_sync, _schedule_retry methods

    def _get_utc_datetime(self) -> datetime.datetime:
        """Get current UTC time from RTC"""
        t = self._rtc.datetime()
        return datetime.datetime(t[0], t[1], t[2], t[4], t[5], t[6])

    def _utc_to_cet(self, utc_time: datetime.datetime) -> datetime.datetime:
        """DST-aware UTC to CET conversion (last Sunday of March to last Sunday of October)"""
        year = utc_time.year
        # Last Sunday of March
        march = datetime.date(year, 3, 31)
        last_sunday_march = march - datetime.timedelta(
            days=march.weekday() + 1 if march.weekday() != 6 else 0
        )
        dst_start = datetime.datetime.combine(last_sunday_march, datetime.time(1, 0))
        # Last Sunday of October
        october = datetime.date(year, 10, 31)
        last_sunday_october = october - datetime.timedelta(
            days=october.weekday() + 1 if october.weekday() != 6 else 0
        )
        dst_end = datetime.datetime.combine(last_sunday_october, datetime.time(1, 0))
        if dst_start <= utc_time < dst_end:
            return utc_time + datetime.timedelta(hours=2)
        return utc_time + datetime.timedelta(hours=1)
