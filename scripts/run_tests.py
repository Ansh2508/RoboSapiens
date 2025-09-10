#!/usr/bin/env python3
"""
Test Runner Script

This script provides a comprehensive test runner for the Niryo LLM Robotics Platform
with various testing options and reporting capabilities.

Usage:
    python scripts/run_tests.py [options]
"""

import sys
import subprocess
import argparse
from pathlib import Path
import time
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestRunner:
    """Comprehensive test runner with multiple execution modes."""
    
    def __init__(self):
        """Initialize test runner."""
        self.project_root = Path(__file__).parent.parent
        self.test_dir = self.project_root / "tests"
        
    def run_unit_tests(self, verbose: bool = False, coverage: bool = True) -> bool:
        """
        Run unit tests.
        
        Args:
            verbose: Enable verbose output
            coverage: Enable coverage reporting
            
        Returns:
            True if all tests pass, False otherwise
        """
        print("=" * 60)
        print("Running Unit Tests")
        print("=" * 60)
        
        cmd = ["python", "-m", "pytest", "tests/unit/"]
        
        if verbose:
            cmd.append("-v")
        
        if coverage:
            cmd.extend(["--cov=src", "--cov-report=term-missing"])
        
        cmd.extend(["--tb=short", "--color=yes"])
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            return result.returncode == 0
        except Exception as e:
            print(f"Error running unit tests: {e}")
            return False
    
    def run_integration_tests(self, verbose: bool = False) -> bool:
        """
        Run integration tests.
        
        Args:
            verbose: Enable verbose output
            
        Returns:
            True if all tests pass, False otherwise
        """
        print("=" * 60)
        print("Running Integration Tests")
        print("=" * 60)
        
        cmd = ["python", "-m", "pytest", "tests/integration/", "-m", "integration"]
        
        if verbose:
            cmd.append("-v")
        
        cmd.extend(["--tb=short", "--color=yes"])
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            return result.returncode == 0
        except Exception as e:
            print(f"Error running integration tests: {e}")
            return False
    
    def run_all_tests(self, verbose: bool = False, coverage: bool = True) -> bool:
        """
        Run all tests.
        
        Args:
            verbose: Enable verbose output
            coverage: Enable coverage reporting
            
        Returns:
            True if all tests pass, False otherwise
        """
        print("=" * 60)
        print("Running All Tests")
        print("=" * 60)
        
        cmd = ["python", "-m", "pytest", "tests/"]
        
        if verbose:
            cmd.append("-v")
        
        if coverage:
            cmd.extend([
                "--cov=src",
                "--cov-report=html:htmlcov",
                "--cov-report=term-missing",
                "--cov-report=xml"
            ])
        
        cmd.extend(["--tb=short", "--color=yes", "--durations=10"])
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            return result.returncode == 0
        except Exception as e:
            print(f"Error running all tests: {e}")
            return False
    
    def run_specific_test(self, test_path: str, verbose: bool = False) -> bool:
        """
        Run a specific test file or test function.
        
        Args:
            test_path: Path to test file or test function
            verbose: Enable verbose output
            
        Returns:
            True if test passes, False otherwise
        """
        print("=" * 60)
        print(f"Running Specific Test: {test_path}")
        print("=" * 60)
        
        cmd = ["python", "-m", "pytest", test_path]
        
        if verbose:
            cmd.append("-v")
        
        cmd.extend(["--tb=short", "--color=yes"])
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            return result.returncode == 0
        except Exception as e:
            print(f"Error running specific test: {e}")
            return False
    
    def run_hardware_tests(self, robot_ip: str = None, verbose: bool = False) -> bool:
        """
        Run hardware tests (requires physical robot).
        
        Args:
            robot_ip: Robot IP address
            verbose: Enable verbose output
            
        Returns:
            True if all tests pass, False otherwise
        """
        print("=" * 60)
        print("Running Hardware Tests")
        print("=" * 60)
        
        if robot_ip:
            os.environ["NIRYO_IP"] = robot_ip
            print(f"Using robot IP: {robot_ip}")
        
        cmd = ["python", "-m", "pytest", "tests/", "-m", "hardware"]
        
        if verbose:
            cmd.append("-v")
        
        cmd.extend(["--tb=short", "--color=yes"])
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            return result.returncode == 0
        except Exception as e:
            print(f"Error running hardware tests: {e}")
            return False
    
    def run_connection_test(self, robot_ip: str = None, verbose: bool = False) -> bool:
        """
        Run connection test script.
        
        Args:
            robot_ip: Robot IP address
            verbose: Enable verbose output
            
        Returns:
            True if connection test passes, False otherwise
        """
        print("=" * 60)
        print("Running Connection Test")
        print("=" * 60)
        
        cmd = ["python", "scripts/test_connection.py"]
        
        if robot_ip:
            cmd.extend(["--ip", robot_ip])
        
        if verbose:
            cmd.append("--verbose")
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            return result.returncode == 0
        except Exception as e:
            print(f"Error running connection test: {e}")
            return False
    
    def generate_coverage_report(self) -> bool:
        """
        Generate detailed coverage report.
        
        Returns:
            True if report generation succeeds, False otherwise
        """
        print("=" * 60)
        print("Generating Coverage Report")
        print("=" * 60)
        
        cmd = [
            "python", "-m", "pytest", "tests/",
            "--cov=src",
            "--cov-report=html:htmlcov",
            "--cov-report=xml",
            "--cov-report=term"
        ]
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            
            if result.returncode == 0:
                print("\nCoverage reports generated:")
                print(f"  HTML: {self.project_root}/htmlcov/index.html")
                print(f"  XML:  {self.project_root}/coverage.xml")
                return True
            else:
                print("Coverage report generation failed")
                return False
                
        except Exception as e:
            print(f"Error generating coverage report: {e}")
            return False
    
    def run_performance_tests(self, verbose: bool = False) -> bool:
        """
        Run performance tests.
        
        Args:
            verbose: Enable verbose output
            
        Returns:
            True if all tests pass, False otherwise
        """
        print("=" * 60)
        print("Running Performance Tests")
        print("=" * 60)
        
        cmd = ["python", "-m", "pytest", "tests/", "-k", "performance"]
        
        if verbose:
            cmd.append("-v")
        
        cmd.extend(["--tb=short", "--color=yes", "--durations=0"])
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            return result.returncode == 0
        except Exception as e:
            print(f"Error running performance tests: {e}")
            return False
    
    def check_test_environment(self) -> bool:
        """
        Check if test environment is properly set up.
        
        Returns:
            True if environment is ready, False otherwise
        """
        print("Checking test environment...")
        
        # Check Python version
        if sys.version_info < (3, 9):
            print(f"❌ Python 3.9+ required, found {sys.version_info.major}.{sys.version_info.minor}")
            return False
        else:
            print(f"✅ Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        
        # Check required packages
        required_packages = ["pytest", "pytest-cov", "pydantic", "click", "rich"]
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
                print(f"✅ Package {package}: OK")
            except ImportError:
                missing_packages.append(package)
                print(f"❌ Package {package}: MISSING")
        
        if missing_packages:
            print(f"\nMissing packages: {', '.join(missing_packages)}")
            print("Install with: pip install -r requirements.txt")
            return False
        
        # Check test directory structure
        required_dirs = ["tests/unit", "tests/integration", "tests/fixtures"]
        for test_dir in required_dirs:
            dir_path = self.project_root / test_dir
            if dir_path.exists():
                print(f"✅ Directory {test_dir}: OK")
            else:
                print(f"❌ Directory {test_dir}: MISSING")
                return False
        
        print("✅ Test environment is ready")
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test runner for Niryo LLM Robotics Platform")
    parser.add_argument("--mode", choices=["unit", "integration", "all", "hardware", "connection", "coverage", "performance", "check"], 
                       default="all", help="Test mode to run")
    parser.add_argument("--test", help="Specific test file or function to run")
    parser.add_argument("--ip", help="Robot IP address for hardware tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--no-coverage", action="store_true", help="Disable coverage reporting")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    # Check environment first
    if not runner.check_test_environment():
        print("\n❌ Test environment check failed")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("Niryo LLM Robotics Platform - Test Runner")
    print("=" * 60)
    
    start_time = time.time()
    success = False
    
    try:
        if args.test:
            success = runner.run_specific_test(args.test, args.verbose)
        elif args.mode == "unit":
            success = runner.run_unit_tests(args.verbose, not args.no_coverage)
        elif args.mode == "integration":
            success = runner.run_integration_tests(args.verbose)
        elif args.mode == "all":
            success = runner.run_all_tests(args.verbose, not args.no_coverage)
        elif args.mode == "hardware":
            success = runner.run_hardware_tests(args.ip, args.verbose)
        elif args.mode == "connection":
            success = runner.run_connection_test(args.ip, args.verbose)
        elif args.mode == "coverage":
            success = runner.generate_coverage_report()
        elif args.mode == "performance":
            success = runner.run_performance_tests(args.verbose)
        elif args.mode == "check":
            success = True  # Already checked environment above
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "=" * 60)
        if success:
            print(f"✅ Tests completed successfully in {elapsed_time:.2f}s")
        else:
            print(f"❌ Tests failed after {elapsed_time:.2f}s")
        print("=" * 60)
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
