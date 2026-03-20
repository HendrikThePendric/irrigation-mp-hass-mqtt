from time import sleep
from network import WLAN, STA_IF
from rp2 import country
from config import NetworkConfig
from logger import Logger

RETRY_DELAY = 2  # seconds


class WiFiManager:
    def __init__(self, config: NetworkConfig, logger: Logger) -> None:
        self._config = config
        self._logger = logger
        self._wlan = WLAN(STA_IF)
        self._retry_time = 0
        self._connected = False

        country("nl")

    def setup(self) -> None:
        self._wlan.active(True)
        self._connect()  # Attempt to connect immediately

    def check_connection(self) -> None:
        """Check WiFi connection and reconnect if needed."""
        if not self._wlan.isconnected():
            self._connected = False
            self._logger.log("WiFi connection lost, attempting to reconnect...")
            self._connect()

    def _connect(self) -> None:
        """Attempt to connect to the WiFi network."""
        self._logger.log("Attempting to connect to WiFi...")
        self._wlan.connect(self._config.wifi_ssid, self._config.wifi_password)
        self._retry_time = 0

        while True:
            if self._wlan.status() < 0 or self._wlan.status() >= 3:
                break
            self._logger.log(
                "Trying to connect to WiFi (" + str(self._retry_time) + "s)"
            )
            self._retry_time += RETRY_DELAY
            sleep(RETRY_DELAY)

        if self._wlan.status() == 3:
            self._connected = True
            self._log_connection_info()
        else:
            self._connected = False
            self._logger.log("WiFi connection failed")

    def _log_connection_info(self) -> None:
        """Log the WiFi connection details."""
        info = self._wlan.ifconfig()
        message = "\n".join(
            [
                "Connected to WiFi network " + self._config.wifi_ssid + ":",
                "IP:          " + info[0],
                "Subnet mask: " + info[1],
                "Gateway:     " + info[2],
                "Primary DNS: " + info[3],
            ]
        )
        self._logger.log(message)
