#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import logging
from .database import Database  # Assuming Database is in the same package

class ClientHandler:
    """Handler for managing client connections and commands"""
    
    def __init__(self, db: Database, logger: logging.Logger):
        """Initialize the client handler
        
        Args:
            db: Database instance
            logger: Logger instance
        """
        self.db: Database = db
        self.logger: logging.Logger = logger
        self.heartbeat_timeout: int = 60  # seconds
        self.cleanup_interval: int = 300  # seconds
        self.last_cleanup: float = time.time()
    
    def register_client(self, client_data: Dict[str, Any]) -> Optional[str]:
        """Register a new client or update existing client
        
        Args:
            client_data: Client information
            
        Returns:
            Client ID or None if registration fails
        """
        try:
            if 'id' not in client_data or not client_data['id']:
                client_data['id'] = str(uuid.uuid4())
            
            self.db.add_client(client_data)
            self.logger.info(f"Client registered: {client_data['id']} ({client_data.get('hostname', 'Unknown')})")
            return client_data['id']
        except Exception as e:
            self.logger.error(f"Error registering client: {e}")
            return None
    
    def heartbeat(self, client_id: str) -> bool:
        """Update client heartbeat
        
        Args:
            client_id: Client ID
            
        Returns:
            Success status
        """
        try:
            client = self.db.get_client(client_id)
            if not client:
                self.logger.warning(f"Heartbeat received from unknown client: {client_id}")
                return False
            
            success = self.db.update_client_status(client_id, online=True)
            if not success:
                self.logger.warning(f"Failed to update heartbeat for client: {client_id}")
                return False
            
            # Periodic cleanup
            current_time = time.time()
            if current_time - self.last_cleanup > self.cleanup_interval:
                self.cleanup_offline_clients()
                self.last_cleanup = current_time
            
            self.logger.debug(f"Heartbeat processed for client: {client_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error processing heartbeat for client {client_id}: {e}")
            return False
    
    def cleanup_offline_clients(self) -> None:
        """Mark clients as offline if they haven't sent a heartbeat recently"""
        try:
            clients = self.db.get_all_clients()
            current_time = datetime.now()
            
            for client in clients:
                if not client['online']:
                    continue
                    
                last_seen = client['last_seen']
                if isinstance(last_seen, str):
                    try:
                        last_seen = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                    except ValueError:
                        self.logger.warning(f"Invalid last_seen format for client {client['id']}: {last_seen}")
                        continue
                
                if (current_time - last_seen).total_seconds() > self.heartbeat_timeout:
                    self.db.update_client_status(client['id'], online=False)
                    self.logger.info(f"Client marked offline: {client['id']} ({client.get('hostname', 'Unknown')})")
        except Exception as e:
            self.logger.error(f"Error during client cleanup: {e}")
    
    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get client information
        
        Args:
            client_id: Client ID
            
        Returns:
            Client information or None if not found
        """
        try:
            client = self.db.get_client(client_id)
            if not client:
                self.logger.debug(f"Client not found: {client_id}")
            return client
        except Exception as e:
            self.logger.error(f"Error getting client {client_id}: {e}")
            return None
    
    def get_all_clients(self) -> List[Dict[str, Any]]:
        """Get all clients
        
        Returns:
            List of client dictionaries
        """
        try:
            clients = self.db.get_all_clients()
            return clients
        except Exception as e:
            self.logger.error(f"Error getting all clients: {e}")
            return []
    
    def add_command(self, client_id: str, command: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Add a command for a client
        
        Args:
            client_id: Client ID
            command: Command to execute
            params: Command parameters
            
        Returns:
            Command ID or None if failed
        """
        try:
            if not self.db.get_client(client_id):
                self.logger.error(f"Cannot add command for unknown client: {client_id}")
                return None
            
            command_id = self.db.add_command(client_id, command, params)
            if command_id is not None:
                self.logger.info(f"Command added for client {client_id}: {command} (ID: {command_id})")
            return command_id
        except Exception as e:
            self.logger.error(f"Error adding command for client {client_id}: {e}")
            return None
    
    def get_pending_commands(self, client_id: str) -> List[Dict[str, Any]]:
        """Get pending commands for a client
        
        Args:
            client_id: Client ID
            
        Returns:
            List of command dictionaries
        """
        try:
            commands = self.db.get_pending_commands(client_id)
            return commands
        except Exception as e:
            self.logger.error(f"Error getting pending commands for client {client_id}: {e}")
            return []
    
    def update_command_result(self, command_id: int, status: str, result: Any) -> bool:
        """Update command result
        
        Args:
            command_id: Command ID
            status: Command status (success, error, etc.)
            result: Command result
            
        Returns:
            Success status
        """
        try:
            success = self.db.update_command_result(command_id, status, result)
            if success:
                self.logger.info(f"Command {command_id} updated with status: {status}")
            else:
                self.logger.warning(f"Failed to update command {command_id}: Command not found")
            return success
        except Exception as e:
            self.logger.error(f"Error updating command {command_id}: {e}")
            return False
    
    def get_command_history(self, client_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get command history for a client
        
        Args:
            client_id: Client ID
            limit: Maximum number of commands to return
            
        Returns:
            List of command dictionaries
        """
        try:
            if limit < 1 or limit > 1000:
                self.logger.warning(f"Invalid limit value {limit} for command history, using default 50")
                limit = 50
                
            history = self.db.get_command_history(client_id, limit)
            return history
        except Exception as e:
            self.logger.error(f"Error getting command history for client {client_id}: {e}")
            return []
    
    def add_file(self, client_id: str, file_data: Dict[str, Any]) -> Optional[int]:
        """Add a file record
        
        Args:
            client_id: Client ID
            file_data: File information
            
        Returns:
            File ID or None if failed
        """
        try:
            if not self.db.get_client(client_id):
                self.logger.error(f"Cannot add file for unknown client: {client_id}")
                return None
            
            file_id = self.db.add_file(client_id, file_data)
            if file_id is not None:
                self.logger.info(f"File added for client {client_id}: {file_data.get('file_name')} (ID: {file_id})")
            return file_id
        except Exception as e:
            self.logger.error(f"Error adding file for client {client_id}: {e}")
            return None
    
    def get_files(self, client_id: str) -> List[Dict[str, Any]]:
        """Get files for a client
        
        Args:
            client_id: Client ID
            
        Returns:
            List of file dictionaries
        """
        try:
            files = self.db.get_files(client_id)
            return files
        except Exception as e:
            self.logger.error(f"Error getting files for client {client_id}: {e}")
            return []

if __name__ == "__main__":
    # Example usage
    import logging
    from database import Database  # Assuming database.py is in the same directory
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Initialize database and client handler
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'rat.db')
    db = Database(db_path)
    handler = ClientHandler(db, logger)
    
    # Register a client
    client_data = {
        'hostname': 'test-host',
        'ip_address': '192.168.1.100',
        'os': 'Windows 10',
        'username': 'testuser',
        'admin_rights': True,
        'system_info': {'cpu': 'Intel i7'}
    }
    client_id = handler.register_client(client_data)
    print(f"Registered client: {client_id}")
    
    # Process heartbeat
    handler.heartbeat(client_id)
    
    # Add a command
    command_id = handler.add_command(client_id, 'system_info', {'detail': 'full'})
    print(f"Added command: {command_id}")
    
    # Update command result
    handler.update_command_result(command_id, 'success', {'output': 'System info collected'})
    
    # Add a file
    file_data = {
        'file_name': 'test.txt',
        'file_size': 1024,
        'file_type': '.txt'
    }
    file_id = handler.add_file(client_id, file_data)
    print(f"Added file: {file_id}")
    
    # Get all clients
    clients = handler.get_all_clients()
    print(f"Total clients: {len(clients)}")
    
    # Cleanup
    db.close()