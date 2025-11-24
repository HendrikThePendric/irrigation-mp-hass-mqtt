from umqtt.simple import MQTTClient
from time import sleep
from logger import Logger


class MqttRobustClient(MQTTClient):
    """MQTT Client based on umqtt.robust with threading-safe callback pattern"""

    DELAY = 2
    DEBUG = False

    def __init__(
        self,
        client_id,
        server,
        port=0,
        user=None,
        password=None,
        keepalive=0,
        ssl=None,
        ssl_params={},
        logger: Logger | None = None,
        on_reconnect_callback=None,
    ):
        super().__init__(
            client_id, server, port, user, password, keepalive, ssl, ssl_params
        )
        self._logger = logger
        self._on_reconnect_callback = on_reconnect_callback

    def delay(self, i):
        multiplier = i if isinstance(i, int) and i > 0 else 1
        sleep(self.DELAY * multiplier)

    def log(self, in_reconnect, e):
        if self._logger:
            if in_reconnect:
                self._logger.log(f"mqtt reconnect: {e}")
            else:
                self._logger.log(f"mqtt: {e}")

    def reconnect(self):
        reconnect_failures = 0

        while True:
            try:
                result = super().connect(clean_session=False)
                # Call callback to toggle boolean flag (light work only)
                if self._on_reconnect_callback:
                    self._on_reconnect_callback()
                return result
            except OSError as e:
                reconnect_failures += 1
                # Log on first attempt and then every 5 attempts
                if reconnect_failures == 0 or reconnect_failures % 5 == 0:
                    self.log(True, e)
                self.delay(reconnect_failures)

    def publish(self, topic, msg, retain=False, qos=0):
        """Publish with retry and reconnect until reconnect timeout expires"""
        while 1:
            try:
                result = super().publish(topic, msg, retain, qos)
                return result
            except OSError as e:
                self.log(False, e)
            self.reconnect()

    def wait_msg(self):
        """Wait for message with retry and reconnect until reconnect timeout expires"""
        while 1:
            try:
                result = super().wait_msg()
                return result
            except OSError as e:
                self.log(False, e)
            self.reconnect()

    def check_msg(self, attempts=4):
        """Check messages like umqtt.robust - limited attempts"""
        while attempts:
            self.sock.setblocking(False)
            try:
                result = super().wait_msg()
                return result
            except OSError as e:
                self.log(False, e)
            self.reconnect()
            attempts -= 1

    def connect(
        self,
        clean_session=True,
        timeout=None,
        lwt_topic=None,
        lwt_msg=None,
        lwt_retain=False,
        lwt_qos=0,
    ):
        """Connect with LWT support and infinite retry"""
        if lwt_topic:
            self.set_last_will(lwt_topic, lwt_msg, lwt_retain, lwt_qos)

        i = 1
        while True:
            try:
                return super().connect(clean_session, timeout)
            except OSError as e:
                self.log(True, e)
                self.delay(i)
                i += 1
