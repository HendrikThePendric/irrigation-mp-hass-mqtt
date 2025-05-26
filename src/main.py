from time import sleep
import ntptime
from logger import Logger
from config import Config
from wifi import connect_to_wifi

sleep(2)

logger = Logger()
config = Config("./config.json")

logger.log(str(config))
connect_to_wifi(config.network, logger)
ntptime.settime()

counter = 0

while True:
    counter += 1
    msg = f"B {counter}"
    print(msg)
    logger.log(msg)
    sleep(0.005)
