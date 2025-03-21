#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import io
import zlib
import shutil
import stat
import time
import hashlib
import logging
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from base64 import b64encode, b64decode

class FileManager:
    """Advanced file management with encryption and integrity verification"""
    
    def __init__(self, encryption_key: Optional[bytes] = None):
        """Initialize the file manager
        
        Args:
            encryption_key (bytes, optional): Key for file encryption
        """
        self.encryption_key = encryption_key
        if encryption_key:
            try:
                self.cipher_suite = Fernet(encryption_key)
            except ValueError as e:
                logging.error(f"Invalid encryption key: {e}")
                self.encryption_key = None
                self.cipher_suite = None
    
    @staticmethod
    def generate_key(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """Generate encryption key from password
        
        Args:
            password (str): Password to derive key from
            salt (bytes, optional): Salt for key derivation
            
        Returns:
            tuple: (key, salt) pair
        """
        if not salt:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = b64encode(kdf.derive(password.encode()))
        return key, salt
    
    def calculate_file_hash(self, file_path: str) -> Optional[str]:
        """Calculate SHA-256 hash of a file
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            str: Hexadecimal hash string or None if failed
        """
        sha256_hash = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            logging.error(f"Error calculating file hash: {e}")
            return None

    def encrypt_file(self, source_path: str, dest_path: Optional[str] = None) -> bool:
        """Encrypt a file
        
        Args:
            source_path (str): Path to the source file
            dest_path (str, optional): Path to save encrypted file
            
        Returns:
            bool: Success status
        """
        if not self.encryption_key or not self.cipher_suite:
            logging.error("Encryption key not set or invalid")
            return False
            
        if not os.path.exists(source_path):
            logging.error(f"Source file does not exist: {source_path}")
            return False
            
        if not dest_path:
            dest_path = source_path + '.encrypted'
        
        try:
            # Read and encrypt file
            with open(source_path, 'rb') as f:
                file_data = f.read()
            
            # Compress before encryption
            compressed_data = zlib.compress(file_data)
            
            # Calculate original file hash
            original_hash = hashlib.sha256(file_data).hexdigest()
            
            # Encrypt the compressed data
            encrypted_data = self.cipher_suite.encrypt(compressed_data)
            
            # Prepare metadata
            metadata = {
                'original_hash': original_hash,
                'original_size': len(file_data),
                'compressed_size': len(compressed_data),
                'encrypted_size': len(encrypted_data),
                'timestamp': datetime.now().isoformat()
            }
            
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Write encrypted file with metadata
            with open(dest_path, 'wb') as f:
                f.write(b64encode(json.dumps(metadata).encode()) + b'\n')
                f.write(encrypted_data)
            
            logging.info(f"File encrypted successfully: {dest_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error encrypting file: {e}")
            return False
    
    def decrypt_file(self, source_path: str, dest_path: Optional[str] = None) -> bool:
        """Decrypt a file
        
        Args:
            source_path (str): Path to the encrypted file
            dest_path (str, optional): Path to save decrypted file
            
        Returns:
            bool: Success status
        """
        if not self.encryption_key or not self.cipher_suite:
            logging.error("Encryption key not set or invalid")
            return False
            
        if not os.path.exists(source_path):
            logging.error(f"Encrypted file does not exist: {source_path}")
            return False
            
        if not dest_path:
            dest_path = source_path.rsplit('.encrypted', 1)[0] if source_path.endswith('.encrypted') else source_path + '.decrypted'
        
        try:
            # Read encrypted file
            with open(source_path, 'rb') as f:
                # Read metadata from first line
                metadata_line = f.readline().strip()
                metadata = json.loads(b64decode(metadata_line).decode())
                
                # Read encrypted data
                encrypted_data = f.read()
            
            # Decrypt and decompress
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            decompressed_data = zlib.decompress(decrypted_data)
            
            # Verify integrity
            current_hash = hashlib.sha256(decompressed_data).hexdigest()
            if current_hash != metadata['original_hash']:
                logging.error("File integrity check failed")
                return False
            
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Write decrypted file
            with open(dest_path, 'wb') as f:
                f.write(decompressed_data)
            
            logging.info(f"File decrypted successfully: {dest_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error decrypting file: {e}")
            return False

def list_directory(path: str) -> Dict:
    """List contents of a directory
    
    Args:
        path (str): Directory path
        
    Returns:
        dict: Dictionary containing success status and items list or error message
    """
    items = []
    
    try:
        # Normalize path
        path = os.path.normpath(path)
        
        # Check if path exists
        if not os.path.exists(path):
            return {
                'success': False,
                'message': f"Path does not exist: {path}"
            }
        
        # Check if path is a directory
        if not os.path.isdir(path):
            return {
                'success': False,
                'message': f"Path is not a directory: {path}"
            }
        
        # Get parent directory
        parent_dir = os.path.dirname(path)
        
        # Add parent directory entry if not at root
        if path != parent_dir and os.path.exists(parent_dir):
            items.append({
                'name': '..',
                'path': parent_dir,
                'type': 'directory',
                'size': 0,
                'modified': datetime.fromtimestamp(os.path.getmtime(parent_dir)).isoformat(),
                'permissions': stat.filemode(os.stat(parent_dir).st_mode)
            })
        
        # List directory contents
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            item_stat = os.stat(item_path)
            
            item_type = 'directory' if os.path.isdir(item_path) else 'file'
            item_size = item_stat.st_size if item_type == 'file' else 0
            item_modified = datetime.fromtimestamp(item_stat.st_mtime).isoformat()
            item_permissions = stat.filemode(item_stat.st_mode)
            
            items.append({
                'name': item,
                'path': item_path,
                'type': item_type,
                'size': item_size,
                'modified': item_modified,
                'permissions': item_permissions
            })
        
        return {
            'success': True,
            'items': items
        }
    
    except Exception as e:
        logging.error(f"Error listing directory: {e}")
        return {
            'success': False,
            'message': str(e)
        }

def download_file(file_path: str) -> bytes:
    """Read a file for downloading
    
    Args:
        file_path (str): Path to the file
        
    Returns:
        bytes: File data
        
    Raises:
        Exception: If file reading fails
    """
    try:
        if not os.path.exists(file_path):
            raise Exception(f"File does not exist: {file_path}")
            
        with open(file_path, 'rb') as f:
            data = f.read()
        logging.info(f"File downloaded: {file_path}")
        return data
    except Exception as e:
        logging.error(f"Error reading file: {str(e)}")
        raise

def upload_file(file_path: str, file_data: bytes) -> bool:
    """Write a file after uploading
    
    Args:
        file_path (str): Path to save the file
        file_data (bytes): File data
        
    Returns:
        bool: Success status
        
    Raises:
        Exception: If file writing fails
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        with open(file_path, 'wb') as f:
            f.write(file_data)
        logging.info(f"File uploaded: {file_path}")
        return True
    except Exception as e:
        logging.error(f"Error writing file: {str(e)}")
        raise

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    key, salt = FileManager.generate_key("testpassword")
    fm = FileManager(key)
    
    # Test encryption
    test_file = "test.txt"
    with open(test_file, 'w') as f:
        f.write("This is a test file")
    
    fm.encrypt_file(test_file)
    fm.decrypt_file(test_file + ".encrypted")
    
    # Test directory listing
    dir_list = list_directory(os.getcwd())
    if dir_list['success']:
        for item in dir_list['items']:
            print(f"{item['type']}: {item['name']} ({item['size']} bytes)")
    
    # Clean up
    if os.path.exists(test_file):
        os.remove(test_file)
    if os.path.exists(test_file + ".encrypted"):
        os.remove(test_file + ".encrypted")