"""
Comprehensive Main Window

Modern, Apple-inspired main window with comprehensive 5-section layout:
Header Bar, Collapsible Sidebar, Main Content Area, Right Panel, and Status Bar.
"""

import os
import sys
from typing import Dict, Any, Optional
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QFrame, QLabel, QPushButton, QListWidget, QListWidgetItem, QGroupBox,
    QSizePolicy, QScrollArea, QPropertyAnimation, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QEasingCurve
from PyQt5.QtGui import QFont, QIcon, QResizeEvent, QPixmap

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from interfaces.unified_gui.themes.apple_theme import AppleTheme, ThemeMode
from interfaces.unified_gui.components.header_bar import HeaderBar
from interfaces.unified_gui.components.right_panel import RightPanel
from interfaces.unified_gui.components.status_bar import StatusBar
from interfaces.unified_gui.views.dashboard_view import DashboardView
from interfaces.unified_gui.views.manual_control_view import ManualControlView
from interfaces.unified_gui.views.vision_system_view import VisionSystemView
from utils.logger import get_logger

# Import responsive layout manager
try:
    from interfaces.unified_gui.utils.responsive_layout import ResponsiveLayoutManager, ResponsiveWidget
    RESPONSIVE_AVAILABLE = True
except ImportError:
    RESPONSIVE_AVAILABLE = False
    ResponsiveLayoutManager = None
    ResponsiveWidget = QWidget

logger = get_logger(__name__)


