
from machine import Pin, I2C
import time
from ads1x15 import ADS1115

MOSFET_PIN = 21

def read_ads_channels(ads: ADS1115, ads_num: int):
    for ch in range(4):
        # CORRECTED: Use channel1 parameter for single-ended measurements
        raw_value = ads.read(0, ch)  # Note: channel1 parameter
        voltage = raw_value * 6.144 / 32767  # Convert to voltage
        print(f"ADS{ads_num} CH{ch}: Raw={raw_value}, Voltage={voltage:.3f}V")

def check_all_script():
    # Initialize I2C and ADS1115
    i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
    ads1 = ADS1115(i2c, address=0x48, gain=0)  # First ADS1115
    ads2 = ADS1115(i2c, address=0x49, gain=0)  # Second ADS1115

    # Initialize MOSFET on GP19
    mosfet = Pin(MOSFET_PIN, Pin.OUT)

    # Wait 5 seconds so we are sure to catch all output on the terminal
    time.sleep(5)

    print("Starting MOSFET and Sensor Test...")
    print("I2C addresses found:", [hex(addr) for addr in i2c.scan()])

    while True:
        # Turn MOSFET ON (sensor powered)
        mosfet.on()
        print("\nMOSFET ON - Sensor should be powered\n")
        time.sleep_ms(300)  # Wait for sensor to stabilize

        read_ads_channels(ads1, 1)
        read_ads_channels(ads2, 2)

        # Turn MOSFET OFF
        time.sleep(10)
        mosfet.off()
        print("\nMOSFET OFF - Sensor should be off\n")
        time.sleep(2)

def original_script():
    # Initialize I2C and ADS1115
    i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
    ads = ADS1115(i2c, address=0x48, gain=0) # First ADS1115

    # Initialize MOSFET on GP18
    mosfet = Pin(MOSFET_PIN, Pin.OUT)

    print("Starting MOSFET and Sensor Test...")

    while True:
        # Turn MOSFET ON (sensor powered)
        mosfet.on()
        print(f"MOSFET ON - Sensor should be powered: {mosfet.value()}")
        time.sleep_ms(300) # Wait for sensor to stabilize

        # Read sensor value from A0
        raw_value = ads.read(0, 0) # Read channel A0
        voltage = raw_value * 6.144 / 32767 # Convert to voltage

        print(f"Raw: {raw_value}, Voltage: {voltage:.3f}V")

        # Turn MOSFET OFF
        time.sleep(1)
        mosfet.off()
        print(f"MOSFET OFF - Sensor should be off: {mosfet.value()}")
        print(f"Raw: {raw_value}, Voltage: {voltage:.3f}V")
        time.sleep(2) # Wait 2 seconds before next reading

def force_fresh_reads():
    # Initialize I2C and ADS1115
    i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
    ads = ADS1115(i2c, address=0x48, gain=0) # First ADS1115
    mosfet = Pin(MOSFET_PIN, Pin.OUT)
    # Turn MOSFET ON (sensor powered)
    mosfet.on()
    print("Forcing fresh reads")

    for _ in range(40):
        ads = ADS1115(i2c, address=0x48, gain=0)
        raw = ads.read(0, 1)   # read AIN1
        print("RAW AIN1:", raw)
        time.sleep(0.2)
# original_script()
check_all_script()
# force_fresh_reads()