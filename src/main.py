from machine import reset, Pin
from time import sleep
from mqtt_hass_manager import MqttHassManager
from irrigation_station import IrrigationStation
from logger import Logger
from task_scheduler import TaskScheduler
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
    scheduler = TaskScheduler(
        sensor_measurement_interval=config.measurement_interval,
        mqtt_publish_interval=config.publish_interval,
    )
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

    try:
        while True:
            # === MAINTENANCE TASKS (Infrastructure) ===
            # These keep the system running but aren't core irrigation logic

            watchdog.feed()
            scheduler.update()

            if scheduler.wifi_check.is_due():
                wifi_manager.check_connection()
                scheduler.wifi_check.complete()

            if scheduler.ntp_sync.is_due():
                if time_keeper.sync_time():
                    scheduler.ntp_sync.complete()

            if scheduler.garbage_collect.is_due():
                gc.collect()
                scheduler.garbage_collect.complete()

            if scheduler.led_update.is_due():
                onboard_led.value(0 if onboard_led.value() else 1)
                scheduler.led_update.complete()

            if scheduler.broker_test.is_due():
                mqtt_manager.test_broker_connectivity()
                scheduler.broker_test.complete()

            mqtt_manager.process_messages()
            valve_commands = mqtt_manager.get_station_instructions()

            if valve_commands:
                station.process_instructions(valve_commands)
                valve_states = station.get_valve_states()
                mqtt_manager.publish_valve_states(valve_states)

            if scheduler.sensor_measurement.is_due():
                station.take_measurements()
                scheduler.sensor_measurement.complete()

            if scheduler.mqtt_publish.is_due():
                sensor_states = station.get_sensor_states()
                mqtt_manager.publish_sensor_states(sensor_states)
                scheduler.mqtt_publish.complete()

            sleep(1)

    except Exception as e:
        logger.log(f"Exception in main loop: {e}")
        reset()


if __name__ == "__main__":
    main()
