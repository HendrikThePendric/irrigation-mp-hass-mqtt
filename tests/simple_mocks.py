"""Simple mocks for testing hardware-dependent code.

Instead of complex sys.modules replacement, we'll create simple mock classes
and use dependency injection or monkey patching.
"""


class MockPin:
    """Mock machine.Pin class."""

    OUT = 1
    IN = 0

    def __init__(self, pin_id: int, mode: int = OUT, pull=None) -> None:
        self.pin_id = pin_id
        self.mode = mode
        self._value = 0  # 0 = off, 1 = on
        self.calls = []

    def on(self) -> None:
        """Turn pin on."""
        self._value = 1
        self.calls.append(("on",))

    def off(self) -> None:
        """Turn pin off."""
        self._value = 0
        self.calls.append(("off",))

    def value(self, val: int | None = None) -> int:
        """Get or set pin value."""
        if val is not None:
            self._value = val
            self.calls.append(("value", val))
        return self._value


# Create a wrapper class that tracks pin creations
class PinFactory:
    """Factory that creates MockPin instances and tracks them."""

    OUT = MockPin.OUT
    IN = MockPin.IN

    def __init__(self, mock_machine):
        self.mock_machine = mock_machine

    def __call__(self, pin_id: int, mode: int = MockPin.OUT, pull=None) -> MockPin:
        """Create a mock pin."""
        pin = MockPin(pin_id, mode, pull)
        self.mock_machine.pins_created.append(pin)
        return pin


# Create a simple mock machine module
class MockMachine:
    """Mock machine module."""

    def __init__(self):
        self.pins_created = []
        self.Pin = PinFactory(self)

    def unique_id(self) -> bytes:
        """Return a mock unique ID."""
        return b"mock-device-id-12345"


# Mock os module
class MockOS:
    """Mock os module."""

    @staticmethod
    def rename(old: str, new: str) -> None:
        pass

    @staticmethod
    def stat(path: str) -> tuple:
        # Return a tuple with st_size at index 6
        return (0, 0, 0, 0, 0, 0, 1000)

    @staticmethod
    def sync() -> None:
        pass


# Mock datetime module
class MockDatetime:
    """Mock datetime module for MicroPython testing."""

    class datetime:
        def __init__(
            self,
            year: int,
            month: int = 1,
            day: int = 1,
            hour: int = 0,
            minute: int = 0,
            second: int = 0,
        ):
            self.year = year
            self.month = month
            self.day = day
            self.hour = hour
            self.minute = minute
            self.second = second

        def __str__(self) -> str:
            return f"{self.year}-{self.month:02}-{self.day:02} {self.hour:02}:{self.minute:02}:{self.second:02}"

    class date:
        def __init__(self, year: int, month: int, day: int):
            self.year = year
            self.month = month
            self.day = day

        def weekday(self) -> int:
            # Simple mock - always return Monday (0)
            return 0

        def __sub__(self, other):
            # Mock subtraction with timedelta
            if isinstance(other, MockDatetime.timedelta):
                # Return a new date (simplified)
                return MockDatetime.date(self.year, self.month, self.day)
            return self

    class time:
        def __init__(self, hour: int = 0, minute: int = 0, second: int = 0):
            self.hour = hour
            self.minute = minute
            self.second = second

    class timedelta:
        def __init__(
            self,
            days: int = 0,
            seconds: int = 0,
            microseconds: int = 0,
            milliseconds: int = 0,
            minutes: int = 0,
            hours: int = 0,
            weeks: int = 0,
        ):
            self.days = days
            self.seconds = seconds

        def __add__(self, other):
            # Simple mock addition
            return MockDatetime.timedelta(days=self.days, seconds=self.seconds)

    @staticmethod
    def combine(date, time):
        return MockDatetime.datetime(
            date.year, date.month, date.day, time.hour, time.minute, time.second
        )


# Mock ntptime module
class MockNTPTime:
    """Mock ntptime module."""

    host = "nl.pool.ntp.org"

    @staticmethod
    def settime() -> None:
        pass


# Mock time module
class MockTime:
    """Mock time module for testing."""

    _ticks = 0

    @staticmethod
    def sleep(seconds: float) -> None:
        """Mock sleep - does nothing."""
        MockTime._ticks += int(seconds * 1000)

    @staticmethod
    def sleep_ms(ms: int) -> None:
        """Mock sleep_ms - does nothing."""
        MockTime._ticks += ms

    @staticmethod
    def ticks_ms() -> int:
        """Return mock tick count."""
        MockTime._ticks += 1
        return MockTime._ticks

    @staticmethod
    def reset_ticks() -> None:
        """Reset tick counter for tests."""
        MockTime._ticks = 0


# Mock ADS1x15 module for ADC
class MockADS1115:
    """Mock ADS1115 ADC class."""

    def __init__(self, i2c_bus=None, address=None, gain=None):
        self.read_calls = []
        self.raw_to_v_calls = []
        self.read_return_value = 1000  # Default raw reading
        self.voltage_return_value = 2.5  # Default voltage

    def read(self, rate, channel):
        self.read_calls.append((rate, channel))
        return self.read_return_value

    def raw_to_v(self, raw):
        self.raw_to_v_calls.append(raw)
        return self.voltage_return_value


# Global mock instances
mock_machine = MockMachine()
mock_os = MockOS()
mock_datetime = MockDatetime()
mock_ntptime = MockNTPTime()
mock_time = MockTime()
mock_ads1115 = MockADS1115()
