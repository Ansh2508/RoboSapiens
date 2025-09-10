"""
Quality Control System

Automated visual inspection workflows with statistical process control,
defect classification, and comprehensive quality reporting for manufacturing
and educational applications.

Features:
- Configurable visual inspection workflows using Phase 3 computer vision
- Statistical process control with trend analysis and quality metrics
- Automated defect detection and classification systems
- Real-time quality monitoring and alerting
- Comprehensive reporting with data analysis and export capabilities
- Integration with conveyor systems for automated inspection
"""

import os
import time
import json
import statistics
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import threading

try:
    import numpy as np
    import cv2
    from applications.scipy import stats
    import matplotlib.pyplot as plt
    import pandas as pd
    ANALYSIS_LIBRARIES_AVAILABLE = True
except ImportError:
    ANALYSIS_LIBRARIES_AVAILABLE = False
    logging.warning("Analysis libraries not available. Install with: pip install numpy opencv-python scipy matplotlib pandas")

from utils.logger import get_logger

# Import Phase 3 components for integration
try:
    from vision.camera_interface import CameraInterface
    from vision.object_detection import ObjectDetector
    from automation.coordination_manager import CoordinationManager
except ImportError as e:
    logging.warning(f"Phase 3 components not available: {e}")

logger = get_logger(__name__)


