"""Test logger.py using simple mocks."""

import sys

# Setup paths
sys.path.insert(0, "src")
sys.path.insert(0, "tests")

# Import simple mocks
from simple_mocks import (
    MockPin,
    mock_machine,
    mock_os,
    mock_datetime,
    mock_ntptime,
    mock_time,
)


# Create mock modules before importing ANY project code
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id
    RTC = type("MockRTC", (), {"datetime": lambda self: (2024, 1, 1, 0, 0, 0, 0, 0)})
    Timer = type("MockTimer", (), {"init": lambda self, **kwargs: None, "ONE_SHOT": 0})
    reset = lambda: None


# Mock file operations
class MockFile:
    def __init__(self, filename, mode):
        self.filename = filename
        self.mode = mode
        self.content = ""
        self.closed = False

    def write(self, text):
        self.content += text
        # Also update global file_writes
        if self.filename in file_writes:
            file_writes[self.filename] += text
        else:
            file_writes[self.filename] = text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.closed = True
        # Ensure content is saved to file_writes
        if self.filename in file_writes:
            file_writes[self.filename] = self.content
        else:
            file_writes[self.filename] = self.content


# Track file operations
file_writes = {}
file_opens = []


def mock_open(filename, mode="r"):
    file_opens.append((filename, mode))
    if filename not in file_writes:
        file_writes[filename] = ""
    return MockFile(filename, mode)


# Add all mock modules to sys.modules
sys.modules["machine"] = MachineModule()
sys.modules["os"] = mock_os
sys.modules["datetime"] = mock_datetime
sys.modules["ntptime"] = mock_ntptime
sys.modules["time"] = mock_time

# Replace built-in open with mock
import builtins

original_open = builtins.open
builtins.open = mock_open

# Now import the modules to test
from logger import Logger  # type: ignore


def test_logger_initialization() -> bool:
    """Test logger initialization."""
    print("Testing logger initialization...")

    # Clear file tracking
    global file_opens, file_writes
    file_opens.clear()
    file_writes.clear()

    try:
        # Create logger without printing
        logger = Logger(should_print=False)

        if logger._should_print != False:
            print(f"  ❌ should_print should be False, got {logger._should_print}")
            return False

        # Create logger with printing
        logger_with_print = Logger(should_print=True)

        if logger_with_print._should_print != True:
            print(
                f"  ❌ should_print should be True, got {logger_with_print._should_print}"
            )
            return False

        # Check timestamp function
        from logger import _return_empty_str  # type: ignore

        if logger._get_timestamp() != "":
            print(f"  ❌ Initial timestamp function should return empty string")
            return False

    except Exception as e:
        print(f"  ❌ Logger initialization raised exception: {e}")
        return False

    print("  ✅ Logger initialization test passed")
    return True


def test_logger_log_without_print() -> bool:
    """Test logger log method without printing."""
    print("Testing logger.log() without print...")

    # Clear file tracking
    global file_opens, file_writes
    file_opens.clear()
    file_writes.clear()

    try:
        # Create logger without printing
        logger = Logger(should_print=False)

        # Log a message
        test_message = "Test log message"
        logger.log(test_message)

        # Check that file was opened
        if len(file_opens) == 0:
            print(f"  ❌ File should have been opened for logging")
            return False

        # Check file was opened in append mode
        filename, mode = file_opens[0]
        if mode != "a":
            print(f"  ❌ File should be opened in append mode 'a', got '{mode}'")
            return False

        # Check that message was written (with newline)
        if "./log.txt" not in file_writes:
            print(f"  ❌ Message not written to log file")
            return False

        written = file_writes["./log.txt"]
        if test_message not in written:
            print(f"  ❌ Test message not in written content: {written}")
            return False

    except Exception as e:
        print(f"  ❌ Logger.log() without print raised exception: {e}")
        return False

    print("  ✅ Logger.log() without print test passed")
    return True


