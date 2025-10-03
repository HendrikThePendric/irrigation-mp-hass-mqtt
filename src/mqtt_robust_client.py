from umqtt.simple import MQTTClient
from machine import reset
from time import sleep
from logger import Logger

MAX_RETRIES = 10


class MQTTRobustClient(MQTTClient):
    """MQTT Client with retry/reconnect/restart pattern"""
    
    def __init__(self, client_id, server, port=0, user=None, password=None, 
                 keepalive=0, ssl=None, ssl_params={}, logger=None, connect_callback=None,
                 max_retry_time=30, retry_delay=2):
        super().__init__(client_id, server, port, user, password, keepalive, ssl, ssl_params)
        self._logger = logger
        self._connect_callback = connect_callback  # Callback to handle reconnection setup
        self._max_retry_time = max_retry_time
        self._retry_delay = retry_delay
        
    def publish(self, topic, msg, retain=False, qos=0):
        """Publish with retry/reconnect/restart pattern"""
        def _do_publish():
            return super(MQTTRobustClient, self).publish(topic, msg, retain, qos)
        return self._with_retry_pattern(_do_publish, f"publish to {topic} (QoS{qos})")
    
    def subscribe(self, topic, qos=0):
        """Subscribe with retry/reconnect/restart pattern"""
        def _do_subscribe():
            return super(MQTTRobustClient, self).subscribe(topic, qos)
        return self._with_retry_pattern(_do_subscribe, f"subscribe to {topic}")
        
    def check_msg(self):
        """Check messages with retry/reconnect/restart pattern"""
        def _do_check_msg():
            return super(MQTTRobustClient, self).check_msg()
        return self._with_retry_pattern(_do_check_msg, "check_msg")
    
    def connect(self, clean_session=True, timeout=None, lwt_topic=None, lwt_msg=None, lwt_retain=False, lwt_qos=0):
        """Connect with retry logic"""
        retry_time = 0
        connected = False
        
        while not connected and retry_time <= self._max_retry_time:
            try:
                if lwt_topic:
                    self.set_last_will(lwt_topic, lwt_msg, lwt_retain, lwt_qos)
                super().connect(clean_session, timeout)
                connected = True
            except OSError as e:
                sleep(self._retry_delay)
                retry_time += self._retry_delay
                if self._logger:
                    self._logger.log(f"Trying to connect to MQTT Broker ({retry_time}s)")

        if not connected:
            if self._logger:
                self._logger.log("Connection to MQTT Broker failed, going to reset")
            reset()

        return connected
    
    def _with_retry_pattern(self, operation, operation_name):
        """Execute operation with retry/reconnect/restart pattern"""
        
        for attempt in range(MAX_RETRIES):
            try:
                return operation()
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    if self._logger:
                        self._logger.log(f"MQTT {operation_name} failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}, attempting reconnect")
                    self._reconnect()
                    sleep(1)  # Brief delay before retry
                else:
                    if self._logger:
                        self._logger.log(f"MQTT {operation_name} failed after {MAX_RETRIES} attempts: {e}, restarting device")
                    reset()
    
    def _reconnect(self):
        """Reconnect to MQTT broker"""
        try:
            # Don't explicitly disconnect - just reconnect directly
            # This might be more transparent to HASS
            try:
                # Simple reconnect without retries (we're already in retry logic)
                super().connect()
            except Exception as e:
                # If direct reconnect fails, try explicit disconnect first
                try:
                    self.disconnect()
                except:
                    pass  # Ignore disconnect errors
                super().connect()
            
            # Call callback for post-connection setup (like availability publishing)
            if self._connect_callback:
                self._connect_callback()
        except Exception as e:
            # Don't re-raise - let the retry logic handle the failure
            # The next attempt will try the operation again
            if self._logger:
                self._logger.log(f"Reconnection failed: {e}")
            # Return normally - reconnection failed but let retry logic continue
