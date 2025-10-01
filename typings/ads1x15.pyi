from machine import I2C

class ADS1115:
    # Constants
    A0 = 0
    A1 = 1
    A2 = 2
    A3 = 3
    GAIN_6_144V: int
    GAIN_4_096V: int
    GAIN_2_048V: int
    GAIN_1_024V: int
    GAIN_0_512V: int
    GAIN_0_256V: int

    def __init__(self, i2c: I2C, address: int = 0x48, gain: int = GAIN_4_096V) -> None: ...

    def read(self, channel: int, gain: int = GAIN_4_096V) -> int: ...
    def read_voltage(self, channel: int) -> float: ...
    def alert_read(self) -> int: ...
