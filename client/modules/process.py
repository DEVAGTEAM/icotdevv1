#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import psutil
import signal
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union

class ProcessManager:
    """Process and service management functionality"""
    
    def __init__(self):
        """Initialize process manager"""
        self.monitored_processes: Dict[int, Dict] = {}
    
    def get_process_list(self) -> List[Dict]:
        """Get list of running processes with details
        
        Returns:
            List[Dict]: List of process information
        """
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'username', 'status', 'cpu_percent', 'memory_percent']):
                try:
                    proc_info = proc.info
                    with proc.oneshot():
                        proc_info.update({
                            'cpu_percent': proc_info['cpu_percent'],
                            'memory_percent': proc_info['memory_percent'],
                            'create_time': datetime.fromtimestamp(proc.create_time()).isoformat(),
                            'command_line': proc.cmdline() or [],
                            'executable': proc.exe() or '',
                            'working_directory': proc.cwd() or ''
                        })
                    processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            logging.error(f"Error getting process list: {str(e)}")
        return processes
    
    def get_process_info(self, pid: int) -> Optional[Dict]:
        """Get detailed information about a specific process
        
        Args:
            pid: Process ID
            
        Returns:
            Dict: Process information or None if not found
        """
        try:
            proc = psutil.Process(pid)
            with proc.oneshot():
                info = {
                    'pid': proc.pid,
                    'name': proc.name(),
                    'status': proc.status(),
                    'username': proc.username(),
                    'cpu_percent': proc.cpu_percent(interval=0.1),
                    'memory_percent': proc.memory_percent(),
                    'create_time': datetime.fromtimestamp(proc.create_time()).isoformat(),
                    'command_line': proc.cmdline() or [],
                    'executable': proc.exe() or '',
                    'working_directory': proc.cwd() or '',
                    'open_files': [f._asdict() for f in proc.open_files()] if proc.open_files() else [],
                    'connections': [c._asdict() for c in proc.connections()] if proc.connections() else [],
                    'threads': proc.num_threads(),
                    'parent': proc.ppid(),
                    'children': [child.pid for child in proc.children()],
                    'memory_info': proc.memory_info()._asdict(),
                    'cpu_times': proc.cpu_times()._asdict(),
                    'io_counters': proc.io_counters()._asdict() if hasattr(proc, 'io_counters') and proc.io_counters() else None
                }
            return info
        except psutil.NoSuchProcess:
            logging.error(f"Process {pid} not found")
            return None
        except psutil.AccessDenied:
            logging.error(f"Access denied to process {pid}")
            return None
        except Exception as e:
            logging.error(f"Error getting process info for {pid}: {str(e)}")
            return None
    
    def kill_process(self, pid: int) -> bool:
        """Kill a process by its PID
        
        Args:
            pid: Process ID
            
        Returns:
            bool: True if process was killed successfully
        """
        try:
            proc = psutil.Process(pid)
            proc.kill()
            logging.info(f"Process {pid} killed successfully")
            return True
        except psutil.NoSuchProcess:
            logging.error(f"Process {pid} not found")
            return False
        except psutil.AccessDenied:
            logging.error(f"Access denied to kill process {pid}")
            return False
        except Exception as e:
            logging.error(f"Error killing process {pid}: {str(e)}")
            return False
    
    def suspend_process(self, pid: int) -> bool:
        """Suspend a process
        
        Args:
            pid: Process ID
            
        Returns:
            bool: True if process was suspended successfully
        """
        try:
            proc = psutil.Process(pid)
            proc.suspend()
            logging.info(f"Process {pid} suspended successfully")
            return True
        except psutil.NoSuchProcess:
            logging.error(f"Process {pid} not found")
            return False
        except psutil.AccessDenied:
            logging.error(f"Access denied to suspend process {pid}")
            return False
        except Exception as e:
            logging.error(f"Error suspending process {pid}: {str(e)}")
            return False
    
    def resume_process(self, pid: int) -> bool:
        """Resume a suspended process
        
        Args:
            pid: Process ID
            
        Returns:
            bool: True if process was resumed successfully
        """
        try:
            proc = psutil.Process(pid)
            proc.resume()
            logging.info(f"Process {pid} resumed successfully")
            return True
        except psutil.NoSuchProcess:
            logging.error(f"Process {pid} not found")
            return False
        except psutil.AccessDenied:
            logging.error(f"Access denied to resume process {pid}")
            return False
        except Exception as e:
            logging.error(f"Error resuming process {pid}: {str(e)}")
            return False
    
    def start_process(self, command: Union[str, List[str]], shell: bool = False, cwd: Optional[str] = None) -> Optional[int]:
        """Start a new process
        
        Args:
            command: Command to execute (string or list of strings)
            shell: Whether to run through shell
            cwd: Working directory
            
        Returns:
            int: Process ID if started successfully, None otherwise
        """
        try:
            import subprocess
            process = subprocess.Popen(
                command,
                shell=shell,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE
            )
            logging.info(f"Process started with PID {process.pid}: {command}")
            return process.pid
        except Exception as e:
            logging.error(f"Error starting process '{command}': {str(e)}")
            return None
    
    def get_services(self) -> List[Dict]:
        """Get list of system services
        
        Returns:
            List[Dict]: List of service information
        """
        services = []
        try:
            if os.name == 'nt':
                # Windows-specific service handling
                try:
                    import win32serviceutil
                    import win32service
                    for service in psutil.win_service_iter():
                        try:
                            service_info = service.as_dict()
                            status = win32serviceutil.QueryServiceStatus(service.name())
                            config = win32serviceutil.QueryServiceConfig(service.name())
                            service_info.update({
                                'start_type': status[1],  # SERVICE_START_TYPE
                                'binary_path': config[3] if config else 'N/A'
                            })
                            services.append(service_info)
                        except Exception as e:
                            logging.debug(f"Error processing service {service.name()}: {e}")
                            continue
                except ImportError:
                    logging.warning("pywin32 not available, limited service information on Windows")
                    for service in psutil.win_service_iter():
                        services.append(service.as_dict())
            else:
                # Unix-like systems
                if os.path.exists('/bin/systemctl'):
                    try:
                        import subprocess
                        output = subprocess.check_output(
                            ['systemctl', 'list-units', '--type=service', '--all'],
                            universal_newlines=True
                        )
                        lines = output.split('\n')[1:-7]  # Skip header and footer
                        for line in lines:
                            if line.strip():
                                parts = line.split(maxsplit=4)
                                if len(parts) >= 5:
                                    services.append({
                                        'name': parts[0].rstrip('.service'),
                                        'load': parts[1],
                                        'active': parts[2],
                                        'sub': parts[3],
                                        'description': parts[4]
                                    })
                    except subprocess.CalledProcessError as e:
                        logging.error(f"Error running systemctl: {e}")
                else:
                    logging.warning("Systemctl not available, service listing not supported")
        except Exception as e:
            logging.error(f"Error getting services: {str(e)}")
        return services

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    pm = ProcessManager()
    
    # Get process list
    processes = pm.get_process_list()
    print(f"Found {len(processes)} processes")
    
    # Get info for current process
    current_pid = os.getpid()
    info = pm.get_process_info(current_pid)
    if info:
        print(f"Current process info: {info['name']} (PID: {current_pid})")
    
    # Start a test process
    test_pid = pm.start_process("notepad.exe" if os.name == 'nt' else "sleep 10")
    if test_pid:
        print(f"Started test process with PID: {test_pid}")
        
        # Suspend and resume test
        if pm.suspend_process(test_pid):
            print(f"Suspended PID {test_pid}")
            time.sleep(2)
            if pm.resume_process(test_pid):
                print(f"Resumed PID {test_pid}")
        
        # Kill test process
        if pm.kill_process(test_pid):
            print(f"Killed PID {test_pid}")
    
    # Get services
    services = pm.get_services()
    print(f"Found {len(services)} services")