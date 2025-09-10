#!/usr/bin/env python3
"""
Unified GUI Launcher

Launch the modern, Apple-inspired robotics control interface with
seamless voice and visual control integration.
"""

import os
import sys
import logging

# Add src directory to Python path for direct execution
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

def check_dependencies():
    """Check if all required dependencies are available."""
    missing_deps = []
    
    # Check PyQt5
    try:
        import PyQt5
        print("✓ PyQt5 available")
    except ImportError:
        missing_deps.append("PyQt5")
        print("❌ PyQt5 not available")
    
    # Check voice libraries (optional)
    try:
        import speech_recognition
        import pyttsx3
        print("✓ Voice libraries available")
    except ImportError:
        print("⚠️  Voice libraries not available (optional)")
    
    # Check other dependencies
    try:
        import numpy
        print("✓ NumPy available")
    except ImportError:
        print("⚠️  NumPy not available (optional)")
    
    return missing_deps

def install_missing_dependencies(missing_deps):
    """Suggest installation commands for missing dependencies."""
    if not missing_deps:
        return
    
    print("\n" + "="*60)
    print("MISSING DEPENDENCIES")
    print("="*60)
    
    for dep in missing_deps:
        if dep == "PyQt5":
            print("❌ PyQt5 is required for the GUI interface")
            print("   Install with: pip install PyQt5 PyOpenGL")
    
    print("\nOptional dependencies for full functionality:")
    print("   Voice control: pip install SpeechRecognition pyttsx3 pyaudio")
    print("   Vision processing: pip install numpy opencv-python")
    print("="*60)

def main():
    """Main launcher function."""
    print("🚀 NIRYO LLM ROBOTICS PLATFORM - UNIFIED GUI LAUNCHER")
    print("=" * 70)
    print("Apple-inspired robotics control interface")
    print("Features: Voice Control + Visual Controls + Real-time Monitoring")
    print("=" * 70)
    
    # Check dependencies
    print("\nChecking dependencies...")
    missing_deps = check_dependencies()
    
    if missing_deps:
        install_missing_dependencies(missing_deps)
        print("\nPlease install missing dependencies and try again.")
        return 1
    
    print("\n✅ All required dependencies available!")
    print("\nStarting unified GUI application...")
    
    try:
        # Import and run the application
        from interfaces.unified_gui import UnifiedGUIApplication
        
        app = UnifiedGUIApplication()
        return app.run()
        
    except ImportError as e:
        print(f"\n❌ Failed to import application: {e}")
        print("Make sure all dependencies are installed correctly.")
        return 1
    except Exception as e:
        print(f"\n❌ Application error: {e}")
        logging.error(f"Application error: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
