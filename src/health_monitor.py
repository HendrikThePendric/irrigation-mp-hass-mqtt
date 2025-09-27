from machine import Timer, reset
from time import ticks_ms
from umqtt.robust import MQTTClient
from logger import Logger

# Health check interval in milliseconds (2 minutes)
HEALTH_CHECK_INTERVAL = 120_000
# Timeout for waiting for QoS1 acknowledgment in milliseconds (30 seconds)
HEALTH_ACK_TIMEOUT = 30_000


class HealthMonitor:
    """Monitors MQTT connection health by sending periodic QoS1 messages."""
    
    def __init__(self, mqtt_client: MQTTClient, station_id: str, logger: Logger) -> None:
        self._client = mqtt_client
        self._logger = logger
        self._station_id = station_id
        self._health_timer = Timer(-1)
        self._pending_health_check = False
        self._last_health_check_time = 0
        self._health_topic = f"irrigation/{station_id}/health"
        
    def start_health_monitoring(self) -> None:
        """Start the periodic health check timer."""
        self._health_timer.init(
            period=HEALTH_CHECK_INTERVAL,
            mode=Timer.PERIODIC,
            callback=self._set_pending_health_check,
        )
        self._logger.log("Health monitoring started")
        
    def handle_pending_publish(self) -> None:
        """Handle pending health check publish. Should be called by MqttClient.handle_pending_publish()."""
        if not self._pending_health_check:
            return
            
        current_time = ticks_ms()
        
        # Check if previous health check timed out (no acknowledgment received)
        if (self._last_health_check_time > 0 and 
            (current_time - self._last_health_check_time) > HEALTH_ACK_TIMEOUT):
            self._logger.log("Health check acknowledgment timeout, restarting device")
            reset()
        
        # Send health check message with QoS1
        try:
            health_payload = f"health_check_{current_time}"
            
            # Publish with QoS1 - this will block until PUBACK is received or timeout
            # If the broker doesn't acknowledge within the socket timeout, this will raise an exception
            self._client.publish(self._health_topic, health_payload, qos=1)
            
            # If we reach here, the QoS1 PUBACK was received successfully
            self._last_health_check_time = current_time
            self._logger.log(f"Health check acknowledged: {health_payload}")
            
        except Exception as e:
            self._logger.log(f"Health check failed (no broker acknowledgment): {e}, restarting device")
            reset()
            
        self._pending_health_check = False
        
    def _set_pending_health_check(self, _=None) -> None:
        """Set the pending health check flag. Called by timer."""
        self._pending_health_check = True