def test_logger_log_with_print() -> bool:
    """Test logger log method with printing."""
    print("Testing logger.log() with print...")

    # Clear file tracking
    global file_opens, file_writes
    file_opens.clear()
    file_writes.clear()

    # Capture print output
    printed_messages = []
    original_print = print

    def mock_print(*args, **kwargs):
        printed_messages.append(" ".join(str(arg) for arg in args))

    try:
        # Replace print with mock
        builtins.print = mock_print

        # Create logger with printing
        logger = Logger(should_print=True)

        # Log a message
        test_message = "Test log message with print"
        logger.log(test_message)

        # Check that message was printed
        if len(printed_messages) == 0:
            print(f"  ❌ Message should have been printed")
            return False

        printed = printed_messages[0]
        if test_message not in printed:
            print(f"  ❌ Test message not in printed output: {printed}")
            return False

        # Check that file was also written
        if "./log.txt" not in file_writes:
            print(f"  ❌ Message not written to log file")
            return False

    except Exception as e:
        print(f"  ❌ Logger.log() with print raised exception: {e}")
        return False

    finally:
        # Restore original print
        builtins.print = original_print

    print("  ✅ Logger.log() with print test passed")
    return True


def test_logger_enable_timestamp_prefix() -> bool:
    """Test enable_timestamp_prefix method."""
    print("Testing enable_timestamp_prefix()...")

    try:
        # Create logger
        logger = Logger(should_print=False)

        # Create a mock timestamp function
        def mock_timestamp():
            return "2024-01-01 12:00:00"

        # Enable timestamp
        logger.enable_timestamp_prefix(mock_timestamp)

        # Check that timestamp function was set
        if logger._get_timestamp != mock_timestamp:
            print(f"  ❌ Timestamp function not set correctly")
            return False

        # Check that it returns the mock timestamp
        if logger._get_timestamp() != "2024-01-01 12:00:00":
            print(f"  ❌ Timestamp function not returning expected value")
            return False

    except Exception as e:
        print(f"  ❌ enable_timestamp_prefix raised exception: {e}")
        return False

    print("  ✅ enable_timestamp_prefix() test passed")
    return True


def test_logger_format_msg() -> bool:
    """Test _format_msg method."""
    print("Testing _format_msg()...")

    try:
        # Create logger
        logger = Logger(should_print=False)

        # Test without timestamp
        msg = "Test message"
        formatted = logger._format_msg(msg)
        if formatted != msg:
            print(f"  ❌ Format without timestamp should return original message")
            return False

        # Test with timestamp
        def mock_timestamp():
            return "2024-01-01 12:00:00"

        logger.enable_timestamp_prefix(mock_timestamp)

        formatted = logger._format_msg(msg)
        expected = "2024-01-01 12:00:00 Test message"
        if formatted != expected:
            print(
                f"  ❌ Formatted message with timestamp incorrect: '{formatted}', expected '{expected}'"
            )
            return False

        # Test multi-line message
        multi_line_msg = "Line 1\nLine 2\nLine 3"
        formatted = logger._format_msg(multi_line_msg)
        # Should wrap with timestamp header
        if "====2024-01-01 12:00:00====" not in formatted:
            print(
                f"  ❌ Multi-line message not formatted correctly with timestamp header"
            )
            return False

        if "Line 1\nLine 2\nLine 3" not in formatted:
            print(f"  ❌ Multi-line content not preserved")
            return False

    except Exception as e:
        print(f"  ❌ _format_msg raised exception: {e}")
        return False

    print("  ✅ _format_msg() test passed")
    return True


def main() -> None:
    """Run all logger tests."""
    print("=== Testing logger.py ===")

    passed = 0
    total = 0

    # Run tests
    total += 1
    if test_logger_initialization():
        passed += 1

    total += 1
    if test_logger_log_without_print():
        passed += 1

    total += 1
    if test_logger_log_with_print():
        passed += 1

    total += 1
    if test_logger_enable_timestamp_prefix():
        passed += 1

    total += 1
    if test_logger_format_msg():
        passed += 1

    # Summary
    print("=" * 40)
    if passed == total:
        print("✅ All logger tests passed!")
    else:
        print(f"❌ {passed}/{total} tests passed")

    # Restore original open
    builtins.open = original_open


if __name__ == "__main__":
    main()
