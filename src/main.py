from machine import reset, Pin
from time import sleep, ticks_ms
from mqtt_hass_manager import MqttHassManager
from irrigation_station import IrrigationStation
from logger import Logger
from config import Config
from time_keeper import TimeKeeper
from wifi_manager import WiFiManager
from system_monitor import SystemMonitor
import gc

PRINT_LOGS = True

if PRINT_LOGS:
    # Delay initialization for a bit, to ensure
    # `mpremote connect` has completed. This
    # guarrantees that all log statement are going
    # to be visible
    sleep(2)

def main() -> None:
    # Initialize all components
    logger = Logger(PRINT_LOGS)
    time_keeper = TimeKeeper(logger)
    config = Config("./config.json")
    station = IrrigationStation(config, logger)
    wifi_manager = WiFiManager(config.network, logger)
    mqtt_manager = MqttHassManager(config, logger, station)
    
    # Setup components
    logger.log(str(config))
    wifi_manager.setup()
    time_keeper.initialize_ntp_synchronization()
    logger.enable_timestamp_prefix(time_keeper.get_current_cet_datetime_str)
    mqtt_manager.setup()
    system_monitor = SystemMonitor(logger)
    
    # LED for visual feedback
    onboard_led = Pin("LED", Pin.OUT)
    
    try:
        while True:
            system_monitor.loop_started()
            wifi_manager.handle_pending_connection_check()
            mqtt_manager.check_msg()
            time_keeper.handle_pending_ntp_sync()
            mqtt_manager.handle_pending_messages()
            # Toggle LED every tick
            onboard_led.toggle()
            system_monitor.loop_ended()

            sleep(1)
    except Exception as e:
        logger.log(f"Exception in main loop: {e}")
        reset()


if __name__ == "__main__":
    main()
