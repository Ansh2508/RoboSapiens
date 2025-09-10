"""
Responsive Layout Manager

Handles dynamic sizing, responsive breakpoints, and adaptive layouts
for the unified GUI application following Apple design principles.
"""

import sys
import os
from typing import Tuple, Dict, Any, Optional
from PyQt5.QtWidgets import QWidget, QApplication, QSizePolicy
from PyQt5.QtCore import QSize, QRect, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QResizeEvent

# Add src directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from interfaces.unified_gui.themes.apple_theme import AppleTheme, ResponsiveBreakpoints


class ResponsiveLayoutManager(QObject):
    """Manages responsive layouts and dynamic sizing for the unified GUI."""
    
    # Signals for responsive changes
    breakpoint_changed = pyqtSignal(str)  # mobile, tablet, desktop, large, xl
    size_changed = pyqtSignal(int, int)   # width, height
    
    def __init__(self, theme: AppleTheme):
        super().__init__()
        self.theme = theme
        self.breakpoints = theme.breakpoints
        self.current_breakpoint = "desktop"
        self.current_size = QSize(1400, 900)
        
        # Responsive configuration
        self.min_window_size = QSize(320, 480)  # Minimum usable size
        self.preferred_ratios = {
            "mobile": (9, 16),    # Portrait mobile
            "tablet": (4, 3),     # Tablet landscape
            "desktop": (16, 10),  # Desktop widescreen
            "large": (21, 9),     # Ultrawide
        }
        
        # Layout constraints
        self.panel_constraints = {
            "mobile": {"min_width": 280, "max_width": 400},
            "tablet": {"min_width": 320, "max_width": 480},
            "desktop": {"min_width": 350, "max_width": 600},
            "large": {"min_width": 400, "max_width": 800},
        }
    
    def get_breakpoint_for_width(self, width: int) -> str:
        """Determine the current breakpoint based on width."""
        if width < self.breakpoints.mobile:
            return "mobile"
        elif width < self.breakpoints.tablet:
            return "mobile"
        elif width < self.breakpoints.desktop:
            return "tablet"
        elif width < self.breakpoints.large:
            return "desktop"
        elif width < self.breakpoints.xl:
            return "large"
        else:
            return "xl"
    
    def update_size(self, size: QSize):
        """Update the current size and breakpoint."""
        old_breakpoint = self.current_breakpoint
        self.current_size = size
        self.current_breakpoint = self.get_breakpoint_for_width(size.width())
        
        # Update theme with new screen width
        self.theme.set_screen_width(size.width())
        
        # Emit signals if changed
        if old_breakpoint != self.current_breakpoint:
            self.breakpoint_changed.emit(self.current_breakpoint)
        
        self.size_changed.emit(size.width(), size.height())
    
    def get_panel_width(self, panel_type: str = "default") -> int:
        """Get optimal panel width for current breakpoint."""
        constraints = self.panel_constraints.get(self.current_breakpoint, 
                                                self.panel_constraints["desktop"])
        
        # Calculate based on screen width percentage
        if self.current_breakpoint == "mobile":
            # Mobile: panels take full width or stack vertically
            return min(self.current_size.width() - 40, constraints["max_width"])
        elif self.current_breakpoint == "tablet":
            # Tablet: panels take 1/2 or 1/3 of width
            return min(self.current_size.width() // 2 - 20, constraints["max_width"])
        else:
            # Desktop+: panels take 1/3 of width with constraints
            panel_width = self.current_size.width() // 3 - 20
            return max(constraints["min_width"], 
                      min(panel_width, constraints["max_width"]))
    
    def get_layout_mode(self) -> str:
        """Get the current layout mode based on screen size."""
        if self.current_breakpoint in ["mobile"]:
            return "stack"  # Vertical stacking
        elif self.current_breakpoint in ["tablet"]:
            return "adaptive"  # Adaptive 2-column or stack
        else:
            return "three_column"  # Traditional 3-column layout
    
    def should_hide_panel(self, panel_name: str) -> bool:
        """Determine if a panel should be hidden on small screens."""
        if self.current_breakpoint == "mobile":
            # On mobile, hide secondary panels by default
            return panel_name in ["voice_control", "vision_secondary"]
        return False
    
    def get_font_scale(self) -> float:
        """Get font scaling factor for current screen size."""
        if self.current_breakpoint == "mobile":
            return 0.875  # Slightly smaller on mobile
        elif self.current_breakpoint in ["large", "xl"]:
            return 1.125  # Slightly larger on large screens
        return 1.0
    
    def get_spacing_scale(self) -> float:
        """Get spacing scaling factor for current screen size."""
        if self.current_breakpoint == "mobile":
            return 0.75   # Tighter spacing on mobile
        elif self.current_breakpoint in ["large", "xl"]:
            return 1.25   # More generous spacing on large screens
        return 1.0
    
    def get_optimal_window_size(self) -> QSize:
        """Get optimal window size for current screen."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_size = screen.availableSize()
            
            # Calculate optimal size based on screen
            if screen_size.width() < self.breakpoints.tablet:
                # Mobile: use most of screen
                return QSize(screen_size.width() - 40, screen_size.height() - 80)
            elif screen_size.width() < self.breakpoints.desktop:
                # Tablet: use 90% of screen
                return QSize(int(screen_size.width() * 0.9), 
                           int(screen_size.height() * 0.85))
            else:
                # Desktop: use golden ratio or preferred size
                width = min(1400, int(screen_size.width() * 0.8))
                height = min(900, int(screen_size.height() * 0.8))
                return QSize(width, height)
        
        # Fallback
        return QSize(1200, 800)


class ResponsiveWidget(QWidget):
    """Base widget class with responsive behavior."""
    
    def __init__(self, layout_manager: ResponsiveLayoutManager, parent=None):
        super().__init__(parent)
        self.layout_manager = layout_manager
        self.layout_manager.breakpoint_changed.connect(self.on_breakpoint_changed)
        self.layout_manager.size_changed.connect(self.on_size_changed)
        
        # Set responsive size policy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
    def on_breakpoint_changed(self, breakpoint: str):
        """Handle breakpoint changes."""
        self.update_responsive_layout()
    
    def on_size_changed(self, width: int, height: int):
        """Handle size changes."""
        self.update_responsive_sizing()
    
    def update_responsive_layout(self):
        """Update layout based on current breakpoint."""
        # Override in subclasses
        pass
    
    def update_responsive_sizing(self):
        """Update sizing based on current dimensions."""
        # Override in subclasses
        pass
    
    def resizeEvent(self, event: QResizeEvent):
        """Handle resize events."""
        super().resizeEvent(event)
        self.layout_manager.update_size(event.size())


class ResponsiveContainer(ResponsiveWidget):
    """Container widget that adapts its layout based on screen size."""
    
    def __init__(self, layout_manager: ResponsiveLayoutManager, parent=None):
        super().__init__(layout_manager, parent)
        self.setup_responsive_container()
    
    def setup_responsive_container(self):
        """Setup the responsive container."""
        # Set minimum size
        self.setMinimumSize(self.layout_manager.min_window_size)
        
        # Enable responsive behavior
        self.setAttribute(Qt.WA_Resized, True)
        
    def update_responsive_layout(self):
        """Update container layout based on breakpoint."""
        layout_mode = self.layout_manager.get_layout_mode()
        
        if layout_mode == "stack":
            self.setup_stack_layout()
        elif layout_mode == "adaptive":
            self.setup_adaptive_layout()
        else:
            self.setup_three_column_layout()
    
    def setup_stack_layout(self):
        """Setup vertical stacking layout for mobile."""
        # Implementation depends on specific container needs
        pass
    
    def setup_adaptive_layout(self):
        """Setup adaptive layout for tablet."""
        # Implementation depends on specific container needs
        pass
    
    def setup_three_column_layout(self):
        """Setup three-column layout for desktop."""
        # Implementation depends on specific container needs
        pass
