from machine import reset
from time import sleep
from hass_mqtt_client import HassMqttClient
from irrigation_station import IrrigationStation
from logger import Logger
from config import Config
from time_keeper import TimeKeeper
from wifi_manager import WiFiManager

PRINT_LOGS = True

if PRINT_LOGS:
    # Delay initialization for a bit, to ensure
    # `mpremote connect` has completed. This
    # guarrantees that all log statement are going
    # to be visible
    sleep(2)

logger = Logger(PRINT_LOGS)
time_keeper = TimeKeeper(logger)
config = Config("./config.json")
station = IrrigationStation(config, logger)
wifi_manager = WiFiManager(config.network, logger)
hass_mqtt_client = HassMqttClient(config, logger, station)

logger.log(str(config))
wifi_manager.setup()
time_keeper.initialize_ntp_synchronization()
logger.enable_timestamp_prefix(time_keeper.get_current_cet_datetime_str)
hass_mqtt_client.setup()


def main() -> None:
    try:
        while True:
            hass_mqtt_client.check_msg()
            time_keeper.handle_pending_ntp_sync()
            hass_mqtt_client.handle_pending_publish()
            sleep(1)
    except Exception as e:
        logger.log(f"Exception in main loop: {e}")
        reset()


if __name__ == "__main__":
    main()
