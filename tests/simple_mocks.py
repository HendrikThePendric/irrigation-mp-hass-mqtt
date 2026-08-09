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


# Mock Timer class
class MockTimer:
    """Mock machine.Timer class with expiration simulation."""

    ONE_SHOT = 0
    PERIODIC = 1

    def __init__(self):
        self.init_calls = []
        self.callback = None
        self.period = 0
        self.mode = self.ONE_SHOT
        self.active = False
        self.elapsed_time = 0
        self.timer_id = id(self)  # Unique ID for this timer
        self.id = -1  # Timer ID parameter

    def init(self, period, mode, callback):
        """Initialize timer with period, mode, and callback."""
        self.init_calls.append((period, mode, callback))
        self.period = period
        self.mode = mode
        self.callback = callback
        self.active = True
        self.elapsed_time = 0

    def deinit(self):
        """Deinitialize timer."""
        self.active = False
        self.callback = None

    def simulate_expiration(self):
        """Simulate timer expiration by calling callback if active."""
        if self.active and self.callback:
            # Call the callback with timer object as argument
            self.callback(self)
            # If ONE_SHOT mode, deactivate after firing
            if self.mode == self.ONE_SHOT:
                self.active = False

    def simulate_time_passed(self, ms):
        """Simulate time passing and check if timer should expire."""
        if not self.active:
            return

        self.elapsed_time += ms
        if self.elapsed_time >= self.period:
            self.simulate_expiration()
            # Reset elapsed time for periodic timers
            if self.mode == self.PERIODIC:
                self.elapsed_time = 0


# Timer factory to track timer creations
class TimerFactory:
    """Factory that creates MockTimer instances and tracks them."""

    ONE_SHOT = MockTimer.ONE_SHOT
    PERIODIC = MockTimer.PERIODIC

    def __init__(self, mock_machine):
        self.mock_machine = mock_machine

    def __call__(self, id=-1):
        """Create a mock timer."""
        timer = MockTimer()
        timer.id = id  # Store the ID for compatibility
        self.mock_machine.timers_created.append(timer)
        return timer


# Create a simple mock machine module
class MockMachine:
    """Mock machine module."""

    def __init__(self):
        self.pins_created = []
        self.Pin = PinFactory(self)
        self.I2C = type("MockI2C", (), {"init": lambda self, **kwargs: None})
        self.Timer = TimerFactory(self)
        self.timers_created = []

    def unique_id(self) -> bytes:
        """Return a mock unique ID."""
        return b"mock-device-id-12345"

    def reset(self) -> None:
        """Mock reset function."""
        pass


# Mock os module
class MockOS:
    _files = {}
    """Mock os module."""

    # Essential attributes for unittest and standard library
    name = "posix"
    sep = "/"
    supports_dir_fd = False
    supports_bytes_environ = True
    supports_effective_ids = True
    supports_fd = True
    supports_follow_symlinks = True

    # Mock environ dictionary
    environ = {}

    # Functions needed by shutil and other stdlib modules
    # Use regular functions, not static methods, so they can be put in sets
    def open(self, path: str, mode: str = "r"):
        raise NotImplementedError("MockOS.open not implemented")

    def unlink(self, path: str):
        pass

    def rmdir(self, path: str):
        pass

    def listdir(self, path: str = "."):
        return []

    def makedirs(self, path: str, exist_ok: bool = False):
        pass

    def remove(self, path: str):
        pass

    def getcwd(self):
        return "/mock/cwd"

    # stat_result class needed by shutil module
    class stat_result:
        st_file_attributes = 0

    # Add path submodule
    class path:
        @staticmethod
        def join(*args: str) -> str:
            return "/".join(args)

        @staticmethod
        def exists(path: str) -> bool:
            return True

        @staticmethod
        def isfile(path: str) -> bool:
            return True

        @staticmethod
        def isdir(path: str) -> bool:
            return False

        @staticmethod
        def getsize(path: str) -> int:
            return 1000

        @staticmethod
        def basename(path: str) -> str:
            """Mock basename function."""
            if "/" in path:
                return path.split("/")[-1]
            return path

    def stat(self, path: str) -> tuple:
        # Return a tuple with st_size at index 6
        return (0, 0, 0, 0, 0, 0, 1000)

    def sync(self) -> None:
        pass

    def rename(self, old: str, new: str) -> None:
        pass

    @staticmethod
    def isatty(fd):
        """Mock isatty function."""
        return False


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
    _current_time = 1000.0  # Start at 1000 seconds

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
    def ticks_diff(ticks1: int, ticks2: int) -> int:
        """Mock ticks_diff - returns simple difference."""
        return ticks1 - ticks2

    @staticmethod
    def reset_ticks() -> None:
        """Reset tick counter for tests."""
        MockTime._ticks = 0

    @staticmethod
    def gmtime(seconds: int | None = None) -> tuple:
        """Mock gmtime - returns a fixed time tuple."""
        # Return a fixed time: (2024, 1, 1, 0, 0, 0, 0, 0)
        return (2024, 1, 1, 0, 0, 0, 0, 0)

    @staticmethod
    def perf_counter():
        """Mock perf_counter."""
        return 0.0

    @staticmethod
    def time() -> float:
        """Return mock time."""
        return MockTime._current_time

    @staticmethod
    def set_time(new_time: float) -> None:
        """Set mock time for testing."""
        MockTime._current_time = new_time

    @staticmethod
    def advance(seconds: float) -> None:
        """Advance mock time by seconds."""
        MockTime._current_time += seconds

    @staticmethod
    def reset_time() -> None:
        """Reset mock time to default."""
        MockTime._current_time = 1000.0


