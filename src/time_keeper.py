import ntptime
from machine import RTC, Timer
import datetime
import logger as LoggerType


class TimeKeeper:
    def __init__(self, sync_interval=7200, retry_interval=60):
        self._rtc: RTC = RTC()
        self._sync_timer: Timer = Timer(-1)
        self._sync_interval: int = sync_interval * 1000  # Convert to milliseconds
        self._retry_interval: int = retry_interval * 1000
        self._has_synced: bool = False  # Track first successful sync
        self._logger: LoggerType.Logger
        ntptime.host = "nl.pool.ntp.org"

    def initialize_ntp_synchronization(self, logger: LoggerType.Logger):
        """Start NTP sync with 2-hour default interval and 1-minute retries"""
        self._logger = logger
        self._sync_ntp(None)

    def get_current_cet_datetime_str(self):
        """Return formatted CET string or empty if not synced yet"""
        if not self._has_synced:
            return ""

        u = self._get_utc_datetime()
        c = self._utc_to_cet(u)
        return (
            f"{c.year}/{c.month:02}/{c.day:02}-{c.hour:02}:{c.minute:02}:{c.second:02}"
        )

    def _sync_ntp(self, _):
        """Internal sync handler with success tracking"""
        try:
            ntptime.settime()
            msg = (
                "Initial NPT sync successful"
                if not self._has_synced
                else "NPT sync successful"
            )
            self._has_synced = True  # Flag first successful sync
            self._logger.log(msg)
            self._schedule_normal_sync()
        except Exception as e:
            self._logger.log(f"NTP sync failed: {e}")
            self._schedule_retry()

    def _schedule_normal_sync(self):
        """2-hour sync interval"""
        self._sync_timer.init(
            period=self._sync_interval, mode=Timer.ONE_SHOT, callback=self._sync_ntp
        )

    def _schedule_retry(self):
        """1-minute retry interval on failure"""
        self._sync_timer.init(
            period=self._retry_interval, mode=Timer.ONE_SHOT, callback=self._sync_ntp
        )

    def _get_utc_datetime(self):
        """Get current UTC time from RTC"""
        t = self._rtc.datetime()
        return datetime.datetime(t[0], t[1], t[2], t[4], t[5], t[6])

    def _utc_to_cet(self, utc_time):
        """DST-aware UTC to CET conversion"""
        year = utc_time.year

        def last_sunday(month):
            last_day = datetime.date(year, month, 31 if month in [3, 10] else 30)
            return last_day - datetime.timedelta(days=(last_day.weekday() + 1) % 7)

        dst_start = datetime.datetime.combine(last_sunday(3), datetime.time(1, 0))
        dst_end = datetime.datetime.combine(last_sunday(10), datetime.time(1, 0))

        if dst_start <= utc_time < dst_end:
            return utc_time + datetime.timedelta(hours=2)
        return utc_time + datetime.timedelta(hours=1)
