from machine import reset
from network import WLAN, STA_IF
from rp2 import country
from time import sleep
from config import NetworkConfig
from logger import Logger

MAX_RETRY_TIME = 30
RETRY_DELAY = 2


def wifi_connect(config: NetworkConfig, logger: Logger) -> None:
    country("nl")
    wlan = WLAN(STA_IF)
    wlan.active(True)
    wlan.connect(config.wifi_ssid, config.wifi_password)
    retry_time = 0

    while retry_time <= MAX_RETRY_TIME:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        logger.log(f"Trying to connect to WIFI ({retry_time}s)")
        retry_time += RETRY_DELAY
        sleep(RETRY_DELAY)

    if wlan.status() != 3:
        logger.log("WIFI connection failed, going to reset")
        reset()
    else:
        retry_time = 0
        info = wlan.ifconfig()
        message = "\n".join(
            [
                f"Connected to WIFI network {config.wifi_ssid}:",
                f"IP:          {info[0]}",
                f"Subnet mask: {info[1]}",
                f"Gateway:     {info[2]}",
                f"Primary DNS: {info[3]}",
            ]
        )
        logger.log(message)
