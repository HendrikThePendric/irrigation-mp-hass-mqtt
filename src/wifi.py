from network import WLAN, STA_IF
from rp2 import country
from time import sleep
from config import NetworkConfig
from logger import Logger


def connect_to_wifi(config: NetworkConfig, logger: Logger) -> None:
    country("nl")
    wlan = WLAN(STA_IF)
    elapsed_time = 0

    wlan.active(True)
    wlan.connect(config.wifi_ssid, config.wifi_password)

    while elapsed_time <= 30:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        logger.log(f"Connecting to WIFI ({elapsed_time}s)")
        elapsed_time += 1
        sleep(1)

    if wlan.status() != 3:
        raise RuntimeError("WIFI connection failed")
    else:
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
