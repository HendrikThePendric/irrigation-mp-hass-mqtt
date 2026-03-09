"""Test logger.py using unittest framework."""

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

import unittest


class TestLogger(unittest.TestCase):
    """Test logger.py using unittest framework."""

    def setUp(self) -> None:
        """Reset mock state before each test."""
        global file_opens, file_writes
        file_opens.clear()
        file_writes.clear()
        # Restore original print if it was modified
        if hasattr(self, "_original_print"):
            builtins.print = self._original_print

    def tearDown(self) -> None:
        """Clean up after each test."""
        # Restore original print
        if hasattr(self, "_original_print"):
            builtins.print = self._original_print

    def test_logger_initialization(self) -> None:
        """Test logger initialization."""
        # Create logger without printing
        logger = Logger(should_print=False)
        self.assertFalse(logger._should_print)

        # Create logger with printing
        logger_with_print = Logger(should_print=True)
        self.assertTrue(logger_with_print._should_print)

        # Check timestamp function
        from logger import _return_empty_str  # type: ignore

        self.assertEqual(logger._get_timestamp(), "")

    def test_logger_log_without_print(self) -> None:
        """Test logger log method without printing."""
        # Create logger without printing
        logger = Logger(should_print=False)

        # Log a message
        test_message = "Test log message"
        logger.log(test_message)

        # Check that file was opened
        self.assertTrue(len(file_opens) > 0)

        # Check file was opened in append mode
        filename, mode = file_opens[0]
        self.assertEqual(mode, "a")

        # Check that message was written (with newline)
        self.assertIn("./log.txt", file_writes)
        written = file_writes["./log.txt"]
        self.assertIn(test_message, written)

    def test_logger_log_with_print(self) -> None:
        """Test logger log method with printing."""
        # Capture print output
        printed_messages = []
        self._original_print = builtins.print

        def mock_print(*args, **kwargs):
            printed_messages.append(" ".join(str(arg) for arg in args))

        # Replace print with mock
        builtins.print = mock_print

        try:
            # Create logger with printing
            logger = Logger(should_print=True)

            # Log a message
            test_message = "Test log message with print"
            logger.log(test_message)

            # Check that message was printed
            self.assertTrue(len(printed_messages) > 0)
            printed = printed_messages[0]
            self.assertIn(test_message, printed)

            # Check that file was also written
            self.assertIn("./log.txt", file_writes)

        finally:
            # Restore original print
            builtins.print = self._original_print

    def test_logger_enable_timestamp_prefix(self) -> None:
        """Test enable_timestamp_prefix method."""
        # Create logger
        logger = Logger(should_print=False)

        # Create a mock timestamp function
        def mock_timestamp():
            return "2024-01-01 12:00:00"

        # Enable timestamp
        logger.enable_timestamp_prefix(mock_timestamp)

        # Check that timestamp function was set
        self.assertEqual(logger._get_timestamp, mock_timestamp)

        # Check that it returns the mock timestamp
        self.assertEqual(logger._get_timestamp(), "2024-01-01 12:00:00")

    def test_logger_format_msg(self) -> None:
        """Test _format_msg method."""
        # Create logger
        logger = Logger(should_print=False)

        # Test without timestamp
        msg = "Test message"
        formatted = logger._format_msg(msg)
        self.assertEqual(formatted, msg)

        # Test with timestamp
        def mock_timestamp():
            return "2024-01-01 12:00:00"

        logger.enable_timestamp_prefix(mock_timestamp)

        formatted = logger._format_msg(msg)
        expected = "2024-01-01 12:00:00 Test message"
        self.assertEqual(formatted, expected)

        # Test multi-line message
        multi_line_msg = "Line 1\nLine 2\nLine 3"
        formatted = logger._format_msg(multi_line_msg)
        # Should wrap with timestamp header
        self.assertIn("====2024-01-01 12:00:00====", formatted)
        self.assertIn("Line 1\nLine 2\nLine 3", formatted)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
