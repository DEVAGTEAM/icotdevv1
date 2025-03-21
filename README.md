# IcotRat - Remote Access Tool

IcotRat is a powerful Python-based Remote Access Tool (RAT) system with a modern web-based admin panel for controlling multiple devices simultaneously. It provides secure communication between server and clients, with extensive monitoring and control capabilities.

## Features

### Admin Panel
- Real-time device monitoring and management
- Interactive command execution
- Live system statistics and resource monitoring
- File system explorer with upload/download capabilities
- Remote shell access
- Screen capture and webcam control
- Keylogger with live keystroke monitoring
- Process and service management
- Network connection monitoring
- Client builder with customization options

### Client Features
- Cross-platform compatibility (Windows, Linux, macOS)
- Secure encrypted communication
- System information gathering
- File system operations
- Screenshot capture
- Webcam access
- Keylogging
- Process management
- Network monitoring
- Persistence mechanisms
- Shell command execution

## Installation

### Server Requirements
- Python 3.8+
- Flask
- Flask-SocketIO
- SQLite3

### Client Requirements
- Python 3.8+
- Required modules listed in requirements.txt

### Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/yourusername/IcotRat.git
cd IcotRat
```

2. Install server dependencies:
```bash
pip install -r requirements.txt
```

3. Start the server:
```bash
python server/main.py
```

4. Access the admin panel:
Open your web browser and navigate to `http://localhost:5000`

### Building Clients

1. Use the client builder in the admin panel to generate customized clients
2. Distribute the generated client to target systems

## Security Notice

This tool is intended for educational purposes and authorized testing only. Misuse of this software may be illegal in your jurisdiction. Users are responsible for complying with all applicable laws and regulations.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## Disclaimer

The authors of IcotRat are not responsible for any misuse or damage caused by this program. This software is intended for educational purposes only.