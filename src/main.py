from time import sleep
from config import Config

config = Config("./config.json")

while True:
    print("Hello world")
    sleep(10)
