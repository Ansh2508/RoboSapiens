"""
Image Processing Pipeline

This module provides comprehensive image preprocessing and analysis capabilities
for computer vision applications in educational robotics.

Features:
- Advanced preprocessing pipeline with noise reduction and enhancement
- Real-time image analysis with configurable parameters
- Educational visualization and debugging tools
- Performance optimization for real-time processing
- Batch processing capabilities for workshop activities
- Custom filter framework for specialized applications
"""

import cv2
import numpy as np
import time
import math
from typing import List, Tuple, Optional, Dict, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from vision.camera_interface import CameraInterface, ImageFormat
from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import VisionError

logger = get_logger(__name__)


class FilterType(Enum):
    """Image filter types."""
    GAUSSIAN_BLUR = "gaussian_blur"
    MEDIAN_BLUR = "median_blur"
    BILATERAL_FILTER = "bilateral_filter"
    MORPHOLOGY_OPEN = "morphology_open"
    MORPHOLOGY_CLOSE = "morphology_close"
    EDGE_DETECTION = "edge_detection"
    HISTOGRAM_EQUALIZATION = "histogram_equalization"
    CONTRAST_ENHANCEMENT = "contrast_enhancement"
    BRIGHTNESS_ADJUSTMENT = "brightness_adjustment"
    GAMMA_CORRECTION = "gamma_correction"
    CUSTOM = "custom"


class ColorSpace(Enum):
    """Color space options."""
    BGR = "bgr"
    RGB = "rgb"
    GRAY = "gray"
    HSV = "hsv"
    LAB = "lab"
    YUV = "yuv"
    HLS = "hls"


@dataclass
class FilterParameters:
    """Parameters for image filters."""
    filter_type: FilterType
    enabled: bool = True
    
    # Blur parameters
    kernel_size: int = 5
    sigma_x: float = 1.0
    sigma_y: float = 1.0
    
    # Bilateral filter parameters
    d: int = 9
    sigma_color: float = 75.0
    sigma_space: float = 75.0
    
    # Morphology parameters
    morph_kernel_size: int = 5
    morph_iterations: int = 1
    
    # Edge detection parameters
    edge_threshold1: float = 50.0
    edge_threshold2: float = 150.0
    edge_aperture_size: int = 3
    
    # Enhancement parameters
    alpha: float = 1.0  # Contrast multiplier
    beta: float = 0.0   # Brightness offset
    gamma: float = 1.0  # Gamma correction
    
    # Custom parameters
    custom_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """Image processing result."""
    processed_image: np.ndarray
    original_image: np.ndarray
    processing_time: float
    filters_applied: List[str]
    image_stats: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class ProcessingParameters:
    """Image processing configuration."""
    # Input/Output
    input_color_space: ColorSpace = ColorSpace.BGR
    output_color_space: ColorSpace = ColorSpace.BGR
    
    # Processing pipeline
    filters: List[FilterParameters] = field(default_factory=list)
    
    # Performance
    max_processing_time: float = 0.1  # 100ms timeout
    enable_gpu_acceleration: bool = False
    
    # Quality
    preserve_aspect_ratio: bool = True
    interpolation_method: int = cv2.INTER_LINEAR
    
    # Debugging
    save_intermediate_results: bool = False
    debug_visualization: bool = False


