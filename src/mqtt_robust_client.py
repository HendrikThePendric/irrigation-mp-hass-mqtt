from umqtt.simple import MQTTClient
from machine import reset
from time import sleep
from logger import Logger


class MqttRobustClient(MQTTClient):
    """MQTT Client based on umqtt.robust with threading-safe callback pattern"""
    
    DELAY = 2
    DEBUG = False
    MAX_RECONNECT_FAILURES = 30
    MAX_MESSAGE_FAILURES = 10

    def __init__(self, client_id, server, port=0, user=None, password=None, 
                 keepalive=0, ssl=None, ssl_params={}, logger=None, on_reconnect_callback=None):
        super().__init__(client_id, server, port, user, password, keepalive, ssl, ssl_params)
        self._logger = logger
        self._on_reconnect_callback = on_reconnect_callback
        self._subsequent_message_failures = 0

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

        while reconnect_failures <= self.MAX_RECONNECT_FAILURES and self._subsequent_message_failures <= self.MAX_MESSAGE_FAILURES:
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
        if self._logger:
            self._logger.log(f"MQTT reconnect failed after {self.MAX_RECONNECT_FAILURES} of retries, resetting device")
        reset()

    def publish(self, topic, msg, retain=False, qos=0):
        """Publish with retry and reconnect until reconnect timeout expires"""
        while 1:
            try:
                result = super().publish(topic, msg, retain, qos)
                self._subsequent_message_failures = 0
                return result
            except OSError as e:
                self._subsequent_message_failures += 1
                self.log(False, e)
            self.reconnect()

    def wait_msg(self):
        """Wait for message with retry and reconnect until reconnect timeout expires"""
        while 1:
            try:
                result = super().wait_msg()
                self._subsequent_message_failures = 0
                return result
            except OSError as e:
                self._subsequent_message_failures += 1
                self.log(False, e)
            self.reconnect()

    def check_msg(self, attempts=2):
        """Check messages like umqtt.robust - limited attempts"""
        while attempts:
            self.sock.setblocking(False)
            try:
                result= super().wait_msg()
                self._subsequent_message_failures = 0
                return result
            except OSError as e:
                self._subsequent_message_failures += 1
                self.log(False, e)
            self.reconnect()
            attempts -= 1

    def connect(self, clean_session=True, timeout=None, lwt_topic=None, lwt_msg=None, lwt_retain=False, lwt_qos=0, max_retry_time=30):
        """Connect with LWT support and finite retry"""
        if lwt_topic:
            self.set_last_will(lwt_topic, lwt_msg, lwt_retain, lwt_qos)
        
        retry_time = 0
        i = 1
        while retry_time <= max_retry_time:
            try:
                return super().connect(clean_session, timeout)
            except OSError as e:
                self.log(True, e)
                self.delay(i)
                retry_time += i * self.DELAY
                i += 1
        
        # If we get here, connection failed completely
        if self._logger:
            self._logger.log("Connection to MQTT Broker failed, going to reset")
        reset()
