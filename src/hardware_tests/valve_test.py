from machine import Pin
from time import sleep

# Include all pins connected to the relay
PINS = [9, 8, 7, 6, 2, 3, 4, 5]


def main() -> None:
    """This script can be used to test if the relay is working correcly and to map pins to terminals"""

    # Wait 5 seconds so we are sure to catch all output on the terminal
    sleep(5)
    pin_objects = [Pin(p, Pin.OUT) for p in PINS]

    # Make sure all are off initially
    for pin in pin_objects:
        pin.off()

    while True:
        for i, pin in enumerate(pin_objects):
            print(f"Switched on pin {PINS[i]}")
            pin.on()
            sleep(40)  # During this time you can check which terminal is being powered
            pin.off()
            sleep(0.5)


if __name__ == "__main__":
    main()
