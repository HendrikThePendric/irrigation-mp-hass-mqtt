from machine import reset, Pin
from time import sleep
from mqtt_hass_manager import MqttHassManager
from irrigation_station import IrrigationStation
from logger import Logger
from watchdog import Watchdog
from config import Config
from time_keeper import TimeKeeper
from wifi_manager import WiFiManager
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
    watchdog = Watchdog(120, logger)
    time_keeper = TimeKeeper(logger)
    config = Config("./config.json")
    mqtt_manager = MqttHassManager(config, logger)
    station = IrrigationStation(config, logger)
    wifi_manager = WiFiManager(config.network, logger)

    # Setup components
    logger.log(str(config))
    wifi_manager.setup()
    time_keeper.initialize_ntp_synchronization()
    logger.enable_timestamp_prefix(time_keeper.get_current_cet_datetime_str)
    mqtt_manager.setup()

    # LED for visual feedback
    onboard_led = Pin("LED", Pin.OUT)

    loop_count = 0

    try:
        while True:
            # 1. Watchdog, wifi_manager, and time_keeper do their thing
            watchdog.feed()
            wifi_manager.handle_pending_connection_check()
            time_keeper.handle_pending_ntp_sync()

            # 2. Call mqtt_manager.process_messages
            mqtt_manager.process_messages()

            # 3. Call mqtt_manager.get_station_instructions
            mqtt_instructions = mqtt_manager.get_station_instructions()

            # 4. Call station.provide_instructions(mqtt_instructions)
            station.provide_instructions(mqtt_instructions)

            # 5. Call station.execute_pending_tasks()
            station.execute_pending_tasks()

            # 6. Call station.get_status_updates() and store in variable
            status_updates = station.get_status_updates()

            # 7. Finally call mqtt_manager.send_status_updates(status_updates)
            mqtt_manager.send_status_updates(status_updates)

            loop_count += 1

            # Run garbage collection every 30 loops (30 seconds) to prevent memory buildup
            if loop_count % 30 == 0:
                gc.collect()

            # LED on every third second (loop_count % 3 == 0), off otherwise
            if loop_count % 3 == 0:
                onboard_led.on()
            else:
                onboard_led.off()

            sleep(1)
    except Exception as e:
        logger.log(f"Exception in main loop: {e}")
        reset()


if __name__ == "__main__":
    main()
