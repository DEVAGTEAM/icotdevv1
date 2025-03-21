#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import signal
import logging
import subprocess
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class ShellExecutor:
    """Secure shell command execution and output handling"""
    
    def __init__(self):
        """Initialize shell executor"""
        self.running_processes: Dict[int, Dict] = {}
        self.output_buffer_size: int = 8192  # 8KB buffer
        self.timeout: int = 30  # Default timeout in seconds
    
    def execute_command(self, command: str, shell: bool = False, cwd: Optional[str] = None,
                       timeout: Optional[int] = None, env: Optional[Dict] = None) -> Dict:
        """Execute shell command securely
        
        Args:
            command: Command to execute
            shell: Whether to run through shell
            cwd: Working directory
            timeout: Command timeout in seconds
            env: Environment variables
            
        Returns:
            Dict: Command execution results
        """
        try:
            start_time = time.time()
            
            # Create process
            process = subprocess.Popen(
                command,
                shell=shell,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=self.output_buffer_size
            )
            
            # Store process info
            process_info = {
                'pid': process.pid,
                'command': command,
                'start_time': datetime.now().isoformat(),
                'status': 'running',
                'process': process
            }
            self.running_processes[process.pid] = process_info
            
            try:
                # Wait for process with timeout
                stdout, stderr = process.communicate(timeout=timeout or self.timeout)
                
                # Update process info
                process_info.update({
                    'status': 'completed',
                    'exit_code': process.returncode,
                    'stdout': stdout,
                    'stderr': stderr,
                    'duration': time.time() - start_time
                })
                logging.info(f"Command completed: {command}")
                
            except subprocess.TimeoutExpired:
                # Kill process on timeout
                process.kill()
                stdout, stderr = process.communicate()
                
                process_info.update({
                    'status': 'timeout',
                    'exit_code': -1,
                    'stdout': stdout,
                    'stderr': stderr,
                    'duration': time.time() - start_time
                })
                logging.warning(f"Command timed out: {command}")
            
            return process_info
            
        except Exception as e:
            logging.error(f"Error executing command '{command}': {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'command': command
            }
        finally:
            self.cleanup_processes()
    
    def execute_command_async(self, command: str, shell: bool = False, cwd: Optional[str] = None,
                            env: Optional[Dict] = None) -> Dict:
        """Execute command asynchronously
        
        Args:
            command: Command to execute
            shell: Whether to run through shell
            cwd: Working directory
            env: Environment variables
            
        Returns:
            Dict: Process information
        """
        try:
            # Create process
            process = subprocess.Popen(
                command,
                shell=shell,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=self.output_buffer_size
            )
            
            # Store process info
            process_info = {
                'pid': process.pid,
                'command': command,
                'start_time': datetime.now().isoformat(),
                'status': 'running',
                'process': process
            }
            self.running_processes[process.pid] = process_info
            
            logging.info(f"Started async command: {command} (PID: {process.pid})")
            return process_info
            
        except Exception as e:
            logging.error(f"Error starting async command '{command}': {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'command': command
            }
    
    def get_process_output(self, pid: int) -> Dict:
        """Get output from running process
        
        Args:
            pid: Process ID
            
        Returns:
            Dict: Process output and status
        """
        try:
            process_info = self.running_processes.get(pid)
            if not process_info:
                logging.error(f"Process {pid} not found in running processes")
                return {'error': f'Process {pid} not found'}
            
            if process_info['status'] != 'running':
                return process_info
            
            process = process_info['process']
            
            # Check if process has completed
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                process_info.update({
                    'status': 'completed',
                    'exit_code': process.returncode,
                    'stdout': stdout,
                    'stderr': stderr,
                    'duration': time.time() - datetime.fromisoformat(process_info['start_time']).timestamp()
                })
                logging.info(f"Process {pid} completed")
            else:
                # Process still running, return current status
                process_info['stdout'] = process.stdout.read() if process.stdout else ''
                process_info['stderr'] = process.stderr.read() if process.stderr else ''
            
            return process_info
            
        except Exception as e:
            logging.error(f"Error getting process output for PID {pid}: {str(e)}")
            return {'error': str(e)}
    
    def terminate_process(self, pid: int) -> bool:
        """Terminate a running process
        
        Args:
            pid: Process ID
            
        Returns:
            bool: True if process was terminated
        """
        try:
            process_info = self.running_processes.get(pid)
            if not process_info:
                logging.error(f"Process {pid} not found")
                return False
            
            if process_info['status'] != 'running':
                logging.info(f"Process {pid} already terminated or completed")
                return True
            
            process = process_info['process']
            process.terminate()
            
            try:
                process.wait(timeout=5)  # Wait for process to terminate
            except subprocess.TimeoutExpired:
                process.kill()  # Force kill if terminate fails
                logging.warning(f"Force killed process {pid} after terminate timeout")
            
            stdout, stderr = process.communicate()
            process_info.update({
                'status': 'terminated',
                'exit_code': process.returncode,
                'stdout': stdout,
                'stderr': stderr,
                'duration': time.time() - datetime.fromisoformat(process_info['start_time']).timestamp()
            })
            
            logging.info(f"Process {pid} terminated successfully")
            return True
            
        except Exception as e:
            logging.error(f"Error terminating process {pid}: {str(e)}")
            return False
        finally:
            self.cleanup_processes()
    
    def cleanup_processes(self) -> None:
        """Cleanup terminated processes"""
        try:
            for pid in list(self.running_processes.keys()):
                process_info = self.running_processes[pid]
                if process_info['status'] != 'running':
                    del self.running_processes[pid]
                    logging.debug(f"Cleaned up process {pid}")
        except Exception as e:
            logging.error(f"Error cleaning up processes: {str(e)}")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    executor = ShellExecutor()
    
    # Synchronous command
    result = executor.execute_command("dir" if os.name == 'nt' else "ls -l", shell=True)
    print("Sync command result:")
    print(f"Status: {result['status']}")
    print(f"Output: {result.get('stdout', '')}")
    print(f"Error: {result.get('stderr', '')}")
    
    # Asynchronous command
    async_result = executor.execute_command_async("ping 127.0.0.1 -n 10" if os.name == 'nt' else "ping 127.0.0.1 -c 10", shell=True)
    if async_result['status'] == 'running':
        pid = async_result['pid']
        print(f"Started async command with PID: {pid}")
        
        # Check output after a delay
        time.sleep(2)
        output = executor.get_process_output(pid)
        print("Async command partial output:")
        print(f"Status: {output['status']}")
        print(f"Partial output: {output.get('stdout', '')}")
        
        # Terminate process
        if executor.terminate_process(pid):
            print("Process terminated")
            final_output = executor.get_process_output(pid)
            print(f"Final status: {final_output['status']}")
            print(f"Final output: {final_output.get('stdout', '')}")