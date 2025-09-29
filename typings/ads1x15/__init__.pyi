"""
Type stubs for the robert-hh/ads1x15 MicroPython library.
Provides type hints for ADS1115 analog-to-digital converter functionality.
"""

from machine import I2C
from typing import Optional, Union

class ADS1115:
    """ADS1115 16-bit ADC with internal reference."""
    
    # Gain settings
    GAIN_TWOTHIRDS: int
    GAIN_ONE: int
    GAIN_TWO: int
    GAIN_FOUR: int
    GAIN_EIGHT: int
    GAIN_SIXTEEN: int
    
    # Data rate settings  
    RATE_8: int
    RATE_16: int
    RATE_32: int
    RATE_64: int
    RATE_128: int
    RATE_250: int
    RATE_475: int
    RATE_860: int
    
    def __init__(
        self, 
        i2c: I2C, 
        address: int = 0x48, 
        gain: int = ...,
        rate: int = ...
    ) -> None:
        """Initialize ADS1115 with I2C interface and optional configuration."""
        ...
    
    def read(
        self, 
        channel: int, 
        gain: Optional[int] = None,
        rate: Optional[int] = None
    ) -> int:
        """Read raw ADC value from specified channel (0-3)."""
        ...
    
    def read_voltage(
        self, 
        channel: int,
        gain: Optional[int] = None,
        rate: Optional[int] = None  
    ) -> float:
        """Read voltage from specified channel (0-3) in volts."""
        ...
        
    def set_gain(self, gain: int) -> None:
        """Set the programmable gain amplifier."""
        ...
        
    def set_rate(self, rate: int) -> None:
        """Set the data rate for conversions."""
        ...

class ADS1015:
    """ADS1015 12-bit ADC with internal reference."""
    
    # Same interface as ADS1115 but 12-bit resolution
    GAIN_TWOTHIRDS: int
    GAIN_ONE: int
    GAIN_TWO: int
    GAIN_FOUR: int
    GAIN_EIGHT: int
    GAIN_SIXTEEN: int
    
    RATE_128: int
    RATE_250: int
    RATE_490: int
    RATE_920: int
    RATE_1600: int
    RATE_2400: int
    RATE_3300: int
    
    def __init__(
        self, 
        i2c: I2C, 
        address: int = 0x48,
        gain: int = ...,
        rate: int = ...
    ) -> None: ...
    
    def read(
        self, 
        channel: int,
        gain: Optional[int] = None,
        rate: Optional[int] = None
    ) -> int: ...
    
    def read_voltage(
        self, 
        channel: int,
        gain: Optional[int] = None,
        rate: Optional[int] = None
    ) -> float: ...
        
    def set_gain(self, gain: int) -> None: ...
    def set_rate(self, rate: int) -> None: ...