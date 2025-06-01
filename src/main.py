from time import sleep
from logger import Logger
from config import Config
from mqtt import mqtt_connect
from time_keeper import TimeKeeper
from wifi import connect_to_wifi

PRINT_LOGS = True

if PRINT_LOGS:
    # Delay initialization for a bit, to ensure
    # `mpremote connect` has completed. This
    # guarrantees that all log statement are going
    # to be visible
    sleep(2)

logger = Logger(PRINT_LOGS)
time_keeper = TimeKeeper(logger, 3, 1)
config = Config("./config.json")

logger.log(str(config))
connect_to_wifi(config.network, logger)
time_keeper.initialize_ntp_synchronization()
logger.enable_timestamp_prefix(time_keeper.get_current_cet_datetime_str)
mqtt_connect()

counter = 0

while True:
    counter += 1
    msg = f"B {counter}"
    logger.log(msg)
    sleep(0.05)
