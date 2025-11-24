from machine import Pin, I2C
from time import sleep, sleep_ms
from ads1x15 import ADS1115


MOSFET_PINS = [18, 19, 20, 21, 22, 28, 26, 27]
# Set to None to test all mosfets
CURRENT_MOSFET_PIN: int | None = 28


def read_ads_channels(ads: ADS1115, ads_num: int):
    for ch in range(4):
        raw_value = ads.read(0, ch)  # Note: channel1 parameter
        voltage = raw_value * 6.144 / 32767  # Convert to voltage
        print(f"ADS{ads_num} CH{ch}: Raw={raw_value}, Voltage={voltage:.3f}V")


def read_all_sensors_for_mosfet(
    mosfet: Pin, ads1: ADS1115, ads2: ADS1115, sleep_duration: int
):
    mosfet.on()
    print(f"MOSFET ON - value: {mosfet.value()}")
    sleep_ms(300)  # Wait for sensor to stabilize

    read_ads_channels(ads1, 1)
    read_ads_channels(ads2, 2)

    sleep(sleep_duration)
    # Turn MOSFET OFF
    mosfet.off()
    print(f"MOSFET OFF - value: {mosfet.value()}")
    sleep(0.5)


def main() -> None:
    # Wait 5 seconds so we are sure to catch all output on the terminal
    sleep(5)

    # Initialize I2C and ADS1115
    i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
    ads1 = ADS1115(i2c, address=0x48, gain=0)  # First ADS1115
    ads2 = ADS1115(i2c, address=0x49, gain=0)  # Second ADS1115
    mosfet_pin_objects = [Pin(p, Pin.OUT) for p in MOSFET_PINS]

    print("Starting MOSFET and Sensor Test...")
    print("I2C addresses found:", [hex(addr) for addr in i2c.scan()])

    if CURRENT_MOSFET_PIN:
        # This is meant to help check if the sensor readings are correct.
        # Connect a potentiometer to a single sensor and check the voltage changes
        # as expected when turning the knob
        print(
            f"Running test for all sensors with single MOSFET pin {CURRENT_MOSFET_PIN}"
        )

        if CURRENT_MOSFET_PIN not in MOSFET_PINS:
            print(f"Error: {CURRENT_MOSFET_PIN} not in MOSFET_PINS list")
            return

        # Make sure all are off initially
        for mosfet_pin in mosfet_pin_objects:
            mosfet_pin.off()

        mosfet_index = MOSFET_PINS.index(CURRENT_MOSFET_PIN)
        mosfet = mosfet_pin_objects[mosfet_index]

        while True:
            read_all_sensors_for_mosfet(mosfet, ads1, ads2, 1)

    else:
        # This is meant to help figuring out how the MOSFET pins and sensor ADS/Channels
        # are mapped to terminals.
        print(f"Running test for all sensors and all MOSFET pins")

        # Make sure all are off initially
        for mosfet_pin in mosfet_pin_objects:
            mosfet_pin.off()

        while True:
            for i, mosfet_pin in enumerate(mosfet_pin_objects):
                print(f"Testing MOSFET on pin {MOSFET_PINS[i]}")
                # Long sleep duration during which you can check which terminal is being activated
                read_all_sensors_for_mosfet(mosfet_pin, ads1, ads2, 40)


if __name__ == "__main__":
    main()
