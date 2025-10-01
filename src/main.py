# from machine import Pin, I2C
# import time
# from ads1x15 import ADS1115

# # Initialize with type hints
# i2c: I2C = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
# ads1: ADS1115 = ADS1115(i2c, address=0x48)
# ads2: ADS1115 = ADS1115(i2c, address=0x49)

# # Define MOSFET control pins with type hints
# mosfet_pins: list[int] = [2, 3] # GPIO pins for MOSFETs
# mosfets: list[Pin] = [Pin(pin, Pin.OUT) for pin in mosfet_pins]

# def read_sensor(ads: ADS1115, channel: int) -> tuple[int, float]:
#     """Read a specific channel from an ADS1115"""
#     raw_value: int = ads.read(channel) # Use ads.read() instead of set_input()
#     volts: float = raw_value * 4.096 / 32767
#     return (raw_value, volts)

# # Test loop
# while True:
#     for i, mosfet in enumerate(mosfets):
#         mosfet.on()
#         time.sleep_ms(50)

#         # Read with type hints
#         raw1: int
#         volts1: float
#         raw1, volts1 = read_sensor(ads1, 0)
#         print(f"MOSFET {i}, ADS1 A0: {raw1} ({volts1:.3f}V)")

#         raw2, volts2 = read_sensor(ads2, 0)
#         print(f"MOSFET {i}, ADS2 A0: {raw2} ({volts2:.3f}V)")

#         mosfet.off()
#         time.sleep(1)

# from machine import I2C, Pin
# import time

# i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000) # Use your pins

# while True:
#     print("Scanning I2C bus...")
#     devices = i2c.scan()
#     if devices:
#         for device in devices:
#             print("Found device at address: ", hex(device))
#     else:
#         print("No I2C devices found!")
        
#     time.sleep(2)

from machine import Pin, I2C
import time
from ads1x15 import ADS1115

# Initialize I2C and ADS1115
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
ads = ADS1115(i2c, address=0x48) # First ADS1115

# Initialize MOSFET on GP18
mosfet = Pin(18, Pin.OUT)

print("Starting MOSFET and Sensor Test...")

while True:
    # Turn MOSFET ON (sensor powered)
    mosfet.on()
    print("MOSFET ON - Sensor should be powered")
    time.sleep_ms(500) # Wait for sensor to stabilize

    # Read sensor value from A0
    raw_value = ads.read(0) # Read channel A0
    voltage = raw_value * 4.096 / 32767 # Convert to voltage

    print(f"Raw: {raw_value}, Voltage: {voltage:.3f}V")

    # Turn MOSFET OFF
    time.sleep(5)
    mosfet.off()
    print("MOSFET OFF - Sensor should be off")
    time.sleep(5) # Wait 2 seconds before next reading