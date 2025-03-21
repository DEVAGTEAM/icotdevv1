#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import psutil
import platform
import socket
import logging
from datetime import datetime
from typing import Dict, Any, List

try:
    import cpuinfo
    CPU_INFO_AVAILABLE = True
except ImportError:
    CPU_INFO_AVAILABLE = False
    logging.warning("py-cpuinfo not available, CPU information will be limited")

class SystemInfo:
    """System information gathering and monitoring"""
    
    def __init__(self, update_interval: int = 60):
        """Initialize system information gatherer
        
        Args:
            update_interval: Time in seconds between cache updates (default: 60)
        """
        self.info_cache: Dict[str, Any] = {}
        self.update_interval: int = update_interval
        self.last_update: float = 0
    
    def get_basic_info(self) -> Dict[str, Any]:
        """Get basic system information
        
        Returns:
            Dict: Basic system information
        """
        try:
            return {
                'hostname': socket.gethostname(),
                'platform': platform.system(),
                'platform_release': platform.release(),
                'platform_version': platform.version(),
                'architecture': platform.machine(),
                'processor': platform.processor() or 'N/A',
                'username': os.getlogin(),
                'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                'system': platform.uname().system,
                'node': platform.uname().node,
                'release': platform.uname().release,
                'version': platform.uname().version,
                'machine': platform.uname().machine
            }
        except Exception as e:
            logging.error(f"Error getting basic system info: {str(e)}")
            return {}
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get detailed CPU information
        
        Returns:
            Dict: CPU information and statistics
        """
        try:
            cpu_freq = psutil.cpu_freq()
            cpu_info = {
                'physical_cores': psutil.cpu_count(logical=False),
                'total_cores': psutil.cpu_count(logical=True),
                'max_frequency': cpu_freq.max if cpu_freq else 0.0,
                'min_frequency': cpu_freq.min if cpu_freq else 0.0,
                'current_frequency': cpu_freq.current if cpu_freq else 0.0,
                'cpu_usage_per_core': psutil.cpu_percent(interval=0.1, percpu=True),
                'total_cpu_usage': psutil.cpu_percent(interval=0.1),
                'cpu_times': psutil.cpu_times()._asdict()
            }
            
            if CPU_INFO_AVAILABLE:
                try:
                    detailed_info = cpuinfo.get_cpu_info()
                    cpu_info.update({
                        'brand_raw': detailed_info.get('brand_raw', 'Unknown'),
                        'hz_advertised': detailed_info.get('hz_advertised', 'N/A'),
                        'l2_cache_size': detailed_info.get('l2_cache_size', 0),
                        'l3_cache_size': detailed_info.get('l3_cache_size', 0),
                        'vendor_id': detailed_info.get('vendor_id_raw', 'N/A'),
                        'flags': detailed_info.get('flags', [])
                    })
                except Exception as e:
                    logging.warning(f"Error getting detailed CPU info: {e}")
            
            return cpu_info
        except Exception as e:
            logging.error(f"Error getting CPU info: {str(e)}")
            return {}
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory usage information
        
        Returns:
            Dict: Memory usage statistics
        """
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            return {
                'virtual': {
                    'total': memory.total,
                    'available': memory.available,
                    'used': memory.used,
                    'free': memory.free,
                    'percent': memory.percent,
                    'buffers': getattr(memory, 'buffers', 0),
                    'cached': getattr(memory, 'cached', 0)
                },
                'swap': {
                    'total': swap.total,
                    'used': swap.used,
                    'free': swap.free,
                    'percent': swap.percent,
                    'sin': getattr(swap, 'sin', 0),
                    'sout': getattr(swap, 'sout', 0)
                }
            }
        except Exception as e:
            logging.error(f"Error getting memory info: {str(e)}")
            return {}
    
    def get_disk_info(self) -> Dict[str, Dict]:
        """Get disk usage information
        
        Returns:
            Dict: Disk usage statistics by device
        """
        try:
            disks = {}
            for partition in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disks[partition.device] = {
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'opts': partition.opts,
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': usage.percent
                    }
                except (PermissionError, OSError) as e:
                    logging.debug(f"Skipping disk {partition.device}: {e}")
                    continue
            return disks
        except Exception as e:
            logging.error(f"Error getting disk info: {str(e)}")
            return {}
    
    def get_network_info(self) -> Dict[str, Dict]:
        """Get network interfaces information
        
        Returns:
            Dict: Network interface statistics
        """
        try:
            interfaces = {}
            net_stats = psutil.net_if_stats()
            net_addrs = psutil.net_if_addrs()
            
            for name in net_stats.keys():
                try:
                    stats = net_stats[name]
                    addrs = net_addrs.get(name, [])
                    interfaces[name] = {
                        'isup': stats.isup,
                        'duplex': stats.duplex,
                        'speed': stats.speed,
                        'mtu': stats.mtu,
                        'addresses': [
                            {
                                'family': str(addr.family),
                                'address': addr.address,
                                'netmask': addr.netmask or 'N/A',
                                'broadcast': addr.broadcast or 'N/A',
                                'ptp': addr.ptp or 'N/A'
                            } for addr in addrs
                        ],
                        'stats': psutil.net_io_counters(pernic=True)[name]._asdict()
                    }
                except Exception as e:
                    logging.debug(f"Error processing interface {name}: {e}")
                    continue
            return interfaces
        except Exception as e:
            logging.error(f"Error getting network info: {str(e)}")
            return {}
    
    def get_process_info(self) -> Dict[int, Dict]:
        """Get running processes information
        
        Returns:
            Dict: Process information and statistics by PID
        """
        try:
            processes = {}
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status', 'create_time']):
                try:
                    with proc.oneshot():
                        pinfo = proc.info
                        processes[pinfo['pid']] = {
                            'name': pinfo['name'],
                            'username': pinfo['username'],
                            'cpu_percent': pinfo['cpu_percent'],
                            'memory_percent': pinfo['memory_percent'],
                            'status': pinfo['status'],
                            'create_time': datetime.fromtimestamp(pinfo['create_time']).isoformat(),
                            'exe': proc.exe() or 'N/A',
                            'cmdline': proc.cmdline() or []
                        }
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                    logging.debug(f"Skipping process {proc.pid}: {e}")
                    continue
            return processes
        except Exception as e:
            logging.error(f"Error getting process info: {str(e)}")
            return {}
    
    def get_all_info(self) -> Dict[str, Any]:
        """Get all system information
        
        Returns:
            Dict: Complete system information
        """
        current_time = time.time()
        
        # Update cache if interval has passed
        if current_time - self.last_update >= self.update_interval or not self.info_cache:
            try:
                self.info_cache = {
                    'timestamp': datetime.now().isoformat(),
                    'basic': self.get_basic_info(),
                    'cpu': self.get_cpu_info(),
                    'memory': self.get_memory_info(),
                    'disk': self.get_disk_info(),
                    'network': self.get_network_info(),
                    'processes': self.get_process_info()
                }
                self.last_update = current_time
                logging.info("System information cache updated")
            except Exception as e:
                logging.error(f"Error updating system info cache: {e}")
        
        return self.info_cache.copy()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    sys_info = SystemInfo(update_interval=5)
    
    # Get all info
    info = sys_info.get_all_info()
    
    # Print some key information
    print(f"System: {info['basic']['platform']} {info['basic']['platform_release']}")
    print(f"CPU: {info['cpu'].get('brand_raw', 'Unknown')} ({info['cpu']['physical_cores']} cores)")
    print(f"Memory: {info['memory']['virtual']['used'] / 1024**3:.2f}/{info['memory']['virtual']['total'] / 1024**3:.2f} GB")
    print(f"Network Interfaces: {list(info['network'].keys())}")
    print(f"Running Processes: {len(info['processes'])}")
    
    # Save to JSON file
    with open('system_info.json', 'w') as f:
        json.dump(info, f, indent=2)
    print("System info saved to system_info.json")