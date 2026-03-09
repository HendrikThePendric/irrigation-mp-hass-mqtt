#!/usr/bin/env python3
"""Test runner for MicroPython irrigation system.

This runs tests in actual MicroPython interpreter.
All tests now use unittest framework.
"""

import subprocess
import sys
import os.path


def run_test(test_file: str) -> bool:
    """Run a unittest test file in MicroPython."""
    print(f"Running test: {test_file}")

    # Get the MicroPython binary path
    micropython_bin = "./micropython-local"
    if not os.path.exists(micropython_bin):
        print(f"❌ MicroPython binary not found at {micropython_bin}")
        print("Run: ./scripts/setup_micropython_test_env.sh")
        return False

    try:
        # Run unittest test in MicroPython
        result = subprocess.run(
            [micropython_bin, test_file], capture_output=True, text=True, timeout=10
        )

        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"Stderr: {result.stderr}")

        # Check for unittest success indicator
        if "OK" in result.stdout and "FAILED" not in result.stdout:
            print(f"✅ {test_file} passed")
            return True
        else:
            print(f"❌ {test_file} failed")
            return False

    except subprocess.TimeoutExpired:
        print(f"❌ {test_file} timed out")
        return False
    except Exception as e:
        print(f"❌ {test_file} error: {e}")
        return False


def main() -> None:
    """Run all tests."""
    print("=== MicroPython Test Runner ===")

    # Check if MicroPython is available
    micropython_bin = "./micropython-local"
    if not os.path.exists(micropython_bin):
        print("MicroPython not found. Setting up...")
        setup_result = subprocess.run(
            ["./scripts/setup_micropython_test_env.sh"], capture_output=True, text=True
        )
        if setup_result.returncode != 0:
            print("❌ Failed to setup MicroPython")
            sys.exit(1)

    # Find all test files
    test_files = []
    for root, dirs, files in os.walk("tests"):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))

    if not test_files:
        print("No test files found")
        sys.exit(0)

    # Run tests
    passed = 0
    failed = 0

    for test_file in sorted(test_files):
        if run_test(test_file):
            passed += 1
        else:
            failed += 1
        print()

    # Summary
    print("=" * 40)
    print(f"Total: {passed + failed}, Passed: {passed}, Failed: {failed}")

    if failed == 0:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
