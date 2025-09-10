"""
Educational Demonstrations for Phase 4

This script provides comprehensive educational demonstrations for Phase 4
conveyor belt coordination and advanced automation systems, designed for
the Bavarian-Czech Summer School 2025.

Features:
- Progressive workshop activities from basic to advanced
- Visual debugging tools and real-time monitoring
- Interactive demonstrations with student participation
- Performance metrics and progress tracking
- Comprehensive error handling and recovery
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from core.robot_controller import RobotController
from automation.conveyor_controller import ConveyorController, ConveyorDirection
from automation.sensor_interface import SensorInterface, SensorConfiguration, SensorType
from automation.coordination_manager import CoordinationManager
from automation.workflow_executor import WorkflowExecutor
from vision.camera_interface import CameraInterface
from vision.object_detector import ObjectDetector
from vision.workspace_calibrator import WorkspaceCalibrator
from utils.logger import get_logger

logger = get_logger(__name__)


class EducationalDemonstrator:
    """
    Educational demonstration system for Phase 4 conveyor belt coordination
    and advanced automation workflows.
    """
    
    def __init__(self, robot_ip: str = "127.0.0.1"):
        """
        Initialize educational demonstrator.
        
        Args:
            robot_ip: IP address of Niryo robot
        """
        self.robot_ip = robot_ip
        
        # Initialize components
        self.robot_controller = RobotController(robot_ip)
        self.conveyor_controller = ConveyorController(robot_ip)
        self.sensor_interface = SensorInterface(robot_ip)
        self.camera_interface = CameraInterface()
        self.object_detector = ObjectDetector(self.camera_interface)
        self.workspace_calibrator = WorkspaceCalibrator(
            self.camera_interface,
            self.robot_controller,
            self.object_detector
        )
        
        # Initialize coordination and workflow systems
        self.coordination_manager = CoordinationManager(
            self.robot_controller,
            self.conveyor_controller,
            self.sensor_interface,
            self.camera_interface,
            self.object_detector,
            self.workspace_calibrator
        )
        
        self.workflow_executor = WorkflowExecutor(
            self.coordination_manager,
            self.robot_controller,
            None,  # advanced_movement not needed for basic demos
            self.conveyor_controller,
            self.sensor_interface,
            self.camera_interface,
            self.object_detector,
            self.workspace_calibrator
        )
        
        # Demo state
        self.demo_results: List[Dict[str, Any]] = []
        self.current_demo: Optional[str] = None
        
        logger.info("Educational demonstrator initialized")
    
    def setup_system(self) -> bool:
        """
        Setup and initialize all system components.
        
        Returns:
            True if setup successful
        """
        logger.info("Setting up educational demonstration system...")
        
        try:
            # Connect components
            success = True
            success &= self.robot_controller.connect()
            success &= self.conveyor_controller.connect()
            success &= self.sensor_interface.connect()
            success &= self.camera_interface.connect()
            
            if not success:
                logger.error("Failed to connect to system components")
                return False
            
            # Setup sensors
            self._setup_demo_sensors()
            
            # Initialize coordination system
            success = self.coordination_manager.initialize()
            if not success:
                logger.error("Failed to initialize coordination system")
                return False
            
            # Start workflow executor
            success = self.workflow_executor.start_executor()
            if not success:
                logger.error("Failed to start workflow executor")
                return False
            
            logger.info("Educational demonstration system setup complete")
            return True
            
        except Exception as e:
            logger.error(f"Error during system setup: {e}")
            return False
    
    def _setup_demo_sensors(self) -> None:
        """Setup sensors for educational demonstrations."""
        # Conveyor entry sensor
        entry_sensor = SensorConfiguration(
            sensor_id="conveyor_entry",
            sensor_type=SensorType.INFRARED,
            pin_number=18,  # GPIO pin
            position_on_belt=0.0,  # Start of conveyor
            trigger_threshold=0.7
        )
        
        # Conveyor exit sensor
        exit_sensor = SensorConfiguration(
            sensor_id="conveyor_exit",
            sensor_type=SensorType.INFRARED,
            pin_number=19,  # GPIO pin
            position_on_belt=500.0,  # End of conveyor (500mm)
            trigger_threshold=0.7
        )
        
        # Add sensors to interface
        self.sensor_interface.add_sensor(entry_sensor)
        self.sensor_interface.add_sensor(exit_sensor)
        
        # Activate sensors
        self.sensor_interface.activate_sensor("conveyor_entry")
        self.sensor_interface.activate_sensor("conveyor_exit")
        
        logger.info("Demo sensors configured and activated")
    
    def run_demo_1_basic_conveyor(self) -> Dict[str, Any]:
        """
        Demo 1: Basic Conveyor Belt Control
        
        Learning objectives:
        - Understand conveyor belt operation
        - Learn speed and direction control
        - Observe safety systems
        
        Returns:
            Demo results dictionary
        """
        self.current_demo = "basic_conveyor"
        logger.info("Starting Demo 1: Basic Conveyor Belt Control")
        
        demo_result = {
            'demo_name': 'Basic Conveyor Belt Control',
            'start_time': time.time(),
            'steps': [],
            'success': False,
            'learning_points': [],
            'performance_metrics': {}
        }
        
        try:
            # Step 1: Start conveyor forward
            logger.info("Step 1: Starting conveyor forward at 30 mm/s")
            success = self.conveyor_controller.start(30.0, ConveyorDirection.FORWARD)
            demo_result['steps'].append({
                'step': 'start_forward',
                'success': success,
                'timestamp': time.time()
            })
            
            if success:
                demo_result['learning_points'].append("Conveyor can move forward at controlled speeds")
                time.sleep(3)  # Run for 3 seconds
                
                # Step 2: Change speed
                logger.info("Step 2: Changing speed to 60 mm/s")
                success = self.conveyor_controller.change_speed(60.0)
                demo_result['steps'].append({
                    'step': 'change_speed',
                    'success': success,
                    'timestamp': time.time()
                })
                
                if success:
                    demo_result['learning_points'].append("Conveyor speed can be adjusted dynamically")
                    time.sleep(2)
                    
                    # Step 3: Reverse direction
                    logger.info("Step 3: Reversing conveyor direction")
                    success = self.conveyor_controller.reverse_direction()
                    demo_result['steps'].append({
                        'step': 'reverse_direction',
                        'success': success,
                        'timestamp': time.time()
                    })
                    
                    if success:
                        demo_result['learning_points'].append("Conveyor can reverse direction while running")
                        time.sleep(3)
            
            # Step 4: Stop conveyor
            logger.info("Step 4: Stopping conveyor")
            success = self.conveyor_controller.stop()
            demo_result['steps'].append({
                'step': 'stop_conveyor',
                'success': success,
                'timestamp': time.time()
            })
            
            if success:
                demo_result['learning_points'].append("Conveyor can be stopped safely")
            
            # Check overall success
            demo_result['success'] = all(step['success'] for step in demo_result['steps'])
            
            # Performance metrics
            demo_result['performance_metrics'] = {
                'total_runtime': time.time() - demo_result['start_time'],
                'steps_completed': len([s for s in demo_result['steps'] if s['success']]),
                'conveyor_status': self.conveyor_controller.get_status()
            }
            
            logger.info(f"Demo 1 completed - Success: {demo_result['success']}")
            
        except Exception as e:
            logger.error(f"Error in Demo 1: {e}")
            demo_result['error'] = str(e)
        
        finally:
            # Ensure conveyor is stopped
            self.conveyor_controller.stop()
            demo_result['completion_time'] = time.time()
            self.demo_results.append(demo_result)
        
        return demo_result
    
    def run_demo_2_sensor_integration(self) -> Dict[str, Any]:
        """
        Demo 2: Sensor Integration and Object Detection
        
        Learning objectives:
        - Understand sensor operation and calibration
        - Learn object detection and tracking
        - Observe sensor-conveyor coordination
        
        Returns:
            Demo results dictionary
        """
        self.current_demo = "sensor_integration"
        logger.info("Starting Demo 2: Sensor Integration and Object Detection")
        
        demo_result = {
            'demo_name': 'Sensor Integration and Object Detection',
            'start_time': time.time(),
            'steps': [],
            'success': False,
            'learning_points': [],
            'performance_metrics': {}
        }
        
        try:
            # Step 1: Calibrate sensors
            logger.info("Step 1: Calibrating sensors")
            entry_success = self.sensor_interface.calibrate_sensor("conveyor_entry")
            exit_success = self.sensor_interface.calibrate_sensor("conveyor_exit")
            
            demo_result['steps'].append({
                'step': 'calibrate_sensors',
                'success': entry_success and exit_success,
                'timestamp': time.time()
            })
            
            if entry_success and exit_success:
                demo_result['learning_points'].append("Sensors must be calibrated for accurate detection")
                
                # Step 2: Start conveyor and monitor sensors
                logger.info("Step 2: Starting conveyor and monitoring sensors")
                conveyor_success = self.conveyor_controller.start(40.0, ConveyorDirection.FORWARD)
                
                if conveyor_success:
                    demo_result['steps'].append({
                        'step': 'start_monitoring',
                        'success': True,
                        'timestamp': time.time()
                    })
                    
                    # Monitor for 10 seconds
                    monitor_start = time.time()
                    objects_detected = 0
                    
                    while (time.time() - monitor_start) < 10.0:
                        tracked_objects = self.sensor_interface.get_tracked_objects()
                        if len(tracked_objects) > objects_detected:
                            objects_detected = len(tracked_objects)
                            logger.info(f"Object detected! Total objects: {objects_detected}")
                        
                        time.sleep(0.1)
                    
                    demo_result['steps'].append({
                        'step': 'object_detection',
                        'success': objects_detected > 0,
                        'objects_detected': objects_detected,
                        'timestamp': time.time()
                    })
                    
                    if objects_detected > 0:
                        demo_result['learning_points'].append(f"Sensors detected {objects_detected} objects")
                        demo_result['learning_points'].append("Object tracking provides speed and position data")
                    else:
                        demo_result['learning_points'].append("No objects detected - sensors are ready for objects")
            
            # Step 3: Stop conveyor
            logger.info("Step 3: Stopping conveyor")
            success = self.conveyor_controller.stop()
            demo_result['steps'].append({
                'step': 'stop_conveyor',
                'success': success,
                'timestamp': time.time()
            })
            
            # Check overall success
            demo_result['success'] = all(step['success'] for step in demo_result['steps'])
            
            # Performance metrics
            demo_result['performance_metrics'] = {
                'total_runtime': time.time() - demo_result['start_time'],
                'steps_completed': len([s for s in demo_result['steps'] if s['success']]),
                'sensor_status': self.sensor_interface.get_all_sensor_status(),
                'objects_tracked': len(self.sensor_interface.get_tracked_objects())
            }
            
            logger.info(f"Demo 2 completed - Success: {demo_result['success']}")
            
        except Exception as e:
            logger.error(f"Error in Demo 2: {e}")
            demo_result['error'] = str(e)
        
        finally:
            # Ensure conveyor is stopped
            self.conveyor_controller.stop()
            demo_result['completion_time'] = time.time()
            self.demo_results.append(demo_result)
        
        return demo_result
    
    def run_demo_3_vision_conveyor_coordination(self) -> Dict[str, Any]:
        """
        Demo 3: Vision-Conveyor Coordination
        
        Learning objectives:
        - Understand vision-sensor handoff
        - Learn coordinated system operation
        - Observe real-time decision making
        
        Returns:
            Demo results dictionary
        """
        self.current_demo = "vision_conveyor_coordination"
        logger.info("Starting Demo 3: Vision-Conveyor Coordination")
        
        demo_result = {
            'demo_name': 'Vision-Conveyor Coordination',
            'start_time': time.time(),
            'steps': [],
            'success': False,
            'learning_points': [],
            'performance_metrics': {}
        }
        
        try:
            # Step 1: Initialize vision system
            logger.info("Step 1: Initializing vision system")
            if not self.workspace_calibrator.is_calibrated:
                # Perform quick calibration for demo
                logger.info("Performing workspace calibration...")
                calib_success = self.workspace_calibrator.calibrate_workspace()
            else:
                calib_success = True
            
            demo_result['steps'].append({
                'step': 'vision_initialization',
                'success': calib_success,
                'timestamp': time.time()
            })
            
            if calib_success:
                demo_result['learning_points'].append("Vision system requires workspace calibration")
                
                # Step 2: Execute vision-conveyor handoff
                logger.info("Step 2: Executing vision-conveyor handoff")
                handoff_success = self.coordination_manager.execute_synchronized_operation(
                    "vision_handoff",
                    {
                        'timeout': 15.0,
                        'sensor_timeout': 10.0
                    }
                )
                
                demo_result['steps'].append({
                    'step': 'vision_handoff',
                    'success': handoff_success,
                    'timestamp': time.time()
                })
                
                if handoff_success:
                    demo_result['learning_points'].append("Vision and sensors can coordinate object detection")
                    demo_result['learning_points'].append("Handoff protocols ensure reliable object tracking")
            
            # Check overall success
            demo_result['success'] = all(step['success'] for step in demo_result['steps'])
            
            # Performance metrics
            demo_result['performance_metrics'] = {
                'total_runtime': time.time() - demo_result['start_time'],
                'steps_completed': len([s for s in demo_result['steps'] if s['success']]),
                'coordination_status': self.coordination_manager.get_system_status(),
                'calibration_accuracy': self.workspace_calibrator.get_calibration_info().get('accuracy', 0.0)
            }
            
            logger.info(f"Demo 3 completed - Success: {demo_result['success']}")
            
        except Exception as e:
            logger.error(f"Error in Demo 3: {e}")
            demo_result['error'] = str(e)
        
        finally:
            demo_result['completion_time'] = time.time()
            self.demo_results.append(demo_result)
        
        return demo_result

    def run_demo_4_complete_automation(self) -> Dict[str, Any]:
        """
        Demo 4: Complete Automation Workflow

        Learning objectives:
        - Understand end-to-end automation
        - Learn workflow execution and monitoring
        - Observe error recovery and retry mechanisms

        Returns:
            Demo results dictionary
        """
        self.current_demo = "complete_automation"
        logger.info("Starting Demo 4: Complete Automation Workflow")

        demo_result = {
            'demo_name': 'Complete Automation Workflow',
            'start_time': time.time(),
            'steps': [],
            'success': False,
            'learning_points': [],
            'performance_metrics': {}
        }

        try:
            # Step 1: Execute conveyor sorting workflow
            logger.info("Step 1: Executing conveyor sorting workflow")
            execution_id = self.workflow_executor.execute_workflow("conveyor_sorting")

            demo_result['steps'].append({
                'step': 'start_workflow',
                'success': execution_id is not None,
                'execution_id': execution_id,
                'timestamp': time.time()
            })

            if execution_id:
                demo_result['learning_points'].append("Workflows provide structured automation sequences")

                # Monitor workflow execution
                logger.info("Step 2: Monitoring workflow execution")
                monitor_start = time.time()
                workflow_completed = False

                while (time.time() - monitor_start) < 30.0:  # 30 second timeout
                    status = self.workflow_executor.get_workflow_status(execution_id)

                    if status and status['state'] in ['completed', 'failed', 'cancelled']:
                        workflow_completed = True
                        break

                    time.sleep(1.0)

                demo_result['steps'].append({
                    'step': 'monitor_workflow',
                    'success': workflow_completed,
                    'final_status': status['state'] if status else 'unknown',
                    'timestamp': time.time()
                })

                if workflow_completed and status['state'] == 'completed':
                    demo_result['learning_points'].append("Workflow executed successfully with all steps completed")
                    demo_result['learning_points'].append("Automation systems can handle complex multi-step processes")
                elif workflow_completed:
                    demo_result['learning_points'].append(f"Workflow ended with status: {status['state']}")
                    demo_result['learning_points'].append("Error recovery mechanisms help handle failures")

            # Check overall success
            demo_result['success'] = all(step['success'] for step in demo_result['steps'])

            # Performance metrics
            demo_result['performance_metrics'] = {
                'total_runtime': time.time() - demo_result['start_time'],
                'steps_completed': len([s for s in demo_result['steps'] if s['success']]),
                'workflow_statistics': self.workflow_executor.get_statistics(),
                'final_workflow_status': self.workflow_executor.get_workflow_status(execution_id) if execution_id else None
            }

            logger.info(f"Demo 4 completed - Success: {demo_result['success']}")

        except Exception as e:
            logger.error(f"Error in Demo 4: {e}")
            demo_result['error'] = str(e)

        finally:
            demo_result['completion_time'] = time.time()
            self.demo_results.append(demo_result)

        return demo_result

    def run_all_demos(self) -> Dict[str, Any]:
        """
        Run all educational demonstrations in sequence.

        Returns:
            Summary of all demo results
        """
        logger.info("Starting complete educational demonstration sequence")

        overall_start = time.time()

        # Run all demos
        demo1_result = self.run_demo_1_basic_conveyor()
        demo2_result = self.run_demo_2_sensor_integration()
        demo3_result = self.run_demo_3_vision_conveyor_coordination()
        demo4_result = self.run_demo_4_complete_automation()

        # Compile summary
        summary = {
            'total_runtime': time.time() - overall_start,
            'demos_run': 4,
            'demos_successful': sum(1 for result in self.demo_results if result['success']),
            'overall_success': all(result['success'] for result in self.demo_results),
            'learning_points_total': sum(len(result['learning_points']) for result in self.demo_results),
            'demo_results': self.demo_results.copy()
        }

        logger.info(f"All demos completed - Overall success: {summary['overall_success']}")
        logger.info(f"Total learning points covered: {summary['learning_points_total']}")

        return summary

    def print_demo_summary(self, demo_result: Dict[str, Any]) -> None:
        """Print formatted demo summary."""
        print(f"\n{'='*60}")
        print(f"DEMO SUMMARY: {demo_result['demo_name']}")
        print(f"{'='*60}")
        print(f"Success: {'✓' if demo_result['success'] else '✗'}")
        print(f"Runtime: {demo_result.get('total_runtime', 0):.2f} seconds")
        print(f"Steps completed: {len([s for s in demo_result['steps'] if s['success']])}/{len(demo_result['steps'])}")

        print(f"\nLearning Points:")
        for i, point in enumerate(demo_result['learning_points'], 1):
            print(f"  {i}. {point}")

        if 'error' in demo_result:
            print(f"\nError: {demo_result['error']}")

        print(f"{'='*60}\n")

    def shutdown_system(self) -> None:
        """Shutdown all system components safely."""
        logger.info("Shutting down educational demonstration system...")

        try:
            # Stop workflow executor
            self.workflow_executor.stop_executor()

            # Shutdown coordination manager
            self.coordination_manager.shutdown()

            # Disconnect components
            self.conveyor_controller.disconnect()
            self.sensor_interface.disconnect()
            self.camera_interface.disconnect()
            self.robot_controller.disconnect()

            logger.info("Educational demonstration system shutdown complete")

        except Exception as e:
            logger.error(f"Error during system shutdown: {e}")


def main():
    """Main function for running educational demonstrations."""
    parser = argparse.ArgumentParser(description="Phase 4 Educational Demonstrations")
    parser.add_argument("--robot-ip", default="127.0.0.1", help="Robot IP address")
    parser.add_argument("--demo", choices=["1", "2", "3", "4", "all"], default="all",
                       help="Demo to run (1-4 or all)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Initialize demonstrator
    demonstrator = EducationalDemonstrator(args.robot_ip)

    try:
        # Setup system
        if not demonstrator.setup_system():
            print("Failed to setup demonstration system")
            return 1

        print("Phase 4 Educational Demonstrations")
        print("Bavarian-Czech Summer School 2025")
        print("Conveyor Belt Coordination and Advanced Automation\n")

        # Run selected demo(s)
        if args.demo == "1":
            result = demonstrator.run_demo_1_basic_conveyor()
            demonstrator.print_demo_summary(result)
        elif args.demo == "2":
            result = demonstrator.run_demo_2_sensor_integration()
            demonstrator.print_demo_summary(result)
        elif args.demo == "3":
            result = demonstrator.run_demo_3_vision_conveyor_coordination()
            demonstrator.print_demo_summary(result)
        elif args.demo == "4":
            result = demonstrator.run_demo_4_complete_automation()
            demonstrator.print_demo_summary(result)
        elif args.demo == "all":
            summary = demonstrator.run_all_demos()

            # Print individual demo summaries
            for result in demonstrator.demo_results:
                demonstrator.print_demo_summary(result)

            # Print overall summary
            print(f"\n{'='*60}")
            print("OVERALL DEMONSTRATION SUMMARY")
            print(f"{'='*60}")
            print(f"Total runtime: {summary['total_runtime']:.2f} seconds")
            print(f"Demos successful: {summary['demos_successful']}/{summary['demos_run']}")
            print(f"Overall success: {'✓' if summary['overall_success'] else '✗'}")
            print(f"Learning points covered: {summary['learning_points_total']}")
            print(f"{'='*60}")

        return 0

    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
        return 1
    except Exception as e:
        print(f"Demo failed with error: {e}")
        return 1
    finally:
        demonstrator.shutdown_system()


if __name__ == "__main__":
    exit(main())
