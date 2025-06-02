from time import sleep
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
hass_mqtt_client = HassMqttClient(config, logger)

logger.log(str(config))
hass_mqtt_client.wifi_connnect()
time_keeper.initialize_ntp_synchronization()
logger.enable_timestamp_prefix(time_keeper.get_current_cet_datetime_str)
hass_mqtt_client.mqtt_connect()

counter = 0

while True:
    counter += 1
    msg = f"Counting: {counter}"
    logger.log(msg)
    sleep(2)
