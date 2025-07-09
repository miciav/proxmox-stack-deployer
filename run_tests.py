#!/usr/bin/env python3
"""
Test runner script for deploy.py

This script provides different test execution modes:
- Unit tests only
- Integration tests only  
- All tests
- Coverage report
- Linting and code quality checks
"""

import sys
import subprocess
import argparse
import os


def run_command(cmd, description=""):
    """Run a command and handle errors"""
    if description:
        print(f"\n{'='*60}")
        print(f"Running: {description}")
        print(f"{'='*60}")
    
    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print(f"❌ {description} failed with exit code {result.returncode}")
        return False
    else:
        print(f"✅ {description} completed successfully")
        return True


def run_unit_tests():
    """Run only unit tests"""
    cmd = ["python", "-m", "pytest", "test_deploy.py::TestArgumentParsing", 
           "test_deploy.py::TestCommandExecution", "test_deploy.py::TestDeploymentFunctions",
           "test_deploy.py::TestMainFunction", "test_deploy.py::TestErrorHandling",
           "test_deploy.py::TestUtilities", "-v"]
    return run_command(cmd, "Unit Tests")


def run_integration_tests():
    """Run only integration tests"""
    cmd = ["python", "-m", "pytest", "test_deploy.py::TestIntegration", "-v"]
    return run_command(cmd, "Integration Tests")


def run_all_tests():
    """Run all tests"""
    cmd = ["python", "-m", "pytest", "test_deploy.py", "-v"]
    return run_command(cmd, "All Tests")


def run_coverage():
    """Run tests with coverage report"""
    cmd = ["python", "-m", "pytest", "test_deploy.py", "--cov=deploy", 
           "--cov-report=html", "--cov-report=term-missing", "-v"]
    return run_command(cmd, "Coverage Report")


def run_linting():
    """Run code quality checks"""
    success = True
    
    # Check if tools are available
    tools = ["black", "flake8", "mypy"]
    available_tools = []
    
    for tool in tools:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
            available_tools.append(tool)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"⚠️  {tool} not available, skipping...")
    
    if "black" in available_tools:
        if not run_command(["black", "--check", "deploy.py", "test_deploy.py"], 
                          "Code formatting check (black)"):
            success = False
    
    if "flake8" in available_tools:
        if not run_command(["flake8", "deploy.py", "test_deploy.py"], 
                          "Code style check (flake8)"):
            success = False
    
    if "mypy" in available_tools:
        if not run_command(["mypy", "deploy.py"], "Type checking (mypy)"):
            success = False
    
    return success


def main():
    parser = argparse.ArgumentParser(description="Test runner for deploy.py")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage")
    parser.add_argument("--lint", action="store_true", help="Run linting and code quality checks")
    parser.add_argument("--all", action="store_true", help="Run all tests and checks")
    
    args = parser.parse_args()
    
    # Check if pytest is available
    try:
        subprocess.run(["python", "-m", "pytest", "--version"], 
                      capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ pytest is not available. Please install it with:")
        print("   pip install -r requirements-test.txt")
        sys.exit(1)
    
    success = True
    
    if args.unit:
        success &= run_unit_tests()
    elif args.integration:
        success &= run_integration_tests()
    elif args.coverage:
        success &= run_coverage()
    elif args.lint:
        success &= run_linting()
    elif args.all:
        success &= run_all_tests()
        success &= run_linting()
    else:
        # Default: run all tests
        success &= run_all_tests()
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
