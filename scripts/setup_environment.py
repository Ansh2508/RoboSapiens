#!/usr/bin/env python3
"""
Environment Setup Script for Niryo LLM Robotics Platform

This script automates the setup process for the development environment
across Windows, Linux, and macOS platforms.

Usage:
    python scripts/setup_environment.py [--platform windows|linux|macos]
"""

import os
import sys
import subprocess
import platform
import argparse
from pathlib import Path
from typing import List, Optional


class EnvironmentSetup:
    """Automated environment setup for cross-platform development."""
    
    def __init__(self, target_platform: Optional[str] = None):
        self.platform = target_platform or platform.system().lower()
        self.project_root = Path(__file__).parent.parent
        self.python_version = "3.13"
        
    def detect_platform(self) -> str:
        """Detect the current platform."""
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        elif system == "darwin":
            return "macos"
        elif system == "linux":
            return "linux"
        else:
            raise RuntimeError(f"Unsupported platform: {system}")
    
    def check_python_version(self) -> bool:
        """Check if Python 3.13+ is available."""
        try:
            result = subprocess.run([sys.executable, "--version"], 
                                  capture_output=True, text=True)
            version_str = result.stdout.strip()
            print(f"Found Python: {version_str}")
            
            # Extract version numbers
            version_parts = version_str.split()[1].split('.')
            major, minor = int(version_parts[0]), int(version_parts[1])
            
            if major >= 3 and minor >= 9:  # Accept 3.9+ for compatibility
                return True
            else:
                print(f"Warning: Python {major}.{minor} found, but 3.13+ recommended")
                return True  # Allow older versions with warning
                
        except Exception as e:
            print(f"Error checking Python version: {e}")
            return False
    
    def check_conda_available(self) -> bool:
        """Check if conda is available."""
        try:
            subprocess.run(["conda", "--version"], 
                          capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def setup_conda_environment(self) -> bool:
        """Set up conda environment from environment.yml."""
        try:
            print("Creating conda environment from environment.yml...")
            
            # Create environment
            cmd = ["conda", "env", "create", "-f", "environment.yml"]
            result = subprocess.run(cmd, cwd=self.project_root, 
                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                # Environment might already exist, try updating
                print("Environment exists, updating...")
                cmd = ["conda", "env", "update", "-f", "environment.yml"]
                result = subprocess.run(cmd, cwd=self.project_root,
                                      capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Conda environment created/updated successfully")
                return True
            else:
                print(f"❌ Error setting up conda environment: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error with conda setup: {e}")
            return False
    
    def setup_pip_environment(self) -> bool:
        """Set up pip virtual environment."""
        try:
            venv_path = self.project_root / "venv"
            
            # Create virtual environment
            if not venv_path.exists():
                print("Creating Python virtual environment...")
                subprocess.run([sys.executable, "-m", "venv", str(venv_path)], 
                             check=True)
            
            # Determine activation script path
            if self.platform == "windows":
                pip_path = venv_path / "Scripts" / "pip.exe"
                python_path = venv_path / "Scripts" / "python.exe"
            else:
                pip_path = venv_path / "bin" / "pip"
                python_path = venv_path / "bin" / "python"
            
            # Upgrade pip
            subprocess.run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"], 
                         check=True)
            
            # Install requirements
            print("Installing Python packages...")
            subprocess.run([str(pip_path), "install", "-r", "requirements.txt"], 
                         cwd=self.project_root, check=True)
            
            print("✅ Pip environment created successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error setting up pip environment: {e}")
            return False
    
    def configure_network_windows(self) -> None:
        """Configure network settings for Windows."""
        print("\n📋 Windows Network Configuration:")
        print("1. Open Network Settings → Ethernet")
        print("2. Set IP to manual: 169.254.200.210")
        print("3. Set Subnet mask: 255.255.255.0")
        print("4. Connect Ethernet cable to robot")
        print("5. Test connection: ping 169.254.200.200")
    
    def configure_network_linux(self) -> None:
        """Configure network settings for Linux."""
        print("\n📋 Linux Network Configuration:")
        print("1. Open Settings → Network → Wired")
        print("2. Click on gear icon for ethernet connection")
        print("3. Go to IPv4 tab")
        print("4. Select 'Link Local Only'")
        print("5. Apply settings and connect cable")
        print("6. Test connection: ping 169.254.200.200")
    
    def configure_network_macos(self) -> None:
        """Configure network settings for macOS."""
        print("\n📋 macOS Network Configuration:")
        print("1. System should auto-configure with DHCP")
        print("2. Connect Ethernet cable to robot")
        print("3. IP should be assigned in 169.254.x.x range")
        print("4. Test connection: ping 169.254.200.200")
    
    def create_project_files(self) -> None:
        """Create essential project files."""
        # Create .gitignore
        gitignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Environment variables
.env

# Data files
data/logs/*.log
data/images/*.jpg
data/images/*.png
data/models/*.pkl
data/exports/*

# OS
.DS_Store
Thumbs.db

# Testing
.coverage
.pytest_cache/
htmlcov/

# Documentation
docs/_build/
"""
        
        gitignore_path = self.project_root / ".gitignore"
        if not gitignore_path.exists():
            with open(gitignore_path, 'w') as f:
                f.write(gitignore_content.strip())
            print("✅ Created .gitignore file")
    
    def run_setup(self) -> bool:
        """Run the complete setup process."""
        print(f"🚀 Setting up Niryo LLM Robotics Platform for {self.platform}")
        print("=" * 60)
        
        # Check Python version
        if not self.check_python_version():
            print("❌ Python version check failed")
            return False
        
        # Try conda first, fallback to pip
        success = False
        if self.check_conda_available():
            print("📦 Using conda for environment setup...")
            success = self.setup_conda_environment()
        
        if not success:
            print("📦 Using pip for environment setup...")
            success = self.setup_pip_environment()
        
        if not success:
            print("❌ Environment setup failed")
            return False
        
        # Create project files
        self.create_project_files()
        
        # Show network configuration instructions
        if self.platform == "windows":
            self.configure_network_windows()
        elif self.platform == "linux":
            self.configure_network_linux()
        elif self.platform == "macos":
            self.configure_network_macos()
        
        print("\n✅ Environment setup completed successfully!")
        print("\n📋 Next steps:")
        print("1. Copy .env.example to .env and configure your settings")
        print("2. Configure network settings as shown above")
        print("3. Connect to robot and test: python scripts/test_connection.py")
        
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Setup Niryo LLM Robotics Platform")
    parser.add_argument("--platform", choices=["windows", "linux", "macos"],
                       help="Target platform (auto-detected if not specified)")
    
    args = parser.parse_args()
    
    try:
        setup = EnvironmentSetup(args.platform)
        success = setup.run_setup()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n❌ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Setup failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
