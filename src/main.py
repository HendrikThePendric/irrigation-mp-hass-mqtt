from machine import reset
from time import sleep
from firmware_controller import FirmwareController

PRINT_LOGS = True

if PRINT_LOGS:
    # Delay initialization for a bit, to ensure
    # `mpremote connect` has completed. This
    # guarrantees that all log statement are going
    # to be visible
    sleep(2)


def main() -> None:
    # Create the irrigation system
    system = FirmwareController("./config.json", PRINT_LOGS)

    try:
        while True:
            system.tick()
            sleep(1)

    except Exception as e:
        system.logger.log(f"Exception in main loop: {e}")
        reset()


if __name__ == "__main__":
    main()
