# Testing Framework

This project includes a simple but effective testing framework that runs tests in **actual MicroPython** (not CPython) with mocked hardware modules.

## Quick Start

```bash
# Setup MicroPython runtime (first time only)
./scripts/setup_micropython_test_env.sh

# Run all tests
python3 tests/run_tests.py

# Run individual test in MicroPython
./micropython-local tests/unit/test_rolling_average.py
```

## Framework Design

### Simple & Incremental
- **No complex mock systems**: Simple mock classes with dependency injection
- **Test-first approach**: Write mocks, test them, then test real code
- **MicroPython runtime**: Tests run in actual MicroPython interpreter

### Key Components

1. **Test Runner** (`tests/run_tests.py`):
   - Discovers and runs all test files
   - Runs tests in MicroPython interpreter
   - Provides clear pass/fail output

2. **Simple Mocks** (`tests/simple_mocks.py`):
   - Minimal mock classes for hardware modules
   - Tracks state for assertions
   - Easy to extend for new tests

3. **Test Files** (`tests/unit/*.py`):
   - Self-contained test scripts
   - Print results with ✅/❌ indicators
   - Can run standalone in MicroPython

## Writing Tests

### 1. Test Hardware-Free Modules
Start with modules that don't need mocks (like `rolling_average.py`):

```python
# tests/unit/test_example.py
import sys
sys.path.insert(0, "src")
from example import Example

def test_example() -> bool:
    example = Example()
    result = example.calculate()
    if result == expected:
        print("✅ Test passed")
        return True
    else:
        print(f"❌ Expected {expected}, got {result}")
        return False
```

### 2. Test Hardware-Dependent Modules
Use simple mocks for hardware dependencies:

```python
# tests/unit/test_hardware.py
import sys
sys.path.insert(0, "tests")
from simple_mocks import MockPin, mock_machine, mock_os

# Create mock modules before importing hardware-dependent code
class MachineModule:
    Pin = mock_machine.Pin
    unique_id = mock_machine.unique_id

sys.modules['machine'] = MachineModule()
sys.modules['os'] = mock_os

# Now import and test
from hardware_module import HardwareClass

def test_hardware() -> bool:
    # Test with mocked hardware
    hardware = HardwareClass()
    hardware.do_something()
    
    # Assert mock state
    if mock_machine.pins_created[0]._value == 1:
        print("✅ Hardware test passed")
        return True
    else:
        print("❌ Hardware test failed")
        return False
```

### 3. Mock Design Principles
- **Keep it simple**: Mock only what's needed for the test
- **Track state**: Use attributes like `_value`, `calls` for assertions
- **Incremental**: Add mock functionality as tests need it

## Current Test Coverage

### ✅ Working Tests
- `rolling_average.py`: Rolling average and EMA calculations
- `valve.py`: Valve control with mocked `machine.Pin`

### 🔧 Ready to Test Next
- `sensor.py`: Soil moisture sensor with ADS1115 mock
- `irrigation_point.py`: Complete irrigation point logic
- `mqtt_hass_manager.py`: MQTT integration with mocked network

## Extending the Framework

### Adding New Mocks
1. Add mock class to `simple_mocks.py`
2. Add factory method to `MockMachine` if needed
3. Update test to inject mock before import

### Testing Complex Scenarios
For integration tests (MQTT → main loop → hardware):
1. Create comprehensive mock in `tests/integration/`
2. Test full message flow
3. Assert hardware state changes

## Benefits

1. **Real MicroPython**: Tests run in actual MicroPython interpreter
2. **Simple Debugging**: No complex mock framework bugs
3. **Incremental**: Add tests as you develop features
4. **Fast**: Direct MicroPython execution, no complex setup

## Limitations

1. **Manual Mocking**: Need to create mocks for each hardware module
2. **Simple Assertions**: Basic print-based testing (not unittest framework)
3. **No Test Discovery**: Manual test file organization

The framework strikes a balance between simplicity and effectiveness, focusing on testing real code in MicroPython rather than building complex test infrastructure.