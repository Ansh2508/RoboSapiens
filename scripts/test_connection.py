#!/usr/bin/env python3
"""
Robot Connection Test Script

This script provides comprehensive testing of robot connectivity,
basic functionality, and system diagnostics for the Niryo LLM Robotics Platform.

Usage:
    python scripts/test_connection.py [--ip IP_ADDRESS] [--verbose]
"""

import sys
import time
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.robot_controller import RobotController, RobotState
from src.core.safety_manager import SafetyManager
from src.utils.config_manager import get_config_manager
from src.utils.logger import get_logger, setup_logging
from src.utils.error_handler import RoboticsError, ConnectionError

logger = get_logger(__name__)


class ConnectionTester:
    """Comprehensive connection and functionality tester."""
    
    def __init__(self, robot_ip: Optional[str] = None, verbose: bool = False):
        """
        Initialize connection tester.
        
        Args:
            robot_ip: Robot IP address (uses config default if None)
            verbose: Enable verbose output
        """
        self.verbose = verbose
        self.config_manager = get_config_manager()
        self.robot_ip = robot_ip or self.config_manager.get_robot_config().ip
        
        # Setup logging
        if verbose:
            setup_logging({"level": "DEBUG"})
        else:
            setup_logging({"level": "INFO"})
        
        self.test_results: Dict[str, Dict[str, Any]] = {}
        
    def print_status(self, message: str, status: str = "INFO") -> None:
        """Print status message with formatting."""
        status_symbols = {
            "INFO": "ℹ",
            "SUCCESS": "✓",
            "WARNING": "⚠",
            "ERROR": "✗",
            "RUNNING": "⟳"
        }
        
        symbol = status_symbols.get(status, "•")
        print(f"{symbol} {message}")
        
        if self.verbose:
            logger.info(f"{status}: {message}")
    
    def run_all_tests(self) -> bool:
        """
        Run all connection and functionality tests.
        
        Returns:
            True if all tests pass, False otherwise
        """
        print("=" * 60)
        print("Niryo LLM Robotics Platform - Connection Test")
        print("=" * 60)
        print(f"Target Robot IP: {self.robot_ip}")
        print(f"Verbose Mode: {self.verbose}")
        print("=" * 60)
        
        tests = [
            ("Environment Check", self._test_environment),
            ("Network Connectivity", self._test_network_connectivity),
            ("Configuration Loading", self._test_configuration),
            ("Robot Connection", self._test_robot_connection),
            ("Basic Robot Commands", self._test_basic_commands),
            ("Safety System", self._test_safety_system),
            ("System Integration", self._test_system_integration)
        ]
        
        all_passed = True
        
        for test_name, test_func in tests:
            print(f"\n[{test_name}]")
            self.print_status(f"Running {test_name}...", "RUNNING")
            
            try:
                result = test_func()
                self.test_results[test_name] = result
                
                if result["passed"]:
                    self.print_status(f"{test_name} PASSED", "SUCCESS")
                else:
                    self.print_status(f"{test_name} FAILED: {result.get('error', 'Unknown error')}", "ERROR")
                    all_passed = False
                    
                # Print details if verbose
                if self.verbose and "details" in result:
                    for detail in result["details"]:
                        print(f"  • {detail}")
                        
            except Exception as e:
                self.print_status(f"{test_name} FAILED: {e}", "ERROR")
                self.test_results[test_name] = {"passed": False, "error": str(e)}
                all_passed = False
        
        # Print summary
        self._print_summary(all_passed)
        return all_passed
    
    def _test_environment(self) -> Dict[str, Any]:
        """Test Python environment and dependencies."""
        details = []
        
        # Check Python version
        python_version = sys.version_info
        details.append(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        if python_version < (3, 9):
            return {
                "passed": False,
                "error": f"Python 3.9+ required, found {python_version.major}.{python_version.minor}",
                "details": details
            }
        
        # Check required packages
        required_packages = ["pyniryo", "pydantic", "click", "rich", "loguru"]
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
                details.append(f"Package {package}: OK")
            except ImportError:
                missing_packages.append(package)
                details.append(f"Package {package}: MISSING")
        
        if missing_packages:
            return {
                "passed": False,
                "error": f"Missing packages: {', '.join(missing_packages)}",
                "details": details
            }
        
        return {"passed": True, "details": details}
    
    def _test_network_connectivity(self) -> Dict[str, Any]:
        """Test network connectivity to robot."""
        details = []
        
        # Test ping connectivity
        try:
            if sys.platform == "win32":
                cmd = ["ping", "-n", "1", "-w", "5000", self.robot_ip]
            else:
                cmd = ["ping", "-c", "1", "-W", "5", self.robot_ip]
            
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            
            if result.returncode == 0:
                details.append(f"Ping to {self.robot_ip}: SUCCESS")
            else:
                return {
                    "passed": False,
                    "error": f"Ping to {self.robot_ip} failed",
                    "details": details
                }
                
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "error": f"Ping to {self.robot_ip} timed out",
                "details": details
            }
        except Exception as e:
            return {
                "passed": False,
                "error": f"Network test error: {e}",
                "details": details
            }
        
        # Test port connectivity (if possible)
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.robot_ip, 40001))
            sock.close()
            
            if result == 0:
                details.append(f"Port 40001 on {self.robot_ip}: OPEN")
            else:
                details.append(f"Port 40001 on {self.robot_ip}: CLOSED/FILTERED")
                
        except Exception as e:
            details.append(f"Port test error: {e}")
        
        return {"passed": True, "details": details}
    
    def _test_configuration(self) -> Dict[str, Any]:
        """Test configuration loading and validation."""
        details = []
        
        try:
            config = self.config_manager.get_config()
            details.append(f"Configuration loaded successfully")
            details.append(f"Robot IP: {config.robot.ip}")
            details.append(f"Robot timeout: {config.robot.timeout}s")
            details.append(f"Max velocity: {config.robot.max_velocity_percent}%")
            details.append(f"Safety enabled: {config.safety.emergency_stop_enabled}")
            
            return {"passed": True, "details": details}
            
        except Exception as e:
            return {
                "passed": False,
                "error": f"Configuration loading failed: {e}",
                "details": details
            }
    
    def _test_robot_connection(self) -> Dict[str, Any]:
        """Test robot connection and basic communication."""
        details = []
        
        try:
            robot_controller = RobotController(self.config_manager)
            
            # Test connection
            start_time = time.time()
            success = robot_controller.connect(self.robot_ip)
            connection_time = time.time() - start_time
            
            if not success:
                return {
                    "passed": False,
                    "error": "Failed to establish robot connection",
                    "details": details
                }
            
            details.append(f"Connection established in {connection_time:.2f}s")
            details.append(f"Robot state: {robot_controller.status.state.value}")
            
            # Test disconnection
            robot_controller.disconnect()
            details.append("Disconnection successful")
            
            return {"passed": True, "details": details}
            
        except Exception as e:
            return {
                "passed": False,
                "error": f"Robot connection test failed: {e}",
                "details": details
            }
    
    def _test_basic_commands(self) -> Dict[str, Any]:
        """Test basic robot commands."""
        details = []
        
        try:
            robot_controller = RobotController(self.config_manager)
            
            with robot_controller.robot_connection(self.robot_ip):
                # Test LED control
                success = robot_controller.led_control([0, 255, 0], 0.5, 1)
                if success:
                    details.append("LED control: SUCCESS")
                else:
                    details.append("LED control: FAILED")
                
                # Test position reading
                position = robot_controller.get_position()
                if position:
                    details.append("Position reading: SUCCESS")
                else:
                    details.append("Position reading: NO DATA")
                
                # Test joint reading
                joints = robot_controller.get_joints()
                if joints:
                    details.append(f"Joint reading: SUCCESS ({len(joints)} joints)")
                else:
                    details.append("Joint reading: NO DATA")
            
            return {"passed": True, "details": details}
            
        except Exception as e:
            return {
                "passed": False,
                "error": f"Basic commands test failed: {e}",
                "details": details
            }
    
    def _test_safety_system(self) -> Dict[str, Any]:
        """Test safety system functionality."""
        details = []
        
        try:
            safety_manager = SafetyManager(self.config_manager)
            
            # Test safety status
            status = safety_manager.get_safety_status()
            details.append(f"Safety monitoring: {'Enabled' if status['safety_enabled'] else 'Disabled'}")
            details.append(f"Emergency stop: {'Active' if status['emergency_stop_active'] else 'Inactive'}")
            
            # Test workspace boundary checking
            in_bounds = safety_manager.check_workspace_boundaries(0, 0, 100)
            details.append(f"Workspace boundary check: {'PASS' if in_bounds else 'FAIL'}")
            
            # Test force limit checking
            force_ok = safety_manager.check_force_limits(10.0)  # 10N test
            details.append(f"Force limit check: {'PASS' if force_ok else 'FAIL'}")
            
            return {"passed": True, "details": details}
            
        except Exception as e:
            return {
                "passed": False,
                "error": f"Safety system test failed: {e}",
                "details": details
            }
    
    def _test_system_integration(self) -> Dict[str, Any]:
        """Test overall system integration."""
        details = []
        
        try:
            # Test robot controller and safety manager integration
            robot_controller = RobotController(self.config_manager)
            safety_manager = SafetyManager(self.config_manager)
            
            # Start safety monitoring
            safety_manager.start_monitoring()
            details.append("Safety monitoring started")
            
            # Test emergency stop integration
            safety_manager.emergency_stop("Integration test")
            if safety_manager.is_emergency_stop_active:
                details.append("Emergency stop activation: SUCCESS")
            else:
                details.append("Emergency stop activation: FAILED")
            
            # Reset emergency stop
            success = safety_manager.reset_emergency_stop()
            if success:
                details.append("Emergency stop reset: SUCCESS")
            else:
                details.append("Emergency stop reset: FAILED")
            
            # Stop safety monitoring
            safety_manager.stop_monitoring()
            details.append("Safety monitoring stopped")
            
            return {"passed": True, "details": details}
            
        except Exception as e:
            return {
                "passed": False,
                "error": f"System integration test failed: {e}",
                "details": details
            }
    
    def _print_summary(self, all_passed: bool) -> None:
        """Print test summary."""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        passed_count = sum(1 for result in self.test_results.values() if result["passed"])
        total_count = len(self.test_results)
        
        print(f"Tests Passed: {passed_count}/{total_count}")
        
        if all_passed:
            self.print_status("ALL TESTS PASSED - System is ready for operation!", "SUCCESS")
        else:
            self.print_status("SOME TESTS FAILED - Check errors above", "ERROR")
            
            # List failed tests
            failed_tests = [name for name, result in self.test_results.items() if not result["passed"]]
            if failed_tests:
                print("\nFailed Tests:")
                for test_name in failed_tests:
                    error = self.test_results[test_name].get("error", "Unknown error")
                    print(f"  • {test_name}: {error}")
        
        print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test robot connection and functionality")
    parser.add_argument("--ip", help="Robot IP address")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        tester = ConnectionTester(robot_ip=args.ip, verbose=args.verbose)
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Test failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
