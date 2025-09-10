# Niryo LLM Robotics Platform

An intelligent robotics platform combining the Niryo Ned2 robotic arm with advanced computer vision and Large Language Model (LLM) capabilities for educational and research applications.

## 🎯 Project Overview

This project integrates traditional robotics control with modern AI technologies to create an intelligent automation system. Developed for the **Bavarian-Czech Summer School 2025** (September 8-12, 2025).

### Key Features
- **Intelligent Robot Control**: Precise movement and manipulation with the Niryo Ned2
- **Computer Vision**: Advanced object detection and recognition
- **AI Integration**: LLM-powered decision making with OpenAI and Ollama
- **Automation Workflows**: Pick-and-place operations with conveyor belt coordination
- **Natural Language Interface**: Voice and text-based robot control

## Quick Start

### Prerequisites
- Python 3.9+ (3.13 recommended)
- Niryo Ned2 robot with Ethernet connection
- Windows 11, Ubuntu 24.04, or macOS 15

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd niryo-llm-robo
   ```

2. **Run automated setup**
   ```bash
   python scripts/setup_environment.py
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Test robot connection**
   ```bash
   python scripts/test_connection.py
   ```

### Manual Installation

#### Using Conda (Recommended)
```bash
conda env create -f environment.yml
conda activate niryo-llm-robo
```

#### Using Pip
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

## 🔧 Network Configuration

### Windows 11
1. Open Network Settings → Ethernet
2. Set IP to manual: `169.254.200.210`
3. Set Subnet mask: `255.255.255.0`
4. Connect Ethernet cable to robot

### Linux Ubuntu
1. Open Settings → Network → Wired
2. Click gear icon for ethernet connection
3. Go to IPv4 tab → Select "Link Local Only"
4. Apply and connect cable

### macOS
1. Connect Ethernet cable (should auto-configure)
2. Verify IP is in `169.254.x.x` range

Test connection: `ping 169.254.200.200`

## 📁 Project Structure

```
niryo-llm-robo/
├── src/                    # Source code modules
│   ├── core/              # Robot control systems
│   ├── vision/            # Computer vision
│   ├── automation/        # Pick-and-place automation
│   ├── ai/                # LLM integration
│   ├── interfaces/        # User interfaces
│   └── utils/             # Utilities and helpers
├── tests/                 # Test suites
├── config/                # Configuration files
├── data/                  # Data storage
├── scripts/               # Utility scripts
└── docs/                  # Documentation
```

## Tasks

The project includes 7 progressive workshop tasks:

1. **Basic Robot Control** - Connection, calibration, movement
2. **Computer Vision** - Image capture, object detection
3. **Pick and Place** - Manual and vision-based operations
4. **Conveyor Belt** - Automation workflows
5. **LLM Integration** - AI-powered decision making
6. **Advanced AI** - Natural language control
7. **Creative Applications** - Custom implementations

## Safety Features

- **Emergency Stop**: Hardware and software emergency protocols
- **Collision Detection**: Real-time safety monitoring
- **Workspace Boundaries**: Configurable safety zones
- **Speed Limiting**: Adjustable maximum velocities (default: 40%)


## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## Support

- **Documentation**: See `docs/` folder for comprehensive guides
- **Issues**: Report bugs and feature requests via GitHub issues
- **Workshop Support**: Contact summer school organizers

## 🔗 Related Resources

- [Niryo Documentation](https://docs.niryo.com/)
- [PyNiryo API Reference](https://niryorobotics.github.io/pyniryo/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
- [Ollama Documentation](https://github.com/ollama/ollama)

---

**Bavarian-Czech Summer School 2025** | September 8-12, 2025
