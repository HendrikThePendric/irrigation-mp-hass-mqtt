from umqtt.simple import MQTTClient
from machine import reset
from time import sleep
from logger import Logger


class MQTTRobustClient(MQTTClient):
    """MQTT Client based on umqtt.robust with threading-safe callback pattern"""
    
    DELAY = 2
    DEBUG = False
    HEALTH_CHECK_QOS = 1
    HEALTH_CHECK_ATTEMPTS = 10

    def __init__(self, client_id, server, port=0, user=None, password=None, 
                 keepalive=0, ssl=None, ssl_params={}, logger=None, on_reconnect_callback=None):
        super().__init__(client_id, server, port, user, password, keepalive, ssl, ssl_params)
        self._logger = logger
        self._on_reconnect_callback = on_reconnect_callback

    def delay(self, i):
        sleep(self.DELAY)

    def log(self, in_reconnect, e):
        if self._logger:
            if in_reconnect:
                self._logger.log(f"mqtt reconnect: {e}")
            else:
                self._logger.log(f"mqtt: {e}")

    def reconnect(self):
        i = 0
        while 1:
            try:
                result = super().connect(False)  # clean_session=False like umqtt.robust
                # Call callback to toggle boolean flag (light work only)
                if self._on_reconnect_callback:
                    self._on_reconnect_callback()
                return result
            except OSError as e:
                # Log on first attempt and then every 5 attempts
                if i == 0 or i % 5 == 0:
                    self.log(True, e)
                i += 1
                self.delay(i)

    def publish(self, topic, msg, retain=False, qos=0):
        """Publish with infinite retry like umqtt.robust"""
        while 1:
            try:
                return super().publish(topic, msg, retain, qos)
            except OSError as e:
                self.log(False, e)
            self.reconnect()

    def publish_health_message(self, topic, msg):
        """Specialized health check publish with simple reconnect and finite attempts"""
        for attempt in range(self.HEALTH_CHECK_ATTEMPTS):
            try:
                return super().publish(topic, msg, False, self.HEALTH_CHECK_QOS)
            except OSError as e:
                self.log(False, e)
                if attempt < self.HEALTH_CHECK_ATTEMPTS - 1:  # Not last attempt
                    try:
                        super().connect(False)  # Simple reconnect, no callback
                    except OSError:
                        continue  # Try next attempt
        raise OSError("Health check publish failed after all attempts")

    def wait_msg(self):
        """Wait for message with infinite retry like umqtt.robust"""
        while 1:
            try:
                return super().wait_msg()
            except OSError as e:
                self.log(False, e)
            self.reconnect()

    def check_msg(self, attempts=2):
        """Check messages like umqtt.robust - limited attempts"""
        while attempts:
            self.sock.setblocking(False)
            try:
                return super().wait_msg()
            except OSError as e:
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
