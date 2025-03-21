#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import logging

class Database:
    """Database class for handling client data storage"""
    
    def __init__(self, db_path: str):
        """Initialize the database
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path: str = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None
        self.initialize()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def initialize(self) -> None:
        """Initialize the database by creating necessary tables if they don't exist"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # Create tables with improved schema
            self.cursor.executescript('''
                CREATE TABLE IF NOT EXISTS clients (
                    id TEXT PRIMARY KEY,
                    hostname TEXT NOT NULL,
                    ip_address TEXT,
                    os TEXT,
                    username TEXT,
                    admin_rights BOOLEAN,
                    av_software TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    online BOOLEAN DEFAULT 0,
                    system_info TEXT
                );
                
                CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    command TEXT NOT NULL,
                    params TEXT,
                    status TEXT DEFAULT 'pending',
                    result TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
                );
                
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    file_path TEXT,
                    file_name TEXT NOT NULL,
                    file_size INTEGER,
                    file_type TEXT,
                    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
                );
            ''')
            
            self.conn.commit()
            self.logger.info(f"Database initialized at {self.db_path}")
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing database: {e}")
            raise

    def add_client(self, client_data: Dict[str, Any]) -> None:
        """Add or update a client in the database
        
        Args:
            client_data: Client information
        """
        try:
            current_time = datetime.now()
            system_info = json.dumps(client_data.get('system_info', {})) if isinstance(client_data.get('system_info'), dict) else client_data.get('system_info', '')
            
            self.cursor.execute('''
                INSERT OR REPLACE INTO clients (
                    id, hostname, ip_address, os, username, admin_rights,
                    av_software, first_seen, last_seen, online, system_info
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 
                    COALESCE((SELECT first_seen FROM clients WHERE id = ?), ?), 
                    ?, ?, ?)
            ''', (
                client_data.get('id'),
                client_data.get('hostname', 'unknown'),
                client_data.get('ip_address'),
                client_data.get('os'),
                client_data.get('username'),
                client_data.get('admin_rights', False),
                json.dumps(client_data.get('av_software', [])),
                client_data.get('id'),  # For COALESCE
                current_time,           # first_seen if new
                current_time,           # last_seen
                True,                   # online
                system_info
            ))
            
            self.conn.commit()
            self.logger.info(f"Added/updated client: {client_data.get('id')}")
        except sqlite3.Error as e:
            self.logger.error(f"Error adding client {client_data.get('id')}: {e}")
            self.conn.rollback()

    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get client information by ID
        
        Args:
            client_id: Client ID
            
        Returns:
            Client information or None if not found
        """
        try:
            self.cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
            client = self.cursor.fetchone()
            
            if client:
                client_dict = dict(client)
                for field in ['system_info', 'av_software']:
                    if client_dict.get(field):
                        try:
                            client_dict[field] = json.loads(client_dict[field])
                        except json.JSONDecodeError:
                            client_dict[field] = None
                return client_dict
            return None
        except sqlite3.Error as e:
            self.logger.error(f"Error getting client {client_id}: {e}")
            return None

    def get_all_clients(self) -> List[Dict[str, Any]]:
        """Get all clients
        
        Returns:
            List of client dictionaries
        """
        try:
            self.cursor.execute('SELECT * FROM clients ORDER BY last_seen DESC')
            clients = self.cursor.fetchall()
            
            result = []
            for client in clients:
                client_dict = dict(client)
                for field in ['system_info', 'av_software']:
                    if client_dict.get(field):
                        try:
                            client_dict[field] = json.loads(client_dict[field])
                        except json.JSONDecodeError:
                            client_dict[field] = None
                result.append(client_dict)
            return result
        except sqlite3.Error as e:
            self.logger.error(f"Error getting all clients: {e}")
            return []

    def update_client_status(self, client_id: str, online: bool = True) -> bool:
        """Update client online status
        
        Args:
            client_id: Client ID
            online: Online status
            
        Returns:
            bool: Success status
        """
        try:
            current_time = datetime.now()
            self.cursor.execute('''
                UPDATE clients SET online = ?, last_seen = ? WHERE id = ?
            ''', (online, current_time, client_id))
            
            if self.cursor.rowcount > 0:
                self.conn.commit()
                self.logger.debug(f"Updated status for client {client_id}: online={online}")
                return True
            return False
        except sqlite3.Error as e:
            self.logger.error(f"Error updating client {client_id} status: {e}")
            self.conn.rollback()
            return False

    def add_command(self, client_id: str, command: str, params: Optional[Dict] = None) -> Optional[int]:
        """Add a new command to the database
        
        Args:
            client_id: Client ID
            command: Command to execute
            params: Command parameters
            
        Returns:
            Command ID or None if failed
        """
        try:
            current_time = datetime.now()
            params_json = json.dumps(params) if params is not None else None
            
            self.cursor.execute('''
                INSERT INTO commands (client_id, command, params, status, timestamp)
                VALUES (?, ?, ?, 'pending', ?)
            ''', (client_id, command, params_json, current_time))
            
            self.conn.commit()
            command_id = self.cursor.lastrowid
            self.logger.info(f"Added command {command} for client {client_id} (ID: {command_id})")
            return command_id
        except sqlite3.Error as e:
            self.logger.error(f"Error adding command for client {client_id}: {e}")
            self.conn.rollback()
            return None

    def update_command_result(self, command_id: int, status: str, result: Any) -> bool:
        """Update command result
        
        Args:
            command_id: Command ID
            status: Command status (success, error, etc.)
            result: Command result
            
        Returns:
            bool: Success status
        """
        try:
            result_json = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
            
            self.cursor.execute('''
                UPDATE commands SET status = ?, result = ? WHERE id = ?
            ''', (status, result_json, command_id))
            
            if self.cursor.rowcount > 0:
                self.conn.commit()
                self.logger.info(f"Updated command {command_id} result: {status}")
                return True
            return False
        except sqlite3.Error as e:
            self.logger.error(f"Error updating command {command_id}: {e}")
            self.conn.rollback()
            return False

    def get_pending_commands(self, client_id: str) -> List[Dict[str, Any]]:
        """Get pending commands for a client
        
        Args:
            client_id: Client ID
            
        Returns:
            List of command dictionaries
        """
        try:
            self.cursor.execute('''
                SELECT * FROM commands WHERE client_id = ? AND status = 'pending'
                ORDER BY timestamp ASC
            ''', (client_id,))
            
            commands = self.cursor.fetchall()
            return self._parse_commands(commands)
        except sqlite3.Error as e:
            self.logger.error(f"Error getting pending commands for client {client_id}: {e}")
            return []

    def get_command_history(self, client_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get command history for a client
        
        Args:
            client_id: Client ID
            limit: Maximum number of commands to return
            
        Returns:
            List of command dictionaries
        """
        try:
            self.cursor.execute('''
                SELECT * FROM commands WHERE client_id = ?
                ORDER BY timestamp DESC LIMIT ?
            ''', (client_id, limit))
            
            commands = self.cursor.fetchall()
            return self._parse_commands(commands)
        except sqlite3.Error as e:
            self.logger.error(f"Error getting command history for client {client_id}: {e}")
            return []

    def _parse_commands(self, commands: List[sqlite3.Row]) -> List[Dict[str, Any]]:
        """Parse command rows into dictionaries
        
        Args:
            commands: List of command rows
            
        Returns:
            List of parsed command dictionaries
        """
        result = []
        for cmd in commands:
            cmd_dict = dict(cmd)
            for field in ['params', 'result']:
                if cmd_dict.get(field):
                    try:
                        cmd_dict[field] = json.loads(cmd_dict[field])
                    except json.JSONDecodeError:
                        cmd_dict[field] = str(cmd_dict[field])
            result.append(cmd_dict)
        return result

    def add_file(self, client_id: str, file_data: Dict[str, Any]) -> Optional[int]:
        """Add a file record to the database
        
        Args:
            client_id: Client ID
            file_data: File information
            
        Returns:
            File ID or None if failed
        """
        try:
            current_time = datetime.now()
            self.cursor.execute('''
                INSERT INTO files (client_id, file_path, file_name, file_size, file_type, upload_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                client_id,
                file_data.get('file_path', ''),
                file_data.get('file_name'),
                file_data.get('file_size', 0),
                file_data.get('file_type', ''),
                current_time
            ))
            
            self.conn.commit()
            file_id = self.cursor.lastrowid
            self.logger.info(f"Added file {file_data.get('file_name')} for client {client_id} (ID: {file_id})")
            return file_id
        except sqlite3.Error as e:
            self.logger.error(f"Error adding file for client {client_id}: {e}")
            self.conn.rollback()
            return None

    def get_files(self, client_id: str) -> List[Dict[str, Any]]:
        """Get files for a client
        
        Args:
            client_id: Client ID
            
        Returns:
            List of file dictionaries
        """
        try:
            self.cursor.execute('''
                SELECT * FROM files WHERE client_id = ?
                ORDER BY upload_time DESC
            ''', (client_id,))
            
            files = self.cursor.fetchall()
            return [dict(file) for file in files]
        except sqlite3.Error as e:
            self.logger.error(f"Error getting files for client {client_id}: {e}")
            return []

    def close(self) -> None:
        """Close the database connection"""
        try:
            if self.conn:
                self.conn.close()
                self.logger.info("Database connection closed")
                self.conn = None
                self.cursor = None
        except sqlite3.Error as e:
            self.logger.error(f"Error closing database: {e}")

    def __enter__(self) -> 'Database':
        """Context manager enter"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit"""
        self.close()

if __name__ == "__main__":
    # Example usage
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'rat.db')
    
    with Database(db_path) as db:
        # Add a client
        client_data = {
            'id': 'test-client-1',
            'hostname': 'test-host',
            'ip_address': '192.168.1.100',
            'os': 'Windows 10',
            'username': 'testuser',
            'admin_rights': True,
            'av_software': ['Windows Defender'],
            'system_info': {'cpu': 'Intel i7', 'ram': '16GB'}
        }
        db.add_client(client_data)
        
        # Get client
        client = db.get_client('test-client-1')
        print("Client:", client)
        
        # Add a command
        command_id = db.add_command('test-client-1', 'system_info', {'detail': 'full'})
        print("Command ID:", command_id)
        
        # Update command result
        db.update_command_result(command_id, 'success', {'output': 'System info collected'})
        
        # Add a file
        file_data = {
            'file_name': 'test.txt',
            'file_path': '/path/to/test.txt',
            'file_size': 1024,
            'file_type': '.txt'
        }
        file_id = db.add_file('test-client-1', file_data)
        print("File ID:", file_id)
        
        # Get all clients
        all_clients = db.get_all_clients()
        print("All clients:", len(all_clients))