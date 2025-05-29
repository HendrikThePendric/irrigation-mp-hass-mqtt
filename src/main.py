from time import sleep
from logger import Logger
from config import Config
from time_keeper import TimeKeeper
from wifi import connect_to_wifi

sleep(2)

time_keeper = TimeKeeper(3, 1)
logger = Logger(time_keeper, True)
config = Config("./config.json")

logger.log(str(config))
connect_to_wifi(config.network, logger)
time_keeper.initialize_ntp_synchronization(logger)

counter = 0

while True:
    counter += 1
    msg = f"B {counter}"
    logger.log(msg)
    sleep(0.05)
