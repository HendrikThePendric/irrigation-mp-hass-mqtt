from config import Config
from logger import Logger
from machine import reset
from network import WLAN, STA_IF
from rp2 import country
from ssl import SSLContext, PROTOCOL_TLS_CLIENT
from time import sleep
from umqtt.simple import MQTTClient

MAX_RETRY_TIME = 30
RETRY_DELAY = 2
CA_PATH = "./ca_crt.der"
CERT_PATH = "./irrigationbackyard_crt.der"
KEY_PATH = "./irrigationbackyard_key.der"
PORT = 8883
KEEPALIVE = 60

# See umqtt.robust for inspiration reg. retries etc
# https://github.com/micropython/micropython-lib/blob/master/micropython/umqtt.robust/umqtt/robust.py


class HassMqttClient:
    def __init__(self, config: Config, logger: Logger) -> None:
        self._config = config
        self._logger = logger
        self._wlan = WLAN(STA_IF)
        self._retry_time = 0
        self._client = None
        country("nl")

    def wifi_connnect(self) -> None:
        self._wlan.active(True)
        self._wlan.connect(
            self._config.network.wifi_ssid, self._config.network.wifi_password
        )

        while self._retry_time <= MAX_RETRY_TIME:
            if self._wlan.status() < 0 or self._wlan.status() >= 3:
                break
            self._logger.log(f"Trying to connect to WIFI ({self._retry_time}s)")
            self._retry_time += RETRY_DELAY
            sleep(RETRY_DELAY)

        if self._wlan.status() != 3:
            self._logger.log("WIFI connection failed, going to reset")
            reset()

        else:
            self._retry_time = 0
            info = self._wlan.ifconfig()
            message = "\n".join(
                [
                    f"Connected to WIFI network {self._config.network.wifi_ssid}:",
                    f"IP:          {info[0]}",
                    f"Subnet mask: {info[1]}",
                    f"Gateway:     {info[2]}",
                    f"Primary DNS: {info[3]}",
                ]
            )
            self._logger.log(message)

    def mqtt_connect(self) -> MQTTClient:
        ssl_context = SSLContext(PROTOCOL_TLS_CLIENT)
        ssl_context.load_verify_locations(cafile=CA_PATH)
        ssl_context.load_cert_chain(certfile=CERT_PATH, keyfile=KEY_PATH)
        self._client = MQTTClient(
            client_id=self._config.station_mqtt_id,
            server=self._config.network.mqtt_broker_ip,
            port=PORT,
            keepalive=KEEPALIVE,
            ssl=ssl_context,
        )
        connected = False
        while not connected and self._retry_time <= MAX_RETRY_TIME:
            try:
                self._client.connect()
                connected = True
            except OSError:
                sleep(RETRY_DELAY)
                self._retry_time += RETRY_DELAY
                self._logger.log(
                    f"Trying to connect to MQTT Broker ({self._retry_time}s)"
                )

        if not connected:
            self._logger.log("Connection to MQTT Broker failed, going to reset")
            reset()

        self._retry_time = 0
        message = "\n".join(
            [
                "Connected to MQTT Broker:",
                f"Address:   {self._config.network.mqtt_broker_ip}:{PORT}",
                f"Client ID: {self._config.station_mqtt_id}",
            ]
        )
        self._logger.log(message)
        return self._client
