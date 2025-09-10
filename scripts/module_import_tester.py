#!/usr/bin/env python3
"""
Module Import Tester for Niryo LLM Robotics Platform

Tests each module individually to identify import issues and missing dependencies.
"""

import sys
import importlib
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

def test_module_import(module_name):
    """Test importing a single module."""
    try:
        print(f"Testing {module_name}...", end=" ")
        importlib.import_module(module_name)
        print("[PASS]")
        return True
    except ImportError as e:
        print(f"[FAIL] ImportError: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False

def main():
    """Test all modules systematically."""
    print("NIRYO LLM ROBOTICS PLATFORM - MODULE IMPORT TESTER")
    print("=" * 80)
    
    # Define modules to test in order of dependency
    modules_to_test = [
        # Core utilities (no dependencies)
        "utils.logger",
        "utils.config_manager",

        # Core robot functionality
        "core.robot_controller",
        "core.safety_manager",
        "core.movement_patterns",
        "core.trajectory_planner",
        "core.advanced_movement",

        # Vision system
        "vision.camera_manager",
        "vision.object_detector",
        "vision.image_processor",

        # Automation system
        "automation.conveyor_controller",
        "automation.coordination_manager",
        "automation.sensor_interface",
        "automation.workflow_executor",

        # LLM integration
        "llm.llm_interface",
        "llm.natural_language",
        "llm.output_parser",
        "llm.safety_validator",
        "llm.task_planner",
        "llm.educational_interface",

        # Interfaces
        "interfaces.voice_interface",
        "interfaces.gui_application",

        # API and applications
        "api.api_server",
        "applications.quality_control",

        # Extensions
        "extensions.plugin_framework"
    ]
    
    successful = []
    failed = []
    
    print(f"\nTesting {len(modules_to_test)} modules...\n")
    
    for module in modules_to_test:
        if test_module_import(module):
            successful.append(module)
        else:
            failed.append(module)
    
    # Summary
    print("\n" + "=" * 80)
    print("IMPORT TEST SUMMARY")
    print("=" * 80)
    
    print(f"Total modules tested: {len(modules_to_test)}")
    print(f"Successful imports: {len(successful)}")
    print(f"Failed imports: {len(failed)}")
    print(f"Success rate: {(len(successful)/len(modules_to_test))*100:.1f}%")
    
    if failed:
        print(f"\nFailed modules:")
        for module in failed:
            print(f"  - {module}")
    
    if successful:
        print(f"\nSuccessful modules:")
        for module in successful:
            print(f"  - {module}")
    
    return len(failed) == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
