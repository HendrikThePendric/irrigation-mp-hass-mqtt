from time import sleep
from hass_messaging_service import HassMessagingService
from irrigation_station import IrrigationStation
from logger import Logger
from config import Config
from mqtt import HassMqttClient
from time_keeper import TimeKeeper

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
station = IrrigationStation(config)
hass_mqtt_client = HassMqttClient(config, logger)


logger.log(str(config))
hass_mqtt_client.wifi_connect()
time_keeper.initialize_ntp_synchronization()
logger.enable_timestamp_prefix(time_keeper.get_current_cet_datetime_str)
mqtt_client = hass_mqtt_client.mqtt_connect()
hass_messaging_service = HassMessagingService(config, mqtt_client, logger, station)

counter = 0


def main() -> None:
    counter: int = 0
    try:
        while True:
            counter += 1
            msg: str = f"Counting: {counter}"
            logger.log(msg)
            mqtt_client.check_msg()
            time_keeper.handle_pending_ntp_sync()
            hass_messaging_service.handle_pending_publish()
            sleep(1)
    except Exception as e:
        import traceback
        logger.log(f"Exception in main loop: {e}\n{traceback.format_exc()}")
        from machine import reset
        reset()


if __name__ == "__main__":
    main()
