from machine import reset, Timer
from time import sleep
from network import WLAN, STA_IF
from rp2 import country
from config import NetworkConfig
from logger import Logger

MAX_RETRY_TIME = 30  # seconds
RETRY_DELAY = 2  # seconds
CHECK_INTERVAL_MS = 600_000  # milliseconds (10 minutes)


class WiFiManager:
    def __init__(self, config: NetworkConfig, logger: Logger) -> None:
        self._config = config
        self._logger = logger
        self._wlan = WLAN(STA_IF)
        self._retry_time = 0
        self._timer = Timer(-1)
        self._pending_connection_check = False

        country("nl")

    def setup(self) -> None:
        self._wlan.active(True)
        self._connect()  # Attempt to connect immediately
        self._start_periodic_check()

    def handle_pending_connection_check(self) -> None:
        """Handle pending connection check if flagged."""
        if not self._pending_connection_check:
            return
        self._pending_connection_check = False
        self._check_connection()

    def _connect(self) -> None:
        """Attempt to connect to the WiFi network."""
        self._logger.log("Attempting to connect to WiFi...")
        self._wlan.connect(self._config.wifi_ssid, self._config.wifi_password)
        self._retry_time = 0

        while self._retry_time <= MAX_RETRY_TIME:
            if self._wlan.status() < 0 or self._wlan.status() >= 3:
                break
            self._logger.log(f"Trying to connect to WiFi ({self._retry_time}s)")
            self._retry_time += RETRY_DELAY
            sleep(RETRY_DELAY)

        if self._wlan.status() == 3:
            self._log_connection_info()
        else:
            self._logger.log("WiFi connection failed, going to reset")
            reset()

    def _log_connection_info(self) -> None:
        """Log the WiFi connection details."""
        info = self._wlan.ifconfig()
        message = "\n".join(
            [
                f"Connected to WiFi network {self._config.wifi_ssid}:",
                f"IP:          {info[0]}",
                f"Subnet mask: {info[1]}",
                f"Gateway:     {info[2]}",
                f"Primary DNS: {info[3]}",
            ]
        )
        self._logger.log(message)

    def _check_connection(self) -> None:
        """Check the WiFi connection and reconnect if needed."""
        if not self._wlan.isconnected():
            self._logger.log("WiFi connection lost, attempting to reconnect...")
            self._connect()

    def _start_periodic_check(self) -> None:
        """Start a timer to periodically check the WiFi connection."""
        self._timer.init(
            period=CHECK_INTERVAL_MS,
            mode=Timer.PERIODIC,
            callback=self._set_pending_connection_check,
        )

    def _set_pending_connection_check(self, _=None) -> None:
        """Set the flag to indicate a pending connection check."""
        self._pending_connection_check = True