class ImageProcessor:
    """
    Advanced image processing pipeline providing preprocessing, analysis,
    and educational visualization capabilities.
    """
    
    def __init__(self, camera_interface: Optional[CameraInterface] = None, config_manager=None):
        """
        Initialize image processor.
        
        Args:
            camera_interface: Camera interface for live processing
            config_manager: Configuration manager instance
        """
        self.camera_interface = camera_interface
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get("config", {})
        
        # Processing parameters
        self.parameters = ProcessingParameters()
        
        # Custom filters
        self._custom_filters: Dict[str, Callable] = {}
        
        # Performance monitoring
        self._performance_monitor = PerformanceMonitor()
        self._processing_history: List[Dict[str, Any]] = []
        
        # Statistics
        self._total_processed = 0
        self._processing_times = []
        self._filter_usage_stats: Dict[str, int] = {}
        
        # Initialize default filters
        self._initialize_default_filters()
        
        logger.info("Image processor initialized")
    
    @property
    def average_processing_time(self) -> float:
        """Get average processing time in milliseconds."""
        if not self._processing_times:
            return 0.0
        return sum(self._processing_times) / len(self._processing_times) * 1000
    
    @property
    def processing_throughput(self) -> float:
        """Get processing throughput in images per second."""
        if not self._processing_times:
            return 0.0
        avg_time = sum(self._processing_times) / len(self._processing_times)
        return 1.0 / avg_time if avg_time > 0 else 0.0
    
    def _initialize_default_filters(self) -> None:
        """Initialize default processing filters."""
        default_filters = [
            FilterParameters(
                filter_type=FilterType.GAUSSIAN_BLUR,
                kernel_size=5,
                sigma_x=1.0,
                enabled=False
            ),
            FilterParameters(
                filter_type=FilterType.HISTOGRAM_EQUALIZATION,
                enabled=False
            ),
            FilterParameters(
                filter_type=FilterType.CONTRAST_ENHANCEMENT,
                alpha=1.2,
                beta=10.0,
                enabled=False
            )
        ]
        
        self.parameters.filters = default_filters
    
    def set_parameters(self, parameters: ProcessingParameters) -> None:
        """
        Set processing parameters.
        
        Args:
            parameters: Processing parameters to set
        """
        self.parameters = parameters
        logger.info("Processing parameters updated")
    
    def add_filter(self, filter_params: FilterParameters) -> None:
        """
        Add filter to processing pipeline.
        
        Args:
            filter_params: Filter parameters
        """
        self.parameters.filters.append(filter_params)
        logger.info(f"Added filter: {filter_params.filter_type.value}")
    
    def remove_filter(self, filter_type: FilterType) -> bool:
        """
        Remove filter from processing pipeline.
        
        Args:
            filter_type: Type of filter to remove
            
        Returns:
            True if filter was removed
        """
        for i, filter_params in enumerate(self.parameters.filters):
            if filter_params.filter_type == filter_type:
                self.parameters.filters.pop(i)
                logger.info(f"Removed filter: {filter_type.value}")
                return True
        return False
    
    def add_custom_filter(self, name: str, filter_func: Callable[[np.ndarray, Dict[str, Any]], np.ndarray]) -> None:
        """
        Add custom filter function.
        
        Args:
            name: Name of the custom filter
            filter_func: Function that takes (image, params) and returns processed image
        """
        self._custom_filters[name] = filter_func
        logger.info(f"Added custom filter: {name}")
    def process_image(self, image: np.ndarray, 
                     custom_parameters: Optional[ProcessingParameters] = None) -> ProcessingResult:
        """
        Process image through the configured pipeline.
        
        Args:
            image: Input image
            custom_parameters: Optional custom processing parameters
            
        Returns:
            Processing result with processed image and metadata
        """
        start_time = time.time()
        
        try:
            # Validate input
            if image is None or image.size == 0:
                raise VisionError("Invalid input image")
            
            # Use custom parameters if provided
            params = custom_parameters or self.parameters
            
            # Store original image
            original_image = image.copy()
            processed_image = image.copy()
            
            # Convert input color space if needed
            if params.input_color_space != ColorSpace.BGR:
                processed_image = self._convert_color_space(processed_image, ColorSpace.BGR, params.input_color_space)
            
            # Apply filters in sequence
            filters_applied = []
            
            for filter_params in params.filters:
                if not filter_params.enabled:
                    continue
                
                try:
                    processed_image = self._apply_filter(processed_image, filter_params)
                    filters_applied.append(filter_params.filter_type.value)
                    
                    # Update filter usage statistics
                    filter_name = filter_params.filter_type.value
                    self._filter_usage_stats[filter_name] = self._filter_usage_stats.get(filter_name, 0) + 1
                    
                except Exception as e:
                    logger.warning(f"Filter {filter_params.filter_type.value} failed: {e}")
            
            # Convert output color space if needed
            if params.output_color_space != ColorSpace.BGR:
                processed_image = self._convert_color_space(processed_image, ColorSpace.BGR, params.output_color_space)
            
            # Calculate image statistics
            image_stats = self._calculate_image_stats(processed_image)
            
            # Update performance statistics
            processing_time = time.time() - start_time
            self._processing_times.append(processing_time)
            if len(self._processing_times) > 100:  # Keep last 100 measurements
                self._processing_times.pop(0)
            
            self._total_processed += 1
            
            # Create result
            result = ProcessingResult(
                processed_image=processed_image,
                original_image=original_image,
                processing_time=processing_time,
                filters_applied=filters_applied,
                image_stats=image_stats
            )
            
            # Record processing
            self._record_processing({
                'timestamp': start_time,
                'processing_time': processing_time,
                'filters_applied': filters_applied,
                'image_size': image.shape,
                'success': True
            })
            
            logger.debug(f"Processed image in {processing_time*1000:.1f}ms with {len(filters_applied)} filters")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self._processing_times.append(processing_time)
            
            error_msg = f"Image processing failed: {e}"
            logger.error(error_msg)
            raise VisionError(error_msg)
    
    def process_image_live(self, duration: float = 10.0,
                          callback: Optional[Callable[[ProcessingResult], None]] = None) -> List[ProcessingResult]:
        """
        Process images live from camera interface.
        
        Args:
            duration: Processing duration in seconds
            callback: Optional callback for each processing result
            
        Returns:
            List of processing results
        """
        if not self.camera_interface or not self.camera_interface.is_connected:
            raise VisionError("Camera interface not available or not connected")
        
        logger.info(f"Starting live image processing for {duration} seconds...")
        
        results = []
        start_time = time.time()
        
        # Start streaming if not already active
        was_streaming = self.camera_interface.is_streaming
        if not was_streaming:
            self.camera_interface.start_streaming(ImageFormat.BGR)
        
        try:
            while time.time() - start_time < duration:
                # Get latest frame
                frame, frame_info = self.camera_interface.get_latest_frame(timeout=0.1)
                
                if frame is not None:
                    # Process image
                    result = self.process_image(frame)
                    results.append(result)
                    
                    # Call callback if provided
                    if callback:
                        try:
                            callback(result)
                        except Exception as e:
                            logger.warning(f"Processing callback error: {e}")
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.01)
        
        finally:
            # Stop streaming if we started it
            if not was_streaming:
                self.camera_interface.stop_streaming()
        
        logger.info(f"Live processing completed: {len(results)} frames processed")
        return results

    def _convert_color_space(self, image: np.ndarray, from_space: ColorSpace, to_space: ColorSpace) -> np.ndarray:
        """
        Convert image between color spaces.

        Args:
            image: Input image
            from_space: Source color space
            to_space: Target color space

        Returns:
            Converted image
        """
        if from_space == to_space:
            return image

        # Define conversion mappings
        conversions = {
            (ColorSpace.BGR, ColorSpace.RGB): cv2.COLOR_BGR2RGB,
            (ColorSpace.BGR, ColorSpace.GRAY): cv2.COLOR_BGR2GRAY,
            (ColorSpace.BGR, ColorSpace.HSV): cv2.COLOR_BGR2HSV,
            (ColorSpace.BGR, ColorSpace.LAB): cv2.COLOR_BGR2LAB,
            (ColorSpace.BGR, ColorSpace.YUV): cv2.COLOR_BGR2YUV,
            (ColorSpace.BGR, ColorSpace.HLS): cv2.COLOR_BGR2HLS,
            (ColorSpace.RGB, ColorSpace.BGR): cv2.COLOR_RGB2BGR,
            (ColorSpace.RGB, ColorSpace.GRAY): cv2.COLOR_RGB2GRAY,
            (ColorSpace.RGB, ColorSpace.HSV): cv2.COLOR_RGB2HSV,
            (ColorSpace.GRAY, ColorSpace.BGR): cv2.COLOR_GRAY2BGR,
            (ColorSpace.GRAY, ColorSpace.RGB): cv2.COLOR_GRAY2RGB,
            (ColorSpace.HSV, ColorSpace.BGR): cv2.COLOR_HSV2BGR,
            (ColorSpace.HSV, ColorSpace.RGB): cv2.COLOR_HSV2RGB,
            (ColorSpace.LAB, ColorSpace.BGR): cv2.COLOR_LAB2BGR,
            (ColorSpace.YUV, ColorSpace.BGR): cv2.COLOR_YUV2BGR,
            (ColorSpace.HLS, ColorSpace.BGR): cv2.COLOR_HLS2BGR
        }

        conversion_code = conversions.get((from_space, to_space))
        if conversion_code is None:
            raise VisionError(f"Unsupported color space conversion: {from_space.value} -> {to_space.value}")

        return cv2.cvtColor(image, conversion_code)

    def _apply_filter(self, image: np.ndarray, filter_params: FilterParameters) -> np.ndarray:
        """
        Apply single filter to image.

        Args:
            image: Input image
            filter_params: Filter parameters

        Returns:
            Filtered image
        """
        filter_type = filter_params.filter_type

        if filter_type == FilterType.GAUSSIAN_BLUR:
            return cv2.GaussianBlur(
                image,
                (filter_params.kernel_size, filter_params.kernel_size),
                filter_params.sigma_x,
                sigmaY=filter_params.sigma_y
            )

        elif filter_type == FilterType.MEDIAN_BLUR:
            return cv2.medianBlur(image, filter_params.kernel_size)

        elif filter_type == FilterType.BILATERAL_FILTER:
            return cv2.bilateralFilter(
                image,
                filter_params.d,
                filter_params.sigma_color,
                filter_params.sigma_space
            )

        elif filter_type == FilterType.MORPHOLOGY_OPEN:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (filter_params.morph_kernel_size, filter_params.morph_kernel_size)
            )
            return cv2.morphologyEx(
                image, cv2.MORPH_OPEN, kernel,
                iterations=filter_params.morph_iterations
            )

        elif filter_type == FilterType.MORPHOLOGY_CLOSE:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (filter_params.morph_kernel_size, filter_params.morph_kernel_size)
            )
            return cv2.morphologyEx(
                image, cv2.MORPH_CLOSE, kernel,
                iterations=filter_params.morph_iterations
            )

        elif filter_type == FilterType.EDGE_DETECTION:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            edges = cv2.Canny(
                gray,
                filter_params.edge_threshold1,
                filter_params.edge_threshold2,
                apertureSize=filter_params.edge_aperture_size
            )

            # Convert back to original format
            if len(image.shape) == 3:
                return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            else:
                return edges

        elif filter_type == FilterType.HISTOGRAM_EQUALIZATION:
            if len(image.shape) == 3:
                # Apply to each channel
                channels = cv2.split(image)
                equalized_channels = [cv2.equalizeHist(ch) for ch in channels]
                return cv2.merge(equalized_channels)
            else:
                return cv2.equalizeHist(image)

        elif filter_type == FilterType.CONTRAST_ENHANCEMENT:
            return cv2.convertScaleAbs(image, alpha=filter_params.alpha, beta=filter_params.beta)

        elif filter_type == FilterType.BRIGHTNESS_ADJUSTMENT:
            return cv2.convertScaleAbs(image, alpha=1.0, beta=filter_params.beta)

        elif filter_type == FilterType.GAMMA_CORRECTION:
            # Build lookup table for gamma correction
            inv_gamma = 1.0 / filter_params.gamma
            table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
            return cv2.LUT(image, table)

        elif filter_type == FilterType.CUSTOM:
            # Apply custom filter if available
            custom_name = filter_params.custom_params.get('name')
            if custom_name and custom_name in self._custom_filters:
                return self._custom_filters[custom_name](image, filter_params.custom_params)
            else:
                logger.warning(f"Custom filter '{custom_name}' not found")
                return image

        else:
            logger.warning(f"Unknown filter type: {filter_type}")
            return image

    def _calculate_image_stats(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Calculate comprehensive image statistics.

        Args:
            image: Input image

        Returns:
            Dictionary with image statistics
        """
        stats = {
            'shape': image.shape,
            'dtype': str(image.dtype),
            'size_bytes': image.nbytes,
            'channels': len(image.shape) if len(image.shape) == 2 else image.shape[2]
        }

        # Calculate per-channel statistics
        if len(image.shape) == 3:
            for i, channel_name in enumerate(['blue', 'green', 'red']):
                channel = image[:, :, i]
                stats[f'{channel_name}_mean'] = float(np.mean(channel))
                stats[f'{channel_name}_std'] = float(np.std(channel))
                stats[f'{channel_name}_min'] = int(np.min(channel))
                stats[f'{channel_name}_max'] = int(np.max(channel))
        else:
            # Grayscale image
            stats['mean'] = float(np.mean(image))
            stats['std'] = float(np.std(image))
            stats['min'] = int(np.min(image))
            stats['max'] = int(np.max(image))

        # Calculate histogram
        if len(image.shape) == 3:
            # Color histogram
            hist_b = cv2.calcHist([image], [0], None, [256], [0, 256])
            hist_g = cv2.calcHist([image], [1], None, [256], [0, 256])
            hist_r = cv2.calcHist([image], [2], None, [256], [0, 256])
            stats['histogram'] = {
                'blue': hist_b.flatten().tolist(),
                'green': hist_g.flatten().tolist(),
                'red': hist_r.flatten().tolist()
            }
        else:
            # Grayscale histogram
            hist = cv2.calcHist([image], [0], None, [256], [0, 256])
            stats['histogram'] = hist.flatten().tolist()

        return stats

    def _record_processing(self, processing_data: Dict[str, Any]) -> None:
        """
        Record processing result in history.

        Args:
            processing_data: Processing data to record
        """
        self._processing_history.append(processing_data)

        # Keep only last 1000 processing records
        if len(self._processing_history) > 1000:
            self._processing_history.pop(0)

    def batch_process_images(self, image_paths: List[Union[str, Path]],
                           output_directory: Optional[Union[str, Path]] = None,
                           custom_parameters: Optional[ProcessingParameters] = None) -> List[ProcessingResult]:
        """
        Process multiple images in batch.

        Args:
            image_paths: List of image file paths
            output_directory: Optional directory to save processed images
            custom_parameters: Optional custom processing parameters

        Returns:
            List of processing results
        """
        logger.info(f"Starting batch processing of {len(image_paths)} images...")

        results = []

        for i, image_path in enumerate(image_paths):
            try:
                # Load image
                image = cv2.imread(str(image_path))
                if image is None:
                    logger.warning(f"Failed to load image: {image_path}")
                    continue

                # Process image
                result = self.process_image(image, custom_parameters)
                results.append(result)

                # Save processed image if output directory specified
                if output_directory:
                    output_dir = Path(output_directory)
                    output_dir.mkdir(parents=True, exist_ok=True)

                    input_path = Path(image_path)
                    output_path = output_dir / f"processed_{input_path.name}"

                    cv2.imwrite(str(output_path), result.processed_image)

                logger.debug(f"Processed image {i+1}/{len(image_paths)}: {image_path}")

            except Exception as e:
                logger.error(f"Failed to process image {image_path}: {e}")

        logger.info(f"Batch processing completed: {len(results)} images processed successfully")
        return results

    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive processing statistics.

        Returns:
            Dictionary with processing statistics
        """
        return {
            'total_processed': self._total_processed,
            'average_processing_time_ms': self.average_processing_time,
            'processing_throughput_fps': self.processing_throughput,
            'filter_usage_stats': self._filter_usage_stats.copy(),
            'custom_filters': list(self._custom_filters.keys()),
            'processing_history_size': len(self._processing_history),
            'parameters': {
                'input_color_space': self.parameters.input_color_space.value,
                'output_color_space': self.parameters.output_color_space.value,
                'filters_configured': len(self.parameters.filters),
                'max_processing_time': self.parameters.max_processing_time
            }
        }

    def reset_statistics(self) -> None:
        """Reset processing statistics."""
        self._total_processed = 0
        self._processing_times.clear()
        self._filter_usage_stats.clear()
        self._processing_history.clear()
        logger.info("Processing statistics reset")

    def create_comparison_view(self, original: np.ndarray, processed: np.ndarray,
                             title: str = "Image Processing Comparison") -> np.ndarray:
        """
        Create side-by-side comparison view of original and processed images.

        Args:
            original: Original image
            processed: Processed image
            title: Title for the comparison

        Returns:
            Combined comparison image
        """
        # Ensure images have same dimensions
        if original.shape != processed.shape:
            # Resize processed to match original
            processed = cv2.resize(processed, (original.shape[1], original.shape[0]))

        # Create side-by-side comparison
        comparison = np.hstack([original, processed])

        # Add title
        cv2.putText(comparison, title, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

        # Add labels
        cv2.putText(comparison, "Original", (10, original.shape[0] - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.putText(comparison, "Processed", (original.shape[1] + 10, original.shape[0] - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        return comparison

    def create_filter_preview(self, image: np.ndarray, filter_params: FilterParameters) -> np.ndarray:
        """
        Create preview of single filter effect.

        Args:
            image: Input image
            filter_params: Filter parameters to preview

        Returns:
            Filtered image preview
        """
        try:
            return self._apply_filter(image, filter_params)
        except Exception as e:
            logger.error(f"Filter preview failed: {e}")
            return image

    def create_processing_pipeline_visualization(self, image: np.ndarray) -> List[np.ndarray]:
        """
        Create visualization of entire processing pipeline showing each step.

        Args:
            image: Input image

        Returns:
            List of images showing each processing step
        """
        pipeline_images = [image.copy()]  # Start with original
        current_image = image.copy()

        for filter_params in self.parameters.filters:
            if filter_params.enabled:
                try:
                    current_image = self._apply_filter(current_image, filter_params)
                    pipeline_images.append(current_image.copy())
                except Exception as e:
                    logger.warning(f"Pipeline visualization failed at {filter_params.filter_type.value}: {e}")
                    pipeline_images.append(current_image.copy())  # Add unchanged image

        return pipeline_images

    def optimize_parameters_for_image(self, image: np.ndarray,
                                    target_metrics: Optional[Dict[str, float]] = None) -> ProcessingParameters:
        """
        Automatically optimize processing parameters for given image.

        Args:
            image: Input image to optimize for
            target_metrics: Optional target metrics to optimize towards

        Returns:
            Optimized processing parameters
        """
        logger.info("Optimizing processing parameters for image...")

        # Calculate image characteristics
        image_stats = self._calculate_image_stats(image)

        # Create optimized parameters based on image characteristics
        optimized_params = ProcessingParameters()

        # Determine if image needs noise reduction
        if image_stats.get('std', 0) > 50:  # High noise
            optimized_params.filters.append(
                FilterParameters(
                    filter_type=FilterType.BILATERAL_FILTER,
                    d=9,
                    sigma_color=75,
                    sigma_space=75,
                    enabled=True
                )
            )

        # Determine if image needs contrast enhancement
        mean_brightness = image_stats.get('mean', 128)
        if mean_brightness < 100:  # Dark image
            optimized_params.filters.append(
                FilterParameters(
                    filter_type=FilterType.CONTRAST_ENHANCEMENT,
                    alpha=1.3,
                    beta=20,
                    enabled=True
                )
            )
        elif mean_brightness > 180:  # Bright image
            optimized_params.filters.append(
                FilterParameters(
                    filter_type=FilterType.CONTRAST_ENHANCEMENT,
                    alpha=0.8,
                    beta=-10,
                    enabled=True
                )
            )

        # Add histogram equalization for low contrast images
        if image_stats.get('std', 0) < 30:  # Low contrast
            optimized_params.filters.append(
                FilterParameters(
                    filter_type=FilterType.HISTOGRAM_EQUALIZATION,
                    enabled=True
                )
            )

        logger.info(f"Generated {len(optimized_params.filters)} optimized filters")
        return optimized_params

    def export_processing_report(self, output_path: Union[str, Path]) -> None:
        """
        Export comprehensive processing report.

        Args:
            output_path: Path to save the report
        """
        report_data = {
            'timestamp': time.time(),
            'statistics': self.get_processing_statistics(),
            'parameters': {
                'input_color_space': self.parameters.input_color_space.value,
                'output_color_space': self.parameters.output_color_space.value,
                'filters': [
                    {
                        'type': f.filter_type.value,
                        'enabled': f.enabled,
                        'kernel_size': f.kernel_size,
                        'alpha': f.alpha,
                        'beta': f.beta,
                        'gamma': f.gamma
                    }
                    for f in self.parameters.filters
                ]
            },
            'processing_history': self._processing_history[-100:]  # Last 100 records
        }

        import json
        with open(output_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"Processing report exported to {output_path}")