# Mock ADS1x15 module for ADC
class MockADS1115:
    """Mock ADS1115 ADC class."""

    def __init__(self, i2c_bus=None, address=None, gain=None):
        self.read_calls = []
        self.raw_to_v_calls = []
        self.read_return_value = 1000  # Default raw reading
        self.voltage_return_value = 1.675  # ~50% moisture with default calibration

    def read(self, rate, channel):
        self.read_calls.append((rate, channel))
        return self.read_return_value

    def raw_to_v(self, raw):
        self.raw_to_v_calls.append(raw)
        return self.voltage_return_value


# Mock for umqtt.simple module
class MockMQTTClient:
    # Class-level list to track all instances
    instances = []

    def __init__(self, *args, **kwargs):
        self.published_messages = []
        self.connected = False
        self.disconnect_called = False
        self.connect_calls = []
        self.subscribe_calls = []
        self.keepalive = kwargs.get("keepalive", 0)
        # Register this instance
        MockMQTTClient.instances.append(self)

    def connect(self, *args, **kwargs):
        self.connected = True
        self.connect_calls.append((args, kwargs))

    def disconnect(self):
        self.connected = False
        self.disconnect_called = True

    def publish(self, topic, message, retain=False, qos=0):
        self.published_messages.append((topic, message, retain, qos))

    def subscribe(self, topic):
        self.subscribe_calls.append(topic)

    def ping(self):
        pass

    def check_msg(self):
        return None

    def wait_msg(self):
        return None

    def set_last_will(self, topic, message, retain=False, qos=0):
        self.last_will_topic = topic
        self.last_will_message = message
        self.last_will_retain = retain
        self.last_will_qos = qos

    def set_callback(self, callback):
        self.callback = callback

    @property
    def sock(self):
        # Return a mock socket
        class MockSocket:
            def setblocking(self, *args):
                pass

        return MockSocket()

    @classmethod
    def reset_instances(cls):
        """Clear all tracked instances."""
        cls.instances.clear()


# Mock SSL/TLS module for MQTT over TLS tests
class MockSSLContext:
    def __init__(self, protocol):
        self.protocol = protocol
        self.cafile = None
        self.certfile = None
        self.keyfile = None

    def load_verify_locations(self, cafile=None):
        self.cafile = cafile

    def load_cert_chain(self, certfile=None, keyfile=None):
        self.certfile = certfile
        self.keyfile = keyfile


# Mock ADS1x15 module
class MockADS1x15Module:
    """Mock ads1x15 module with ADS1115 class."""

    class ADS1115:
        def __init__(self, i2c_bus=None, address=None, gain=None):
            self.read_calls = []
            self.raw_to_v_calls = []
            self.read_return_value = 1000  # Default raw reading
            self.voltage_return_value = 1.675  # ~50% moisture with default calibration

        def read(self, rate, channel):
            self.read_calls.append((rate, channel))
            return self.read_return_value

        def raw_to_v(self, raw):
            self.raw_to_v_calls.append(raw)
            return self.voltage_return_value


# Mock network module (for WiFi)
class MockNetwork:
    """Mock network module for WiFi."""

    STA_IF = 0
    AP_IF = 1

    class WLAN:
        def __init__(self, interface):
            self.interface = interface
            self.active_calls = []
            self.connect_calls = []
            self.isconnected_calls = []
            self._active = False
            self._connected = False
            self._config_calls = []

        def active(self, value):
            self.active_calls.append(value)
            self._active = value

        def connect(self, ssid, password):
            self.connect_calls.append((ssid, password))
            self._connected = True

        def isconnected(self):
            self.isconnected_calls.append(())
            return self._connected

        def config(self, **kwargs):
            self._config_calls.append(kwargs)

        def status(self):
            return 3  # STAT_GOT_IP

        def ifconfig(self):
            """Return mock network configuration."""
            return ("192.168.1.100", "255.255.255.0", "192.168.1.1", "8.8.8.8")

    # Create a mock instance for tracking
    wlan_instance = None

    @classmethod
    def create_wlan(cls, interface):
        """Create and track a WLAN instance."""
        cls.wlan_instance = cls.WLAN(interface)
        return cls.wlan_instance

    @classmethod
    def reset(cls):
        """Reset the mock state."""
        cls.wlan_instance = None


# Mock rp2 module
class MockRP2:
    """Mock rp2 module for country setting."""

    def country(self, country_code):
        self.country_code = country_code
        self.country_calls = [country_code]


# Mock gc module
class MockGC:
    """Mock gc module for garbage collection."""

    def __init__(self):
        self.collect_calls = []

    def collect(self):
        self.collect_calls.append(())
        return 0  # Return number of collected objects


# Global mock instances
mock_machine = MockMachine()
mock_os = MockOS()
mock_ntptime = MockNTPTime()
mock_time = MockTime()
mock_ads1115 = MockADS1115()
mock_ads1x15 = MockADS1x15Module()
MockUMQTTClass = type("MockUMQTT", (), {"MQTTClient": MockMQTTClient})
mock_umqtt_simple = MockUMQTTClass()
mock_ssl_context = MockSSLContext
mock_network = MockNetwork()
mock_rp2 = MockRP2()
mock_gc = MockGC()
