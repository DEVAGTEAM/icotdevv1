#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import socket
import psutil
import threading
import logging
from datetime import datetime
from typing import Optional, Dict, List, Callable

class NetworkMonitor:
    """Advanced network monitoring and traffic analysis"""
    
    def __init__(self):
        """Initialize the network monitor"""
        self.monitoring: bool = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.traffic_stats: Dict[str, Dict] = {}
        self.connection_history: List[Dict] = []
        self.alert_callback: Optional[Callable[[Dict], None]] = None
        self.traffic_threshold: int = 1024 * 1024  # 1MB/s default threshold
        self._lock = threading.Lock()
    
    def set_alert_callback(self, callback: Callable[[Dict], None]) -> None:
        """Set callback for network alerts
        
        Args:
            callback: Function to call when alerts are triggered
        """
        self.alert_callback = callback
    
    def set_traffic_threshold(self, bytes_per_second: int) -> None:
        """Set traffic threshold for alerts
        
        Args:
            bytes_per_second: Threshold in bytes per second
        """
        if bytes_per_second < 0:
            raise ValueError("Traffic threshold cannot be negative")
        self.traffic_threshold = bytes_per_second

    def start_monitoring(self) -> bool:
        """Start network monitoring
        
        Returns:
            bool: True if monitoring started successfully
        """
        if self.monitoring:
            logging.warning("Network monitoring is already running")
            return False
        
        self.monitoring = True
        
        def monitor_worker():
            last_io = psutil.net_io_counters(pernic=True)
            last_time = time.time()
            
            while self.monitoring:
                try:
                    # Get current network stats
                    current_io = psutil.net_io_counters(pernic=True)
                    current_time = time.time()
                    time_delta = current_time - last_time
                    
                    if time_delta <= 0:
                        time.sleep(0.1)  # Prevent division by zero
                        continue
                    
                    # Calculate traffic rates for each interface
                    for interface in current_io.keys():
                        if interface in last_io:
                            bytes_sent = current_io[interface].bytes_sent - last_io[interface].bytes_sent
                            bytes_recv = current_io[interface].bytes_recv - last_io[interface].bytes_recv
                            
                            # Calculate rates in bytes per second
                            send_rate = bytes_sent / time_delta
                            recv_rate = bytes_recv / time_delta
                            
                            # Update traffic stats with thread safety
                            with self._lock:
                                self.traffic_stats[interface] = {
                                    'timestamp': datetime.fromtimestamp(current_time).isoformat(),
                                    'send_rate': send_rate,
                                    'recv_rate': recv_rate,
                                    'total_sent': current_io[interface].bytes_sent,
                                    'total_recv': current_io[interface].bytes_recv,
                                    'packets_sent': current_io[interface].packets_sent,
                                    'packets_recv': current_io[interface].packets_recv
                                }
                            
                            # Check for traffic threshold alerts
                            if (send_rate > self.traffic_threshold or recv_rate > self.traffic_threshold) and self.alert_callback:
                                self.alert_callback({
                                    'type': 'traffic_threshold',
                                    'interface': interface,
                                    'send_rate': send_rate,
                                    'recv_rate': recv_rate,
                                    'threshold': self.traffic_threshold,
                                    'timestamp': datetime.fromtimestamp(current_time).isoformat()
                                })
                    
                    # Update connection history
                    connections = get_connections()
                    if connections.get('success', False):
                        self.connection_history.append({
                            'timestamp': datetime.fromtimestamp(current_time).isoformat(),
                            'connections': connections['connections'],
                            'interfaces': connections['interfaces'],
                            'stats': connections['stats']
                        })
                        
                        # Keep only last 100 history entries
                        if len(self.connection_history) > 100:
                            self.connection_history.pop(0)
                    
                    last_io = current_io
                    last_time = current_time
                    
                except Exception as e:
                    logging.error(f"Error in network monitoring: {e}")
                
                time.sleep(1)  # Update every second
        
        self.monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
        self.monitor_thread.start()
        logging.info("Network monitoring started")
        return True
    
    def stop_monitoring(self) -> None:
        """Stop network monitoring"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
            self.monitor_thread = None
        logging.info("Network monitoring stopped")
    
    def get_traffic_stats(self) -> Dict[str, Dict]:
        """Get current traffic statistics
        
        Returns:
            dict: Dictionary containing traffic statistics for each interface
        """
        return self.traffic_stats.copy()
    
    def get_connection_history(self) -> List[Dict]:
        """Get connection history
        
        Returns:
            list: List of historical connection data
        """
        return self.connection_history.copy()

def get_connections() -> Dict:
    """Get current network connections and statistics
    
    Returns:
        dict: Dictionary containing connections, interfaces, and stats
    """
    try:
        connections = []
        
        # Get all network connections
        for conn in psutil.net_connections(kind='all'):
            try:
                # Get process information
                process_name = 'System'
                if conn.pid:
                    try:
                        process = psutil.Process(conn.pid)
                        process_name = process.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                # Format connection information
                connection_info = {
                    'protocol': 'TCP' if conn.type == socket.SOCK_STREAM else 'UDP',
                    'local_address': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else 'N/A',
                    'remote_address': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else 'N/A',
                    'status': conn.status if conn.type == socket.SOCK_STREAM else 'N/A',
                    'pid': conn.pid if conn.pid else 0,
                    'process': process_name
                }
                
                connections.append(connection_info)
            except Exception as e:
                logging.debug(f"Error processing connection: {e}")
                continue
        
        # Get network interface information
        interfaces = []
        for interface_name, interface_addresses in psutil.net_if_addrs().items():
            for address in interface_addresses:
                if address.family == socket.AF_INET:  # IPv4 only for now
                    interfaces.append({
                        'name': interface_name,
                        'ip': address.address,
                        'netmask': address.netmask or 'N/A',
                        'broadcast': address.broadcast or 'N/A'
                    })
        
        # Get network statistics
        io_counters = psutil.net_io_counters(pernic=True)
        stats = []
        for interface_name, counters in io_counters.items():
            stats.append({
                'name': interface_name,
                'bytes_sent': counters.bytes_sent,
                'bytes_recv': counters.bytes_recv,
                'packets_sent': counters.packets_sent,
                'packets_recv': counters.packets_recv,
                'errin': counters.errin,
                'errout': counters.errout,
                'dropin': counters.dropin,
                'dropout': counters.dropout
            })
        
        return {
            'success': True,
            'connections': connections,
            'interfaces': interfaces,
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logging.error(f"Error getting connections: {e}")
        return {
            'success': False,
            'message': str(e)
        }

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    monitor = NetworkMonitor()
    
    def alert_handler(data):
        logging.warning(f"Network Alert: {data}")
    
    monitor.set_alert_callback(alert_handler)
    monitor.set_traffic_threshold(1024 * 1024)  # 1MB/s
    
    if monitor.start_monitoring():
        try:
            print("Network monitoring started. Press Ctrl+C to stop.")
            time.sleep(10)  # Run for 10 seconds
            stats = monitor.get_traffic_stats()
            history = monitor.get_connection_history()
            
            print("\nTraffic Stats:")
            for interface, data in stats.items():
                print(f"{interface}: Send: {data['send_rate']:.2f} B/s, Recv: {data['recv_rate']:.2f} B/s")
            
            print("\nLast Connection History Entry:")
            if history:
                print(json.dumps(history[-1], indent=2))
                
        except KeyboardInterrupt:
            pass
        finally:
            monitor.stop_monitoring()