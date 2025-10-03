from machine import Timer, reset
from time import ticks_ms
from logger import Logger
from mqtt_robust_client import MQTTRobustClient

# Health check interval in milliseconds (2 minutes)
HEALTH_CHECK_INTERVAL = 120_000
# HEALTH_CHECK_INTERVAL = 5_000 # 5 seconds


class HealthMonitor:
    """Monitors MQTT connection health by sending periodic QoS1 messages."""
    
    def __init__(self, mqtt_client: MQTTRobustClient, station_id: str, logger: Logger) -> None:
        self._client = mqtt_client
        self._logger = logger
        self._station_id = station_id
        self._health_timer = Timer(-1)
        self._pending_health_check = False
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
        
        # Send health check message with QoS1
        try:
            health_payload = f"health_check_{current_time}"
            
            # Publish with specialized health check method - QoS1 with 3 attempts and simple reconnect
            # This will raise exception if no PUBACK after 3 attempts with reconnection retries
            self._client.publish_health_message(self._health_topic, health_payload)
            
            # If we reach here, the QoS1 PUBACK was received successfully
            self._logger.log(f"Health check acknowledged: {health_payload}")
            
        except OSError as e:
            # Network error during publish - will be raised by publish_health_message() after retry attempts
            self._logger.log(f"Health check failed after all retries: {e}")
            self._logger.log("Resetting device for recovery...")
            reset()
            
        self._pending_health_check = False
        
    def _set_pending_health_check(self, _=None) -> None:
        """Set the pending health check flag. Called by timer."""
        self._pending_health_check = True