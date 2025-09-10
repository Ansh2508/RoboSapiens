"""
Unified GUI Application

Modern, Apple-inspired robotics control interface that seamlessly combines
voice commands and visual controls for intuitive robot operation.
"""

import os
import sys
import signal
from typing import Optional
from PyQt5.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QFont

# Add src directory to Python path for direct execution
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(current_dir))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from interfaces.unified_gui.core.comprehensive_main_window import ComprehensiveMainWindow
from interfaces.unified_gui.themes.apple_theme import AppleTheme, ThemeMode
from utils.logger import get_logger

logger = get_logger(__name__)


class UnifiedGUIApplication:
    """Main application class for the unified GUI."""
    
    def __init__(self):
        self.app: Optional[QApplication] = None
        self.main_window: Optional[ComprehensiveMainWindow] = None
        self.theme = AppleTheme(ThemeMode.LIGHT)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def initialize_application(self) -> bool:
        """Initialize the Qt application."""
        try:
            # Create QApplication
            self.app = QApplication(sys.argv)
            self.app.setApplicationName("Niryo LLM Robotics Platform")
            self.app.setApplicationVersion("1.0.0")
            self.app.setOrganizationName("Bavarian-Czech Summer School")
            
            # Set application icon (if available)
            try:
                icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
                if os.path.exists(icon_path):
                    self.app.setWindowIcon(QPixmap(icon_path))
            except Exception:
                pass  # Icon not critical
            
            # Set application font
            font = QFont("SF Pro Display", 10)
            if not font.exactMatch():
                font = QFont("Segoe UI", 10)  # Windows fallback
            self.app.setFont(font)
            
            # Apply global stylesheet
            self.app.setStyleSheet(self.theme.get_complete_stylesheet())
            
            logger.info("Qt application initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Qt application: {e}")
            return False
    
    def show_splash_screen(self) -> Optional[QSplashScreen]:
        """Show application splash screen."""
        try:
            # Create splash screen
            splash_pixmap = QPixmap(400, 300)
            splash_pixmap.fill(Qt.white)
            
            splash = QSplashScreen(splash_pixmap)
            splash.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
            
            # Show splash with message
            splash.show()
            splash.showMessage(
                "Niryo LLM Robotics Platform\nLoading...",
                Qt.AlignCenter | Qt.AlignBottom,
                Qt.black
            )
            
            # Process events to show splash
            self.app.processEvents()
            
            return splash
            
        except Exception as e:
            logger.warning(f"Failed to show splash screen: {e}")
            return None
    
    def initialize_main_window(self) -> bool:
        """Initialize the main application window."""
        try:
            self.main_window = ComprehensiveMainWindow()
            
            # Setup window properties
            self.main_window.setWindowTitle("Niryo LLM Robotics Platform - Unified Control Interface")
            
            # Center window on screen
            self.center_window()
            
            logger.info("Main window initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize main window: {e}")
            return False
    
    def center_window(self):
        """Center the main window on the screen."""
        if not self.main_window:
            return
        
        try:
            # Get screen geometry
            screen = self.app.primaryScreen()
            screen_geometry = screen.availableGeometry()
            
            # Calculate center position
            window_geometry = self.main_window.geometry()
            x = (screen_geometry.width() - window_geometry.width()) // 2
            y = (screen_geometry.height() - window_geometry.height()) // 2
            
            # Move window to center
            self.main_window.move(x, y)
            
        except Exception as e:
            logger.warning(f"Failed to center window: {e}")
    
    def setup_error_handling(self):
        """Setup global error handling."""
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            
            logger.error(
                "Uncaught exception",
                exc_info=(exc_type, exc_value, exc_traceback)
            )
            
            # Show error dialog
            if self.app and self.main_window:
                QMessageBox.critical(
                    self.main_window,
                    "Application Error",
                    f"An unexpected error occurred:\n\n{exc_value}\n\n"
                    "Please check the logs for more details."
                )
        
        sys.excepthook = handle_exception
    
    def run(self) -> int:
        """Run the application."""
        try:
            # Initialize application
            if not self.initialize_application():
                logger.error("Failed to initialize application")
                return 1
            
            # Setup error handling
            self.setup_error_handling()
            
            # Show splash screen
            splash = self.show_splash_screen()
            
            # Initialize main window
            if not self.initialize_main_window():
                logger.error("Failed to initialize main window")
                return 1
            
            # Hide splash and show main window
            if splash:
                splash.finish(self.main_window)
            
            self.main_window.show()
            
            # Setup timer for periodic tasks
            self.setup_periodic_tasks()
            
            logger.info("Application started successfully")
            
            # Run the application event loop
            return self.app.exec_()
            
        except Exception as e:
            logger.error(f"Application error: {e}")
            return 1
        finally:
            self.cleanup()
    
    def setup_periodic_tasks(self):
        """Setup periodic tasks and timers."""
        # Timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.periodic_update)
        self.update_timer.start(1000)  # Update every second
    
    def periodic_update(self):
        """Perform periodic updates."""
        try:
            # Update application status
            if self.main_window:
                # You can add periodic status updates here
                pass
                
        except Exception as e:
            logger.warning(f"Periodic update error: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        
        if self.app:
            self.app.quit()
    
    def cleanup(self):
        """Cleanup resources before exit."""
        try:
            logger.info("Cleaning up application resources...")
            
            # Stop voice controller if active
            if self.main_window and hasattr(self.main_window, 'voice_control_panel'):
                voice_panel = self.main_window.voice_control_panel
                if voice_panel.is_voice_active():
                    voice_panel.stop_voice_control()
            
            # Disconnect from robot if connected
            if self.main_window and hasattr(self.main_window, 'robot_control_panel'):
                robot_panel = self.main_window.robot_control_panel
                if robot_panel.is_connected:
                    robot_panel.disconnect_robot()
            
            logger.info("Application cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point for the unified GUI application."""
    print("🚀 NIRYO LLM ROBOTICS PLATFORM - UNIFIED GUI")
    print("=" * 60)
    print("Starting Apple-inspired robotics control interface...")
    print("Features: Voice Control + Visual Controls + Real-time Monitoring")
    print("=" * 60)
    
    try:
        # Create and run application
        app = UnifiedGUIApplication()
        exit_code = app.run()
        
        print(f"\nApplication exited with code: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 0
    except Exception as e:
        print(f"\nApplication failed to start: {e}")
        logger.error(f"Application startup error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
