"""
Command-Line Interface

This module provides a comprehensive command-line interface for the
Niryo LLM Robotics Platform, enabling basic robot control, connection testing,
and system diagnostics.

Features:
- Interactive robot control commands
- Connection testing and diagnostics
- System status monitoring
- Configuration management
- Safety controls and emergency stop
"""

import click
import time
import sys
import os
from typing import Optional, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm

# Add src directory to Python path for direct execution
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from core.robot_controller import RobotController, RobotState
    from core.safety_manager import SafetyManager
    from utils.config_manager import ConfigManager
    from utils.logger import get_logger
    from utils.error_handler import RoboticsError, ConnectionError, SafetyError
except ImportError as e:
    print(f"Warning: Could not import some components: {e}")
    # Create fallback classes
    class RobotController:
        def __init__(self, *args, **kwargs):
            pass
    class SafetyManager:
        def __init__(self, *args, **kwargs):
            pass
    class ConfigManager:
        def __init__(self, *args, **kwargs):
            pass
    def get_logger(name):
        import logging
        return logging.getLogger(name)
    class RoboticsError(Exception):
        pass
    class ConnectionError(Exception):
        pass
    class SafetyError(Exception):
        pass
    RobotState = None

logger = get_logger(__name__)
console = Console()


class CLIInterface:
    """Command-line interface for robot control and system management."""
    
    def __init__(self):
        """Initialize CLI interface."""
        self.config_manager = get_config_manager()
        self.robot_controller = RobotController(self.config_manager)
        self.safety_manager = SafetyManager(self.config_manager)
        
        # Setup logging for CLI
        setup_logging(self.config_manager.get("config", {}).dict())
        
        console.print("[bold blue]Niryo LLM Robotics Platform - CLI Interface[/bold blue]")
        console.print("Type 'help' for available commands\n")
    
    def run_interactive(self) -> None:
        """Run interactive CLI session."""
        try:
            while True:
                try:
                    command = Prompt.ask("[bold green]niryo>[/bold green]").strip().lower()
                    
                    if not command:
                        continue
                    
                    if command in ['exit', 'quit', 'q']:
                        break
                    elif command == 'help':
                        self._show_help()
                    elif command == 'status':
                        self._show_status()
                    elif command == 'connect':
                        self._connect_robot()
                    elif command == 'disconnect':
                        self._disconnect_robot()
                    elif command == 'calibrate':
                        self._calibrate_robot()
                    elif command == 'home':
                        self._move_home()
                    elif command == 'position':
                        self._show_position()
                    elif command == 'led':
                        self._control_led()
                    elif command == 'emergency':
                        self._emergency_stop()
                    elif command == 'reset':
                        self._reset_emergency()
                    elif command == 'config':
                        self._show_config()
                    elif command == 'test':
                        self._run_connection_test()
                    elif command == 'safety':
                        self._show_safety_status()
                    else:
                        console.print(f"[red]Unknown command: {command}[/red]")
                        console.print("Type 'help' for available commands")
                
                except KeyboardInterrupt:
                    console.print("\n[yellow]Use 'exit' to quit[/yellow]")
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                    logger.error(f"CLI command error: {e}")
        
        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting...[/yellow]")
        finally:
            self._cleanup()
    
    def _show_help(self) -> None:
        """Show available commands."""
        help_table = Table(title="Available Commands")
        help_table.add_column("Command", style="cyan", no_wrap=True)
        help_table.add_column("Description", style="white")
        
        commands = [
            ("connect", "Connect to the robot"),
            ("disconnect", "Disconnect from the robot"),
            ("calibrate", "Calibrate the robot"),
            ("home", "Move robot to home position"),
            ("position", "Show current robot position"),
            ("led", "Control LED ring"),
            ("status", "Show system status"),
            ("safety", "Show safety status"),
            ("emergency", "Activate emergency stop"),
            ("reset", "Reset emergency stop"),
            ("config", "Show configuration"),
            ("test", "Run connection test"),
            ("help", "Show this help message"),
            ("exit/quit/q", "Exit the program")
        ]
        
        for cmd, desc in commands:
            help_table.add_row(cmd, desc)
        
        console.print(help_table)
    
    def _show_status(self) -> None:
        """Show system status."""
        status_table = Table(title="System Status")
        status_table.add_column("Component", style="cyan")
        status_table.add_column("Status", style="white")
        status_table.add_column("Details", style="dim")
        
        # Robot status
        robot_status = self.robot_controller.status
        status_color = "green" if robot_status.state == RobotState.READY else "yellow"
        if robot_status.state == RobotState.ERROR:
            status_color = "red"
        
        status_table.add_row(
            "Robot",
            f"[{status_color}]{robot_status.state.value.title()}[/{status_color}]",
            robot_status.last_error or "No errors"
        )
        
        # Safety status
        safety_status = self.safety_manager.get_safety_status()
        safety_color = "red" if safety_status["emergency_stop_active"] else "green"
        
        status_table.add_row(
            "Safety",
            f"[{safety_color}]{'Emergency Stop' if safety_status['emergency_stop_active'] else 'Normal'}[/{safety_color}]",
            f"Monitoring: {'Active' if safety_status['monitoring_active'] else 'Inactive'}"
        )
        
        # Configuration
        config = self.config_manager.get_config()
        status_table.add_row(
            "Configuration",
            "[green]Loaded[/green]",
            f"Robot IP: {config.robot.ip}"
        )
        
        console.print(status_table)
    
    def _connect_robot(self) -> None:
        """Connect to the robot."""
        if self.robot_controller.is_connected:
            console.print("[yellow]Robot is already connected[/yellow]")
            return
        
        config = self.config_manager.get("config", {})
        ip = Prompt.ask("Robot IP address", default=config.ip)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Connecting to robot...", total=None)
            
            try:
                success = self.robot_controller.connect(ip)
                if success:
                    console.print(f"[green]Successfully connected to robot at {ip}[/green]")
                else:
                    console.print(f"[red]Failed to connect to robot at {ip}[/red]")
            except Exception as e:
                console.print(f"[red]Connection failed: {e}[/red]")
    
    def _disconnect_robot(self) -> None:
        """Disconnect from the robot."""
        if not self.robot_controller.is_connected:
            console.print("[yellow]Robot is not connected[/yellow]")
            return
        
        self.robot_controller.disconnect()
        console.print("[green]Robot disconnected[/green]")
    
    def _calibrate_robot(self) -> None:
        """Calibrate the robot."""
        if not self.robot_controller.is_connected:
            console.print("[red]Robot must be connected first[/red]")
            return
        
        if not Confirm.ask("Robot will move during calibration. Continue?"):
            return
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Calibrating robot...", total=None)
            
            try:
                success = self.robot_controller.calibrate()
                if success:
                    console.print("[green]Robot calibration completed[/green]")
                else:
                    console.print("[red]Robot calibration failed[/red]")
            except Exception as e:
                console.print(f"[red]Calibration failed: {e}[/red]")
    
    def _move_home(self) -> None:
        """Move robot to home position."""
        if not self.robot_controller.is_ready:
            console.print("[red]Robot is not ready for movement[/red]")
            return
        
        if not Confirm.ask("Move robot to home position?"):
            return
        
        try:
            success = self.robot_controller.move_to_home()
            if success:
                console.print("[green]Robot moved to home position[/green]")
            else:
                console.print("[red]Failed to move to home position[/red]")
        except Exception as e:
            console.print(f"[red]Movement failed: {e}[/red]")
    
    def _show_position(self) -> None:
        """Show current robot position."""
        if not self.robot_controller.is_connected:
            console.print("[red]Robot is not connected[/red]")
            return
        
        position = self.robot_controller.get_position()
        joints = self.robot_controller.get_joints()
        
        if position or joints:
            pos_table = Table(title="Robot Position")
            pos_table.add_column("Type", style="cyan")
            pos_table.add_column("Values", style="white")
            
            if position:
                pos_table.add_row("Cartesian", f"Position data available")
            
            if joints:
                joint_str = ", ".join([f"{j:.3f}" for j in joints])
                pos_table.add_row("Joints (rad)", joint_str)
            
            console.print(pos_table)
        else:
            console.print("[yellow]Position data not available[/yellow]")
    
    def _control_led(self) -> None:
        """Control robot LED ring."""
        if not self.robot_controller.is_connected:
            console.print("[red]Robot is not connected[/red]")
            return
        
        color_options = {
            "red": [255, 0, 0],
            "green": [0, 255, 0],
            "blue": [0, 0, 255],
            "yellow": [255, 255, 0],
            "purple": [255, 0, 255],
            "cyan": [0, 255, 255],
            "white": [255, 255, 255]
        }
        
        color_name = Prompt.ask(
            "LED color",
            choices=list(color_options.keys()),
            default="blue"
        )
        
        duration = float(Prompt.ask("Flash duration (seconds)", default="1.0"))
        iterations = int(Prompt.ask("Number of flashes", default="3"))
        
        try:
            success = self.robot_controller.led_control(
                color_options[color_name],
                duration,
                iterations
            )
            if success:
                console.print(f"[green]LED control executed: {color_name}[/green]")
            else:
                console.print("[red]LED control failed[/red]")
        except Exception as e:
            console.print(f"[red]LED control error: {e}[/red]")
    
    def _emergency_stop(self) -> None:
        """Activate emergency stop."""
        if Confirm.ask("[red]Activate EMERGENCY STOP?[/red]"):
            self.safety_manager.emergency_stop("Manual CLI activation")
            self.robot_controller.emergency_stop()
            console.print("[red bold]EMERGENCY STOP ACTIVATED[/red bold]")
    
    def _reset_emergency(self) -> None:
        """Reset emergency stop."""
        if not self.safety_manager.is_emergency_stop_active:
            console.print("[yellow]Emergency stop is not active[/yellow]")
            return
        
        if Confirm.ask("Reset emergency stop?"):
            success = self.safety_manager.reset_emergency_stop()
            if success:
                self.robot_controller.reset_emergency_stop()
                console.print("[green]Emergency stop reset[/green]")
            else:
                console.print("[red]Cannot reset emergency stop - unsafe conditions[/red]")
    
    def _show_config(self) -> None:
        """Show current configuration."""
        config = self.config_manager.get_config()
        
        config_table = Table(title="Configuration")
        config_table.add_column("Section", style="cyan")
        config_table.add_column("Setting", style="white")
        config_table.add_column("Value", style="dim")
        
        # Robot config
        config_table.add_row("Robot", "IP Address", config.robot.ip)
        config_table.add_row("Robot", "Max Velocity", f"{config.robot.max_velocity_percent}%")
        config_table.add_row("Robot", "Timeout", f"{config.robot.timeout}s")
        
        # Safety config
        config_table.add_row("Safety", "Emergency Stop", str(config.safety.emergency_stop_enabled))
        config_table.add_row("Safety", "Collision Detection", str(config.safety.collision_detection_enabled))
        config_table.add_row("Safety", "Force Limit", f"{config.safety.force_limit_newtons}N")
        
        console.print(config_table)
    
    def _run_connection_test(self) -> None:
        """Run comprehensive connection test."""
        console.print(Panel("Running Connection Test", style="blue"))
        
        config = self.config_manager.get("config", {})
        
        # Test network connectivity
        console.print("1. Testing network connectivity...")
        import subprocess
        try:
            result = subprocess.run(
                ["ping", "-n", "1", config.ip] if sys.platform == "win32" else ["ping", "-c", "1", config.ip],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                console.print("   [green]✓ Network connectivity OK[/green]")
            else:
                console.print("   [red]✗ Network connectivity failed[/red]")
                return
        except Exception as e:
            console.print(f"   [red]✗ Network test error: {e}[/red]")
            return
        
        # Test robot connection
        console.print("2. Testing robot connection...")
        try:
            with self.robot_controller.robot_connection(config.ip):
                console.print("   [green]✓ Robot connection OK[/green]")
                
                # Test basic commands
                console.print("3. Testing basic commands...")
                self.robot_controller.led_control([0, 255, 0], 0.5, 1)
                console.print("   [green]✓ LED control OK[/green]")
                
                position = self.robot_controller.get_position()
                if position:
                    console.print("   [green]✓ Position reading OK[/green]")
                else:
                    console.print("   [yellow]⚠ Position reading unavailable[/yellow]")
                
        except Exception as e:
            console.print(f"   [red]✗ Robot connection failed: {e}[/red]")
            return
        
        console.print("\n[green bold]Connection test completed successfully![/green bold]")
    
    def _show_safety_status(self) -> None:
        """Show safety system status."""
        status = self.safety_manager.get_safety_status()
        events = self.safety_manager.safety_events
        
        safety_table = Table(title="Safety Status")
        safety_table.add_column("Parameter", style="cyan")
        safety_table.add_column("Status", style="white")
        
        # Safety parameters
        safety_table.add_row(
            "Emergency Stop",
            f"[red]Active[/red]" if status["emergency_stop_active"] else "[green]Inactive[/green]"
        )
        safety_table.add_row(
            "Safety Monitoring",
            f"[green]Enabled[/green]" if status["safety_enabled"] else "[red]Disabled[/red]"
        )
        safety_table.add_row(
            "Monitoring Thread",
            f"[green]Active[/green]" if status["monitoring_active"] else "[yellow]Inactive[/yellow]"
        )
        safety_table.add_row("Recent Events", str(status["recent_events_count"]))
        safety_table.add_row("Critical Events", str(status["unresolved_critical_events"]))
        
        console.print(safety_table)
        
        # Show recent events if any
        if events:
            recent_events = [e for e in events[-5:]]  # Last 5 events
            if recent_events:
                console.print("\n[bold]Recent Safety Events:[/bold]")
                for event in recent_events:
                    timestamp = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
                    status_icon = "✓" if event.resolved else "⚠"
                    console.print(f"  {status_icon} [{timestamp}] {event.message}")
    
    def _cleanup(self) -> None:
        """Cleanup resources."""
        try:
            self.robot_controller.disconnect()
            self.safety_manager.stop_monitoring()
            console.print("[dim]Cleanup completed[/dim]")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


@click.group()
def cli():
    """Niryo LLM Robotics Platform CLI."""
    pass


@cli.command()
def interactive():
    """Start interactive CLI session."""
    interface = CLIInterface()
    interface.run_interactive()


@cli.command()
@click.option('--ip', default=None, help='Robot IP address')
def connect(ip):
    """Connect to robot."""
    interface = CLIInterface()
    try:
        success = interface.robot_controller.connect(ip)
        if success:
            click.echo(f"Connected to robot at {ip or 'default IP'}")
        else:
            click.echo("Connection failed")
    except Exception as e:
        click.echo(f"Error: {e}")


@cli.command()
def test():
    """Run connection test."""
    interface = CLIInterface()
    interface._run_connection_test()


if __name__ == "__main__":
    cli()