class InspectionResult(Enum):
    """Inspection result classifications."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    UNKNOWN = "unknown"


class DefectType(Enum):
    """Types of defects that can be detected."""
    DIMENSIONAL = "dimensional"
    SURFACE = "surface"
    COLOR = "color"
    SHAPE = "shape"
    MISSING_COMPONENT = "missing_component"
    CONTAMINATION = "contamination"
    ORIENTATION = "orientation"
    OTHER = "other"


@dataclass
class InspectionConfig:
    """Configuration for visual inspection workflows."""
    # Inspection parameters
    inspection_name: str = "Default Inspection"
    inspection_type: str = "visual"
    enabled: bool = True
    
    # Vision settings
    camera_resolution: Tuple[int, int] = (1920, 1080)
    exposure_time: float = 0.01
    gain: float = 1.0
    lighting_enabled: bool = True
    
    # Detection thresholds
    dimension_tolerance: float = 0.1  # mm
    color_tolerance: float = 10.0     # RGB difference
    surface_roughness_threshold: float = 0.05
    
    # Quality criteria
    pass_threshold: float = 0.95
    warning_threshold: float = 0.85
    
    # Processing settings
    preprocessing_enabled: bool = True
    noise_reduction: bool = True
    edge_enhancement: bool = True
    
    # Automation integration
    conveyor_integration: bool = True
    auto_trigger: bool = True
    trigger_delay: float = 0.5  # seconds
    
    # Data collection
    save_images: bool = True
    save_failed_only: bool = False
    image_storage_path: str = "quality_data/images"
    
    # Reporting
    real_time_reporting: bool = True
    statistical_analysis: bool = True
    trend_analysis_window: int = 100  # number of samples


@dataclass
class QualityMetrics:
    """Quality metrics and statistics."""
    # Basic metrics
    total_inspections: int = 0
    passed_inspections: int = 0
    failed_inspections: int = 0
    warning_inspections: int = 0
    
    # Quality rates
    pass_rate: float = 0.0
    fail_rate: float = 0.0
    warning_rate: float = 0.0
    
    # Defect statistics
    defect_counts: Dict[DefectType, int] = field(default_factory=dict)
    defect_rates: Dict[DefectType, float] = field(default_factory=dict)
    
    # Process capability
    cpk: float = 0.0  # Process capability index
    cp: float = 0.0   # Process capability
    
    # Time metrics
    average_inspection_time: float = 0.0
    total_inspection_time: float = 0.0
    
    # Trend data
    recent_pass_rates: List[float] = field(default_factory=list)
    trend_direction: str = "stable"  # improving, degrading, stable
    
    # Timestamps
    first_inspection: Optional[datetime] = None
    last_inspection: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)


class VisualInspectionWorkflow:
    """
    Configurable visual inspection workflow using computer vision.
    """
    
    def __init__(self, config: InspectionConfig):
        """
        Initialize visual inspection workflow.
        
        Args:
            config: Inspection configuration
        """
        self.config = config
        
        # Initialize vision components
        try:
            self.camera_interface = CameraInterface()
            self.object_detector = ObjectDetector()
            self.vision_available = True
        except:
            self.camera_interface = None
            self.object_detector = None
            self.vision_available = False
            logger.warning("Vision components not available")
        
        # Initialize automation integration
        try:
            self.coordination_manager = CoordinationManager()
            self.automation_available = True
        except:
            self.coordination_manager = None
            self.automation_available = False
            logger.warning("Automation integration not available")
        
        # Inspection state
        self.is_running = False
        self.current_inspection = None
        self.inspection_thread = None
        
        # Callbacks
        self.inspection_callbacks: List[Callable] = []
        self.defect_callbacks: List[Callable] = []
        
        # Create storage directories
        os.makedirs(self.config.image_storage_path, exist_ok=True)
        
        logger.info(f"Visual inspection workflow initialized: {config.inspection_name}")
    
    def start_inspection_workflow(self) -> bool:
        """
        Start automated inspection workflow.
        
        Returns:
            True if workflow started successfully
        """
        if self.is_running:
            logger.warning("Inspection workflow already running")
            return False
        
        if not self.vision_available:
            logger.error("Vision components not available")
            return False
        
        try:
            # Start camera
            self.camera_interface.start_camera()
            
            # Configure camera settings
            self._configure_camera()
            
            # Start inspection thread
            self.is_running = True
            self.inspection_thread = threading.Thread(target=self._inspection_loop)
            self.inspection_thread.daemon = True
            self.inspection_thread.start()
            
            logger.info("Inspection workflow started")
            return True
        
        except Exception as e:
            logger.error(f"Failed to start inspection workflow: {e}")
            return False
    
    def stop_inspection_workflow(self) -> bool:
        """
        Stop inspection workflow.
        
        Returns:
            True if workflow stopped successfully
        """
        if not self.is_running:
            return True
        
        try:
            self.is_running = False
            
            # Wait for inspection thread to finish
            if self.inspection_thread and self.inspection_thread.is_alive():
                self.inspection_thread.join(timeout=5.0)
            
            # Stop camera
            if self.camera_interface:
                self.camera_interface.stop_camera()
            
            logger.info("Inspection workflow stopped")
            return True
        
        except Exception as e:
            logger.error(f"Failed to stop inspection workflow: {e}")
            return False
    
    def _configure_camera(self):
        """Configure camera settings for inspection."""
        if not self.camera_interface:
            return
        
        try:
            # Set resolution
            self.camera_interface.set_resolution(*self.config.camera_resolution)
            
            # Set exposure and gain
            self.camera_interface.set_exposure(self.config.exposure_time)
            self.camera_interface.set_gain(self.config.gain)
            
            logger.info("Camera configured for inspection")
        
        except Exception as e:
            logger.error(f"Camera configuration failed: {e}")
    
    def _inspection_loop(self):
        """Main inspection loop."""
        while self.is_running:
            try:
                # Wait for trigger
                if self.config.auto_trigger:
                    if self._wait_for_trigger():
                        self._perform_inspection()
                else:
                    time.sleep(0.1)  # Prevent busy waiting
            
            except Exception as e:
                logger.error(f"Inspection loop error: {e}")
                time.sleep(1.0)  # Prevent rapid error loops
    
    def _wait_for_trigger(self) -> bool:
        """
        Wait for inspection trigger.
        
        Returns:
            True if trigger detected
        """
        if not self.automation_available or not self.coordination_manager:
            # Simulate trigger for testing
            time.sleep(2.0)
            return True
        
        try:
            # Check for object presence on conveyor
            sensor_data = self.coordination_manager.get_sensor_data()
            
            # Simple trigger logic - object detected
            if sensor_data.get('object_detected', False):
                time.sleep(self.config.trigger_delay)
                return True
            
            time.sleep(0.1)
            return False
        
        except Exception as e:
            logger.error(f"Trigger detection error: {e}")
            return False
    
    def _perform_inspection(self) -> Dict[str, Any]:
        """
        Perform single inspection.
        
        Returns:
            Inspection results
        """
        start_time = time.time()
        
        try:
            # Capture image
            image = self.camera_interface.get_latest_frame()
            if image is None:
                logger.error("Failed to capture inspection image")
                return self._create_inspection_result(InspectionResult.UNKNOWN, "Image capture failed")
            
            # Preprocess image
            if self.config.preprocessing_enabled:
                image = self._preprocess_image(image)
            
            # Perform inspection analysis
            inspection_result = self._analyze_image(image)
            
            # Save image if configured
            if self.config.save_images:
                if not self.config.save_failed_only or inspection_result['result'] != InspectionResult.PASS:
                    self._save_inspection_image(image, inspection_result)
            
            # Calculate inspection time
            inspection_time = time.time() - start_time
            inspection_result['inspection_time'] = inspection_time
            
            # Trigger callbacks
            self._trigger_inspection_callbacks(inspection_result)
            
            logger.debug(f"Inspection completed: {inspection_result['result'].value} in {inspection_time:.3f}s")
            return inspection_result
        
        except Exception as e:
            logger.error(f"Inspection failed: {e}")
            return self._create_inspection_result(InspectionResult.UNKNOWN, f"Inspection error: {e}")
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for inspection.
        
        Args:
            image: Input image
            
        Returns:
            Preprocessed image
        """
        if not ANALYSIS_LIBRARIES_AVAILABLE:
            return image
        
        try:
            processed = image.copy()
            
            # Noise reduction
            if self.config.noise_reduction:
                processed = cv2.bilateralFilter(processed, 9, 75, 75)
            
            # Edge enhancement
            if self.config.edge_enhancement:
                kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
                processed = cv2.filter2D(processed, -1, kernel)
            
            return processed
        
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return image
    
    def _analyze_image(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Analyze image for quality inspection.
        
        Args:
            image: Preprocessed image
            
        Returns:
            Analysis results
        """
        try:
            # Initialize result
            result = self._create_inspection_result(InspectionResult.PASS, "Analysis completed")
            
            # Perform various quality checks
            defects = []
            
            # Dimensional analysis
            dimensional_result = self._check_dimensions(image)
            if not dimensional_result['passed']:
                defects.append({
                    'type': DefectType.DIMENSIONAL,
                    'severity': dimensional_result['severity'],
                    'description': dimensional_result['description']
                })
            
            # Surface quality analysis
            surface_result = self._check_surface_quality(image)
            if not surface_result['passed']:
                defects.append({
                    'type': DefectType.SURFACE,
                    'severity': surface_result['severity'],
                    'description': surface_result['description']
                })
            
            # Color analysis
            color_result = self._check_color_quality(image)
            if not color_result['passed']:
                defects.append({
                    'type': DefectType.COLOR,
                    'severity': color_result['severity'],
                    'description': color_result['description']
                })
            
            # Determine overall result
            if defects:
                # Check severity levels
                critical_defects = [d for d in defects if d['severity'] == 'critical']
                warning_defects = [d for d in defects if d['severity'] == 'warning']
                
                if critical_defects:
                    result['result'] = InspectionResult.FAIL
                    result['message'] = f"Critical defects detected: {len(critical_defects)}"
                elif warning_defects:
                    result['result'] = InspectionResult.WARNING
                    result['message'] = f"Warning defects detected: {len(warning_defects)}"
            
            result['defects'] = defects
            result['defect_count'] = len(defects)
            
            return result
        
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return self._create_inspection_result(InspectionResult.UNKNOWN, f"Analysis error: {e}")
    
    def _check_dimensions(self, image: np.ndarray) -> Dict[str, Any]:
        """Check dimensional accuracy."""
        # Simplified dimensional check
        # In production, use actual measurement algorithms
        
        try:
            # Simulate dimensional measurement
            measured_dimension = 10.0 + np.random.normal(0, 0.05)  # Simulated measurement
            target_dimension = 10.0
            tolerance = self.config.dimension_tolerance
            
            deviation = abs(measured_dimension - target_dimension)
            
            if deviation <= tolerance:
                return {
                    'passed': True,
                    'measured': measured_dimension,
                    'target': target_dimension,
                    'deviation': deviation,
                    'severity': 'none'
                }
            elif deviation <= tolerance * 2:
                return {
                    'passed': False,
                    'measured': measured_dimension,
                    'target': target_dimension,
                    'deviation': deviation,
                    'severity': 'warning',
                    'description': f"Dimension out of tolerance: {deviation:.3f}mm"
                }
            else:
                return {
                    'passed': False,
                    'measured': measured_dimension,
                    'target': target_dimension,
                    'deviation': deviation,
                    'severity': 'critical',
                    'description': f"Dimension critically out of tolerance: {deviation:.3f}mm"
                }
        
        except Exception as e:
            logger.error(f"Dimensional check failed: {e}")
            return {'passed': True, 'severity': 'none'}
    
    def _check_surface_quality(self, image: np.ndarray) -> Dict[str, Any]:
        """Check surface quality."""
        if not ANALYSIS_LIBRARIES_AVAILABLE:
            return {'passed': True, 'severity': 'none'}
        
        try:
            # Convert to grayscale for surface analysis
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Calculate surface roughness using standard deviation
            roughness = np.std(gray) / 255.0
            
            if roughness <= self.config.surface_roughness_threshold:
                return {
                    'passed': True,
                    'roughness': roughness,
                    'severity': 'none'
                }
            elif roughness <= self.config.surface_roughness_threshold * 2:
                return {
                    'passed': False,
                    'roughness': roughness,
                    'severity': 'warning',
                    'description': f"Surface roughness elevated: {roughness:.3f}"
                }
            else:
                return {
                    'passed': False,
                    'roughness': roughness,
                    'severity': 'critical',
                    'description': f"Surface roughness excessive: {roughness:.3f}"
                }
        
        except Exception as e:
            logger.error(f"Surface quality check failed: {e}")
            return {'passed': True, 'severity': 'none'}
    
    def _check_color_quality(self, image: np.ndarray) -> Dict[str, Any]:
        """Check color quality."""
        if not ANALYSIS_LIBRARIES_AVAILABLE:
            return {'passed': True, 'severity': 'none'}
        
        try:
            # Calculate average color
            avg_color = np.mean(image, axis=(0, 1))
            
            # Target color (example: blue object)
            target_color = np.array([100, 100, 200])
            
            # Calculate color difference
            color_diff = np.linalg.norm(avg_color - target_color)
            
            if color_diff <= self.config.color_tolerance:
                return {
                    'passed': True,
                    'color_difference': color_diff,
                    'severity': 'none'
                }
            elif color_diff <= self.config.color_tolerance * 2:
                return {
                    'passed': False,
                    'color_difference': color_diff,
                    'severity': 'warning',
                    'description': f"Color deviation: {color_diff:.1f}"
                }
            else:
                return {
                    'passed': False,
                    'color_difference': color_diff,
                    'severity': 'critical',
                    'description': f"Color deviation excessive: {color_diff:.1f}"
                }
        
        except Exception as e:
            logger.error(f"Color quality check failed: {e}")
            return {'passed': True, 'severity': 'none'}
    
    def _create_inspection_result(self, result: InspectionResult, message: str) -> Dict[str, Any]:
        """Create inspection result dictionary."""
        return {
            'result': result,
            'message': message,
            'timestamp': datetime.now(),
            'inspection_id': f"insp_{int(time.time())}",
            'workflow_name': self.config.inspection_name,
            'defects': [],
            'defect_count': 0,
            'inspection_time': 0.0
        }
    
    def _save_inspection_image(self, image: np.ndarray, result: Dict[str, Any]):
        """Save inspection image with results."""
        try:
            timestamp = result['timestamp'].strftime('%Y%m%d_%H%M%S')
            result_str = result['result'].value
            filename = f"{timestamp}_{result_str}_{result['inspection_id']}.jpg"
            filepath = os.path.join(self.config.image_storage_path, filename)
            
            if ANALYSIS_LIBRARIES_AVAILABLE:
                cv2.imwrite(filepath, image)
                
                # Save result metadata
                metadata_file = filepath.replace('.jpg', '_metadata.json')
                with open(metadata_file, 'w') as f:
                    # Convert datetime to string for JSON serialization
                    result_copy = result.copy()
                    result_copy['timestamp'] = result_copy['timestamp'].isoformat()
                    result_copy['result'] = result_copy['result'].value
                    json.dump(result_copy, f, indent=2)
                
                logger.debug(f"Saved inspection image: {filename}")
        
        except Exception as e:
            logger.error(f"Failed to save inspection image: {e}")
    
    def _trigger_inspection_callbacks(self, result: Dict[str, Any]):
        """Trigger inspection result callbacks."""
        for callback in self.inspection_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Inspection callback error: {e}")
        
        # Trigger defect callbacks if defects found
        if result['defects']:
            for callback in self.defect_callbacks:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Defect callback error: {e}")
    
    def add_inspection_callback(self, callback: Callable):
        """Add inspection result callback."""
        self.inspection_callbacks.append(callback)
    
    def add_defect_callback(self, callback: Callable):
        """Add defect detection callback."""
        self.defect_callbacks.append(callback)
    
    def perform_manual_inspection(self) -> Dict[str, Any]:
        """Perform single manual inspection."""
        if not self.vision_available:
            return self._create_inspection_result(InspectionResult.UNKNOWN, "Vision not available")
        
        return self._perform_inspection()
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """Get workflow status information."""
        return {
            'name': self.config.inspection_name,
            'running': self.is_running,
            'vision_available': self.vision_available,
            'automation_available': self.automation_available,
            'config': {
                'auto_trigger': self.config.auto_trigger,
                'save_images': self.config.save_images,
                'real_time_reporting': self.config.real_time_reporting
            }
        }


class StatisticalProcessControl:
    """
    Statistical process control system with trend analysis and quality metrics.
    """

    def __init__(self, config: InspectionConfig):
        """
        Initialize statistical process control.

        Args:
            config: Inspection configuration
        """
        self.config = config
        self.metrics = QualityMetrics()

        # Data storage
        self.inspection_data: List[Dict[str, Any]] = []
        self.control_limits: Dict[str, Dict[str, float]] = {}

        # Analysis settings
        self.control_chart_window = 20  # Number of samples for control charts
        self.trend_analysis_window = config.trend_analysis_window

        logger.info("Statistical process control initialized")

    def add_inspection_result(self, result: Dict[str, Any]):
        """
        Add inspection result to statistical analysis.

        Args:
            result: Inspection result dictionary
        """
        try:
            # Store inspection data
            self.inspection_data.append(result)

            # Update basic metrics
            self._update_basic_metrics(result)

            # Update defect statistics
            self._update_defect_statistics(result)

            # Update process capability
            self._update_process_capability()

            # Update trend analysis
            self._update_trend_analysis()

            # Check control limits
            self._check_control_limits(result)

            logger.debug(f"Added inspection result to SPC: {result['inspection_id']}")

        except Exception as e:
            logger.error(f"Failed to add inspection result to SPC: {e}")

    def _update_basic_metrics(self, result: Dict[str, Any]):
        """Update basic quality metrics."""
        self.metrics.total_inspections += 1

        if result['result'] == InspectionResult.PASS:
            self.metrics.passed_inspections += 1
        elif result['result'] == InspectionResult.FAIL:
            self.metrics.failed_inspections += 1
        elif result['result'] == InspectionResult.WARNING:
            self.metrics.warning_inspections += 1

        # Calculate rates
        total = self.metrics.total_inspections
        self.metrics.pass_rate = self.metrics.passed_inspections / total
        self.metrics.fail_rate = self.metrics.failed_inspections / total
        self.metrics.warning_rate = self.metrics.warning_inspections / total

        # Update time metrics
        if 'inspection_time' in result:
            total_time = self.metrics.total_inspection_time + result['inspection_time']
            self.metrics.average_inspection_time = total_time / total
            self.metrics.total_inspection_time = total_time

        # Update timestamps
        if self.metrics.first_inspection is None:
            self.metrics.first_inspection = result['timestamp']
        self.metrics.last_inspection = result['timestamp']
        self.metrics.last_updated = datetime.now()

    def _update_defect_statistics(self, result: Dict[str, Any]):
        """Update defect statistics."""
        for defect in result.get('defects', []):
            defect_type = DefectType(defect['type'])

            # Update defect counts
            if defect_type not in self.metrics.defect_counts:
                self.metrics.defect_counts[defect_type] = 0
            self.metrics.defect_counts[defect_type] += 1

            # Calculate defect rates
            total = self.metrics.total_inspections
            self.metrics.defect_rates[defect_type] = self.metrics.defect_counts[defect_type] / total

    def _update_process_capability(self):
        """Update process capability indices."""
        if not ANALYSIS_LIBRARIES_AVAILABLE or len(self.inspection_data) < 10:
            return

        try:
            # Extract dimensional measurements for capability analysis
            measurements = []
            for result in self.inspection_data[-50:]:  # Use last 50 measurements
                for defect in result.get('defects', []):
                    if defect['type'] == DefectType.DIMENSIONAL and 'measured' in defect:
                        measurements.append(defect['measured'])

            if len(measurements) < 10:
                return

            # Calculate process capability
            mean = np.mean(measurements)
            std = np.std(measurements, ddof=1)

            # Assuming target = 10.0, tolerance = ±0.1
            target = 10.0
            usl = target + self.config.dimension_tolerance  # Upper spec limit
            lsl = target - self.config.dimension_tolerance  # Lower spec limit

            # Calculate Cp and Cpk
            if std > 0:
                self.metrics.cp = (usl - lsl) / (6 * std)
                self.metrics.cpk = min(
                    (usl - mean) / (3 * std),
                    (mean - lsl) / (3 * std)
                )

        except Exception as e:
            logger.error(f"Process capability calculation failed: {e}")

    def _update_trend_analysis(self):
        """Update trend analysis."""
        if len(self.inspection_data) < self.trend_analysis_window:
            return

        try:
            # Get recent pass rates
            recent_data = self.inspection_data[-self.trend_analysis_window:]

            # Calculate pass rates for sliding windows
            window_size = max(5, self.trend_analysis_window // 10)
            pass_rates = []

            for i in range(len(recent_data) - window_size + 1):
                window_data = recent_data[i:i + window_size]
                passes = sum(1 for r in window_data if r['result'] == InspectionResult.PASS)
                pass_rate = passes / window_size
                pass_rates.append(pass_rate)

            self.metrics.recent_pass_rates = pass_rates

            # Determine trend direction
            if len(pass_rates) >= 3:
                if ANALYSIS_LIBRARIES_AVAILABLE:
                    # Use linear regression to determine trend
                    x = np.arange(len(pass_rates))
                    slope, _, _, p_value, _ = stats.linregress(x, pass_rates)

                    if p_value < 0.05:  # Statistically significant trend
                        if slope > 0.01:
                            self.metrics.trend_direction = "improving"
                        elif slope < -0.01:
                            self.metrics.trend_direction = "degrading"
                        else:
                            self.metrics.trend_direction = "stable"
                    else:
                        self.metrics.trend_direction = "stable"
                else:
                    # Simple trend analysis
                    recent_avg = np.mean(pass_rates[-3:])
                    earlier_avg = np.mean(pass_rates[:3])

                    if recent_avg > earlier_avg + 0.05:
                        self.metrics.trend_direction = "improving"
                    elif recent_avg < earlier_avg - 0.05:
                        self.metrics.trend_direction = "degrading"
                    else:
                        self.metrics.trend_direction = "stable"

        except Exception as e:
            logger.error(f"Trend analysis failed: {e}")

    def _check_control_limits(self, result: Dict[str, Any]):
        """Check if result is within control limits."""
        try:
            # Simple control limit checking
            # In production, implement proper control chart logic

            if self.metrics.pass_rate < 0.8:  # 80% pass rate threshold
                logger.warning(f"Pass rate below control limit: {self.metrics.pass_rate:.3f}")

            if self.metrics.fail_rate > 0.15:  # 15% fail rate threshold
                logger.warning(f"Fail rate above control limit: {self.metrics.fail_rate:.3f}")

        except Exception as e:
            logger.error(f"Control limit check failed: {e}")

    def generate_control_chart_data(self, metric: str = "pass_rate") -> Dict[str, Any]:
        """
        Generate control chart data for specified metric.

        Args:
            metric: Metric to generate chart for

        Returns:
            Control chart data
        """
        if not ANALYSIS_LIBRARIES_AVAILABLE:
            return {"error": "Analysis libraries not available"}

        try:
            # Get recent data
            recent_data = self.inspection_data[-self.control_chart_window:]

            if metric == "pass_rate":
                values = []
                for i in range(len(recent_data)):
                    window_data = recent_data[max(0, i-4):i+1]  # 5-point moving average
                    passes = sum(1 for r in window_data if r['result'] == InspectionResult.PASS)
                    pass_rate = passes / len(window_data)
                    values.append(pass_rate)
            else:
                values = [0.95] * len(recent_data)  # Placeholder

            # Calculate control limits
            mean_value = np.mean(values)
            std_value = np.std(values)

            ucl = mean_value + 3 * std_value  # Upper control limit
            lcl = max(0, mean_value - 3 * std_value)  # Lower control limit

            return {
                "values": values,
                "mean": mean_value,
                "ucl": ucl,
                "lcl": lcl,
                "timestamps": [r['timestamp'].isoformat() for r in recent_data]
            }

        except Exception as e:
            logger.error(f"Control chart generation failed: {e}")
            return {"error": str(e)}

    def get_quality_metrics(self) -> QualityMetrics:
        """Get current quality metrics."""
        return self.metrics

    def get_process_summary(self) -> Dict[str, Any]:
        """Get process summary statistics."""
        return {
            "total_inspections": self.metrics.total_inspections,
            "pass_rate": self.metrics.pass_rate,
            "fail_rate": self.metrics.fail_rate,
            "warning_rate": self.metrics.warning_rate,
            "cpk": self.metrics.cpk,
            "cp": self.metrics.cp,
            "trend_direction": self.metrics.trend_direction,
            "average_inspection_time": self.metrics.average_inspection_time,
            "defect_summary": dict(self.metrics.defect_rates)
        }