class ComprehensiveMainWindow(QMainWindow):
    """Comprehensive main window with 5-section layout implementation."""
    
    # Signals for inter-component communication
    voice_command_received = pyqtSignal(str, dict)
    robot_status_changed = pyqtSignal(dict)
    vision_status_changed = pyqtSignal(dict)
    breakpoint_changed = pyqtSignal(str)
    emergency_stop_triggered = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.theme = AppleTheme(ThemeMode.LIGHT)
        self.views = {}
        self.voice_controller = None
        self.current_section = "dashboard"
        self.sidebar_collapsed = False
        self.sidebar_width = 280
        self.sidebar_collapsed_width = 60
        
        # Initialize responsive layout manager
        if RESPONSIVE_AVAILABLE:
            self.layout_manager = ResponsiveLayoutManager(self.theme)
            self.layout_manager.breakpoint_changed.connect(self.on_breakpoint_changed)
            self.layout_manager.size_changed.connect(self.on_size_changed)
        else:
            self.layout_manager = None
        
        # Setup window properties
        self.setup_window_properties()
        self.init_ui()
        self.setup_layout()
        self.apply_theme()
        self.setup_connections()

        # Add initial notifications
        self.add_initial_notifications()

        logger.info("Comprehensive main window with 5-section layout initialized")
    
    def setup_window_properties(self):
        """Setup window properties and appearance."""
        self.setWindowTitle("Niryo LLM Robotics Platform - Professional Interface")
        self.setMinimumSize(1024, 768)
        self.resize(1400, 900)
        
        # Center window on screen
        screen = self.screen()
        if screen:
            screen_geometry = screen.availableGeometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)
        
        # Set window icon if available
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.png")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass  # Icon not critical
    
    def init_ui(self):
        """Initialize the comprehensive 5-section UI layout."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main vertical layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. Header Bar (60px height)
        self.header_bar = HeaderBar(self.theme)
        main_layout.addWidget(self.header_bar)
        
        # 2. Middle section with horizontal layout
        middle_layout = QHBoxLayout()
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)
        
        # 2a. Left Sidebar (280px width, collapsible)
        self.sidebar = self.create_enhanced_sidebar()
        middle_layout.addWidget(self.sidebar)
        
        # 2b. Main Content Area (expanding)
        self.main_content = self.create_main_content()
        middle_layout.addWidget(self.main_content)
        
        # 2c. Right Panel (320px width)
        self.right_panel = RightPanel(self.theme)
        middle_layout.addWidget(self.right_panel)
        
        main_layout.addLayout(middle_layout)
        
        # 3. Bottom Status Bar (30px height)
        self.status_bar_widget = StatusBar(self.theme)
        main_layout.addWidget(self.status_bar_widget)
    
    def create_enhanced_sidebar(self) -> QWidget:
        """Create enhanced sidebar with hierarchical navigation."""
        sidebar = QFrame()
        sidebar.setObjectName("enhanced-sidebar")
        sidebar.setFixedWidth(self.sidebar_width)
        sidebar.setFrameStyle(QFrame.StyledPanel)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Sidebar header with collapse button
        header_layout = QHBoxLayout()
        
        # Company branding
        branding_label = QLabel("Niryo Platform")
        branding_label.setObjectName("sidebar-branding")
        header_layout.addWidget(branding_label)
        
        header_layout.addStretch()
        
        # Collapse button
        self.collapse_btn = QPushButton("◀")
        self.collapse_btn.setObjectName("collapse-button")
        self.collapse_btn.setFixedSize(24, 24)
        self.collapse_btn.clicked.connect(self.toggle_sidebar)
        header_layout.addWidget(self.collapse_btn)
        
        layout.addLayout(header_layout)
        
        # Navigation list with hierarchical sections
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("enhanced-nav-list")
        self.setup_enhanced_navigation_items()
        layout.addWidget(self.nav_list)
        
        # Add spacer
        layout.addStretch()
        
        # System status section
        status_section = self.create_sidebar_status_section()
        layout.addWidget(status_section)
        
        return sidebar
    
    def setup_enhanced_navigation_items(self):
        """Setup enhanced hierarchical navigation items."""
        nav_items = [
            ("Dashboard", "dashboard", "System overview and status"),
            ("Manual Control", "manual_control", "Joint and Cartesian control"),
            ("Vision System", "vision_system", "Camera feed and object detection"),
            ("Pick & Place", "pick_place", "Automated pick and place operations"),
            ("Conveyor Belt", "conveyor", "Belt control and sensor monitoring"),
            ("LLM Assistant", "llm_assistant", "Chat interface and voice commands"),
            ("Analytics", "analytics", "Performance metrics and reports"),
            ("Configuration", "configuration", "System settings and calibration"),
        ]
        
        for title, section_id, description in nav_items:
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, section_id)
            item.setToolTip(description)
            self.nav_list.addItem(item)
        
        # Connect selection change
        self.nav_list.currentItemChanged.connect(self.on_navigation_changed)
    
    def create_sidebar_status_section(self) -> QWidget:
        """Create sidebar status section."""
        status_frame = QFrame()
        status_frame.setObjectName("sidebar-status")
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(8, 8, 8, 8)
        status_layout.setSpacing(4)
        
        # Connection status
        self.sidebar_connection_label = QLabel("Status: Disconnected")
        self.sidebar_connection_label.setObjectName("sidebar-status-text")
        status_layout.addWidget(self.sidebar_connection_label)
        
        # System info
        self.sidebar_system_label = QLabel("System: Ready")
        self.sidebar_system_label.setObjectName("sidebar-status-text")
        status_layout.addWidget(self.sidebar_system_label)
        
        return status_frame
    
    def create_main_content(self) -> QWidget:
        """Create main content area with stacked views."""
        content_frame = QFrame()
        content_frame.setObjectName("main-content")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Content header
        self.content_header = self.create_content_header()
        content_layout.addWidget(self.content_header)
        
        # Stacked widget for different views
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("content-stack")
        content_layout.addWidget(self.content_stack)
        
        return content_frame
    
    def create_content_header(self) -> QWidget:
        """Create content header with section title and actions."""
        header_frame = QFrame()
        header_frame.setObjectName("content-header")
        header_frame.setFixedHeight(60)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(24, 12, 24, 12)
        header_layout.setSpacing(16)
        
        # Section title
        self.section_title = QLabel("Dashboard")
        self.section_title.setObjectName("section-title")
        header_layout.addWidget(self.section_title)
        
        header_layout.addStretch()
        
        # Action buttons (context-dependent)
        self.action_buttons_layout = QHBoxLayout()
        self.action_buttons_layout.setSpacing(8)
        header_layout.addLayout(self.action_buttons_layout)
        
        return header_frame
    
    def setup_layout(self):
        """Setup the layout and load content views."""
        self.load_content_views()
        
        # Set initial section to dashboard
        self.switch_to_section(self.current_section)
        
        # Update navigation selection
        for i in range(self.nav_list.count()):
            item = self.nav_list.item(i)
            if item.data(Qt.UserRole) == self.current_section:
                self.nav_list.setCurrentItem(item)
                break
    
    def load_content_views(self):
        """Load all content views into the stack."""
        # Dashboard View (default)
        dashboard_view = DashboardView(self.theme)
        self.views['dashboard'] = dashboard_view
        self.content_stack.addWidget(dashboard_view)

        # Manual Control View
        manual_control_view = ManualControlView(self.theme)
        self.views['manual_control'] = manual_control_view
        self.content_stack.addWidget(manual_control_view)

        # Vision System View
        vision_system_view = VisionSystemView(self.theme)
        self.views['vision_system'] = vision_system_view
        self.content_stack.addWidget(vision_system_view)

        # Placeholder views for remaining sections
        placeholder_sections = [
            "pick_place", "conveyor", "llm_assistant", "analytics", "configuration"
        ]

        for section in placeholder_sections:
            placeholder = self.create_placeholder_view(section)
            self.views[section] = placeholder
            self.content_stack.addWidget(placeholder)
    
    def create_placeholder_view(self, section_name: str) -> QWidget:
        """Create placeholder view for sections not yet implemented."""
        placeholder = QFrame()
        placeholder.setObjectName("placeholder-view")
        layout = QVBoxLayout(placeholder)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)
        
        # Title
        title = QLabel(f"{section_name.replace('_', ' ').title()} View")
        title.setObjectName("placeholder-title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Description
        description = QLabel(f"The {section_name.replace('_', ' ')} interface will be implemented here.")
        description.setObjectName("placeholder-description")
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Coming soon label
        coming_soon = QLabel("Coming Soon...")
        coming_soon.setObjectName("placeholder-coming-soon")
        coming_soon.setAlignment(Qt.AlignCenter)
        layout.addWidget(coming_soon)
        
        return placeholder

    def setup_connections(self):
        """Setup signal connections between components."""
        # Header bar connections
        self.header_bar.emergency_stop_triggered.connect(self.emergency_stop_triggered.emit)
        self.header_bar.settings_requested.connect(self.handle_settings_request)
        self.header_bar.robot_model_changed.connect(self.handle_robot_model_change)

        # Right panel connections
        self.right_panel.screenshot_requested.connect(self.handle_screenshot_request)
        self.right_panel.video_recording_requested.connect(self.handle_video_recording)
        self.right_panel.position_save_requested.connect(self.handle_position_save)

        # Status bar connections
        self.status_bar_widget.connection_clicked.connect(self.handle_connection_click)
        self.status_bar_widget.camera_settings_clicked.connect(self.handle_camera_settings)

        # Dashboard view connections
        if 'dashboard' in self.views:
            self.views['dashboard'].camera_preview_clicked.connect(self.handle_camera_preview_click)
            self.views['dashboard'].status_card_clicked.connect(self.handle_status_card_click)

    def on_navigation_changed(self, current, previous):
        """Handle navigation selection change."""
        if current:
            section_id = current.data(Qt.UserRole)
            if section_id != self.current_section:
                self.switch_to_section(section_id)

    def switch_to_section(self, section_id: str):
        """Switch to a specific section."""
        self.current_section = section_id

        # Update section title
        section_titles = {
            "dashboard": "Dashboard",
            "manual_control": "Manual Control",
            "vision_system": "Vision System",
            "pick_place": "Pick & Place",
            "conveyor": "Conveyor Belt",
            "llm_assistant": "LLM Assistant",
            "analytics": "Analytics",
            "configuration": "Configuration"
        }

        self.section_title.setText(section_titles.get(section_id, "Unknown Section"))

        # Switch content stack
        if section_id in self.views:
            view_index = list(self.views.keys()).index(section_id)
            self.content_stack.setCurrentIndex(view_index)

        # Update action buttons based on section
        self.update_action_buttons(section_id)

        logger.info(f"Switched to section: {section_id}")

    def update_action_buttons(self, section_id: str):
        """Update action buttons based on current section."""
        # Clear existing buttons
        while self.action_buttons_layout.count():
            child = self.action_buttons_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add section-specific buttons
        if section_id == "dashboard":
            refresh_btn = QPushButton("Refresh")
            refresh_btn.setObjectName("action-button")
            refresh_btn.clicked.connect(self.refresh_dashboard)
            self.action_buttons_layout.addWidget(refresh_btn)

        elif section_id == "manual_control":
            home_btn = QPushButton("Home Position")
            home_btn.setObjectName("action-button")
            home_btn.clicked.connect(self.go_home_position)
            self.action_buttons_layout.addWidget(home_btn)

            stop_btn = QPushButton("Stop")
            stop_btn.setObjectName("action-button-danger")
            stop_btn.clicked.connect(self.stop_robot)
            self.action_buttons_layout.addWidget(stop_btn)

        elif section_id == "vision_system":
            camera_btn = QPushButton("Start Camera")
            camera_btn.setObjectName("action-button")
            camera_btn.clicked.connect(self.toggle_camera)
            self.action_buttons_layout.addWidget(camera_btn)

    def toggle_sidebar(self):
        """Toggle sidebar collapsed/expanded state."""
        self.sidebar_collapsed = not self.sidebar_collapsed

        # Create animation for smooth transition
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.sidebar_animation.setDuration(300)
        self.sidebar_animation.setEasingCurve(QEasingCurve.OutCubic)

        if self.sidebar_collapsed:
            self.sidebar_animation.setStartValue(self.sidebar_width)
            self.sidebar_animation.setEndValue(self.sidebar_collapsed_width)
            self.collapse_btn.setText("▶")
            # Hide text in navigation items
            for i in range(self.nav_list.count()):
                item = self.nav_list.item(i)
                item.setText("")
        else:
            self.sidebar_animation.setStartValue(self.sidebar_collapsed_width)
            self.sidebar_animation.setEndValue(self.sidebar_width)
            self.collapse_btn.setText("◀")
            # Restore text in navigation items
            nav_items = [
                "Dashboard", "Manual Control", "Vision System", "Pick & Place",
                "Conveyor Belt", "LLM Assistant", "Analytics", "Configuration"
            ]
            for i, title in enumerate(nav_items):
                if i < self.nav_list.count():
                    self.nav_list.item(i).setText(title)

        self.sidebar_animation.start()

    # Event handlers
    def handle_settings_request(self, settings_type: str):
        """Handle settings request from header bar."""
        logger.info(f"Settings requested: {settings_type}")
        # TODO: Implement settings dialogs

    def handle_robot_model_change(self, model: str):
        """Handle robot model change."""
        logger.info(f"Robot model changed to: {model}")
        # TODO: Update robot configuration

    def handle_screenshot_request(self):
        """Handle screenshot request."""
        logger.info("Screenshot requested")
        # TODO: Implement screenshot functionality

    def handle_video_recording(self, start: bool):
        """Handle video recording request."""
        action = "started" if start else "stopped"
        logger.info(f"Video recording {action}")
        # TODO: Implement video recording

    def handle_position_save(self):
        """Handle position save request."""
        logger.info("Position save requested")
        # TODO: Implement position saving

    def handle_connection_click(self):
        """Handle connection status click."""
        logger.info("Connection status clicked")
        # TODO: Show connection dialog

    def handle_camera_settings(self):
        """Handle camera settings click."""
        logger.info("Camera settings clicked")
        # TODO: Show camera settings dialog

    def handle_camera_preview_click(self):
        """Handle camera preview click."""
        logger.info("Camera preview clicked")
        self.switch_to_section("vision_system")

    def handle_status_card_click(self, card_type: str):
        """Handle status card click."""
        logger.info(f"Status card clicked: {card_type}")
        # TODO: Navigate to relevant section

    # Action button handlers
    def refresh_dashboard(self):
        """Refresh dashboard data."""
        logger.info("Dashboard refresh requested")
        if 'dashboard' in self.views:
            # TODO: Refresh dashboard data
            pass

    def go_home_position(self):
        """Move robot to home position."""
        logger.info("Home position requested")
        # TODO: Implement robot home movement

    def stop_robot(self):
        """Stop robot movement."""
        logger.info("Robot stop requested")
        # TODO: Implement robot stop

    def toggle_camera(self):
        """Toggle camera on/off."""
        logger.info("Camera toggle requested")
        # TODO: Implement camera toggle

    def add_initial_notifications(self):
        """Add initial notifications to demonstrate functionality."""
        self.right_panel.add_notification(
            "System Ready",
            "Comprehensive 5-section layout initialized successfully",
            "info"
        )
        self.right_panel.add_notification(
            "Welcome",
            "Professional robotics control interface is ready for operation",
            "info"
        )
        self.right_panel.add_notification(
            "Features Available",
            "Dashboard, Manual Control, Vision System, and more sections available",
            "info"
        )

    # Responsive design handlers
    def on_breakpoint_changed(self, breakpoint: str):
        """Handle responsive breakpoint changes."""
        logger.info(f"Breakpoint changed to: {breakpoint}")

        # Adjust layout based on breakpoint
        if breakpoint in ["mobile", "tablet"]:
            # Auto-collapse sidebar on smaller screens
            if not self.sidebar_collapsed:
                self.toggle_sidebar()

        self.breakpoint_changed.emit(breakpoint)

    def on_size_changed(self, width: int, height: int):
        """Handle window size changes."""
        # Update responsive behavior based on size
        if width < 1000 and not self.sidebar_collapsed:
            self.toggle_sidebar()
        elif width >= 1200 and self.sidebar_collapsed:
            self.toggle_sidebar()

    def resizeEvent(self, event: QResizeEvent):
        """Handle window resize events."""
        super().resizeEvent(event)

        if self.layout_manager:
            self.layout_manager.handle_resize(event.size())

    def apply_theme(self):
        """Apply comprehensive theme styling."""
        self.setStyleSheet(f"""
        QMainWindow {{
            background-color: {self.theme.colors.primary_background};
            color: {self.theme.colors.primary_text};
        }}

        QFrame#enhanced-sidebar {{
            background-color: {self.theme.colors.secondary_background};
            border-right: 1px solid {self.theme.colors.separator};
        }}

        QLabel#sidebar-branding {{
            font-weight: 700;
            font-size: 16px;
            color: {self.theme.colors.primary_text};
        }}

        QPushButton#collapse-button {{
            background-color: {self.theme.colors.hover_background};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 12px;
            font-size: 12px;
            color: {self.theme.colors.secondary_text};
        }}

        QPushButton#collapse-button:hover {{
            background-color: {self.theme.colors.accent_blue};
            color: white;
        }}

        QListWidget#enhanced-nav-list {{
            background-color: transparent;
            border: none;
            outline: none;
        }}

        QListWidget#enhanced-nav-list::item {{
            background-color: transparent;
            border: none;
            border-radius: 8px;
            padding: 12px 16px;
            margin: 2px 0px;
            color: {self.theme.colors.primary_text};
            font-size: 14px;
            font-weight: 500;
        }}

        QListWidget#enhanced-nav-list::item:selected {{
            background-color: {self.theme.colors.accent_blue};
            color: white;
        }}

        QListWidget#enhanced-nav-list::item:hover {{
            background-color: {self.theme.colors.hover_background};
        }}

        QFrame#sidebar-status {{
            background-color: {self.theme.colors.tertiary_background};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 8px;
        }}

        QLabel#sidebar-status-text {{
            font-size: 11px;
            color: {self.theme.colors.secondary_text};
        }}

        QFrame#main-content {{
            background-color: {self.theme.colors.primary_background};
        }}

        QFrame#content-header {{
            background-color: {self.theme.colors.secondary_background};
            border-bottom: 1px solid {self.theme.colors.separator};
        }}

        QLabel#section-title {{
            font-weight: 700;
            font-size: 24px;
            color: {self.theme.colors.primary_text};
        }}

        QPushButton#action-button {{
            background-color: {self.theme.colors.accent_blue};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 600;
        }}

        QPushButton#action-button:hover {{
            background-color: {self.theme.colors.accent_blue_hover};
        }}

        QPushButton#action-button-danger {{
            background-color: #FF3B30;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 600;
        }}

        QPushButton#action-button-danger:hover {{
            background-color: #D70015;
        }}

        QFrame#placeholder-view {{
            background-color: {self.theme.colors.primary_background};
        }}

        QLabel#placeholder-title {{
            font-weight: 700;
            font-size: 32px;
            color: {self.theme.colors.secondary_text};
        }}

        QLabel#placeholder-description {{
            font-size: 16px;
            color: {self.theme.colors.tertiary_text};
        }}

        QLabel#placeholder-coming-soon {{
            font-size: 14px;
            font-style: italic;
            color: {self.theme.colors.accent_blue};
        }}
        """)
