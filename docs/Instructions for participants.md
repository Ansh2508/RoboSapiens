### BAVARIAN-CZECH SUMMER SCHOOL 2025 8.9.2025 - 12.9.

# Instructions for preparing your computer for the

# workshop

## Software

## Prerequisites

- Virtual environment with Python (3.9) - can be installed using conda (miniconda is
    available here: https://www.anaconda.com/download)
- Install NiryoStudio for your system^1 : https://niryo.com/resources/download-center/
    - When you launch the app for the first time, you will be prompted to register a
       Niryo account. The app will not work without registration.
- Libraries: pyniryo, pydantic, openai, ollama
- Install IDE for python – e.g Visual Studio Code, PyCharm
**Note:** If you are using conda on Windows, you must add it to the path in the environment
variable settings.

## Installation instructions for python libraries:

- Create a virtual environment for Python. (for example using conda):
    conda create -n niryo python=3.
    conda activate niryo
- Install libraries using pip:
    pip install pyniryo pydantic openai ollama
**Note:** Tested on Ubuntu 24.04 LTS, Windows 11 and Macbook M1 with MacOS version 15.

## How to connect the Niryo robot to a computer

1) The robot is connected to the computer via an Ethernet cable (RJ45 connector).
Therefore, you need to have an RJ45 port or a USB-C dongle/hub with an RJ
connector.
2) After connecting the Ethernet cable, you must configure the network:
**Linux ubuntu**
Open Settings →Network →Wired → Profile for ethernet connection connected to the
robot →click on site properties → IPv4 → Link Local Only → Apply

(^1) version for Ned2 robot


### BAVARIAN-CZECH SUMMER SCHOOL 2025 8.9.2025 - 12.9.

The computer will obtain an IP address in the format 169.254.X.X, and everything
should work.
**Windows 11**
Open network settings → Ethernet →Set IP to manual → 169.254.200.210, Mask:
255.255.255.
**MacOS**
If set to DHCP, it should obtain an IP address in the format 169.254.X.X, so it should
work immediately after connecting to the robot.
3) Test the connection:
ping 169.254.200.