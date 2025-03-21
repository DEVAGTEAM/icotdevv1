#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import base64
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, List, Callable

try:
    import win32clipboard
    import win32con
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
    logging.warning("pywin32 not available, clipboard monitoring disabled")

class ClipboardMonitor:
    """Clipboard monitoring and data tracking"""
    
    def __init__(self):
        """Initialize clipboard monitor"""
        self.monitoring = False
        self.monitor_thread = None
        self.history: List[Dict] = []
        self.max_history = 100
        self.last_content = None
        self.callback: Optional[Callable] = None
        self._lock = threading.Lock()
        
        # Create logs directory
        self.log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, 'clipboard.log')
    
    def set_callback(self, callback: Callable[[Dict], None]) -> None:
        """Set callback function for clipboard changes
        
        Args:
            callback: Function to call when clipboard changes
        """
        self.callback = callback
    
    def get_clipboard_data(self) -> Optional[Dict]:
        """Get current clipboard content
        
        Returns:
            Dict: Clipboard data and metadata or None if failed
        """
        if not CLIPBOARD_AVAILABLE:
            return None
            
        try:
            win32clipboard.OpenClipboard()
            
            formats = {
                win32con.CF_TEXT: 'text',
                win32con.CF_UNICODETEXT: 'unicode_text',
                win32con.CF_BITMAP: 'bitmap',
                win32con.CF_HDROP: 'files'
            }
            
            data = {}
            for format_id, format_name in formats.items():
                if win32clipboard.IsClipboardFormatAvailable(format_id):
                    try:
                        content = win32clipboard.GetClipboardData(format_id)
                        
                        if format_id in [win32con.CF_TEXT, win32con.CF_UNICODETEXT]:
                            if isinstance(content, bytes):
                                content = content.decode('utf-8', errors='ignore')
                            data[format_name] = content
                        elif format_id == win32con.CF_BITMAP:
                            # Convert bitmap to base64
                            import win32ui
                            import win32gui
                            from PIL import Image
                            import io
                            
                            # Create bitmap object
                            bmp = win32ui.CreateBitmapFromHandle(content)
                            width = bmp.GetInfo()['bmWidth']
                            height = bmp.GetInfo()['bmHeight']
                            
                            # Create device context
                            dc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                            mem_dc = dc.CreateCompatibleDC()
                            mem_dc.SelectObject(bmp)
                            
                            # Convert to PNG and encode
                            buffer = io.BytesIO()
                            bits = mem_dc.GetBitmapBits(True)
                            img = Image.frombytes('RGBA', (width, height), bits, 'raw', 'BGRA')
                            img.save(buffer, format='PNG')
                            content = base64.b64encode(buffer.getvalue()).decode()
                            data[format_name] = content
                            
                            # Cleanup
                            mem_dc.DeleteDC()
                            win32gui.ReleaseDC(0, dc.GetHandle())
                            win32ui.DeleteObject(bmp.GetHandle())
                        elif format_id == win32con.CF_HDROP:
                            data[format_name] = list(content)
                    except Exception as e:
                        logging.error(f"Error processing format {format_name}: {str(e)}")
                        continue
            
            win32clipboard.CloseClipboard()
            
            if data:
                return {
                    'timestamp': datetime.now().isoformat(),
                    'data': data
                }
            return None
            
        except Exception as e:
            logging.error(f"Error getting clipboard data: {str(e)}")
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return None
    
    def set_clipboard_text(self, text: str) -> bool:
        """Set clipboard text content
        
        Args:
            text: Text to set
            
        Returns:
            bool: True if successful
        """
        if not CLIPBOARD_AVAILABLE:
            return False
            
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, str(text))
            win32clipboard.CloseClipboard()
            return True
        except Exception as e:
            logging.error(f"Error setting clipboard text: {str(e)}")
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return False
    
    def clear_clipboard(self) -> bool:
        """Clear clipboard content
        
        Returns:
            bool: True if successful
        """
        if not CLIPBOARD_AVAILABLE:
            return False
            
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.CloseClipboard()
            return True
        except Exception as e:
            logging.error(f"Error clearing clipboard: {str(e)}")
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return False
    
    def start_monitoring(self) -> bool:
        """Start clipboard monitoring
        
        Returns:
            bool: True if monitoring started successfully
        """
        if not CLIPBOARD_AVAILABLE or self.monitoring:
            return False
        
        self.monitoring = True
        
        def monitor_worker():
            while self.monitoring:
                try:
                    current_data = self.get_clipboard_data()
                    with self._lock:
                        if current_data and (
                            not self.last_content or 
                            current_data['data'] != self.last_content['data']
                        ):
                        self.last_content = current_data
                        self.history.append(current_data)
                        
                        if len(self.history) > self.max_history:
                            self.history.pop(0)
                        
                        with open(self.log_file, 'a', encoding='utf-8') as f:
                            f.write(f"[{current_data['timestamp']}] New clipboard content:\n")
                            for format_name, content in current_data['data'].items():
                                f.write(f"Format: {format_name}\n")
                                if format_name in ['text', 'unicode_text']:
                                    f.write(f"Content: {content}\n")
                                else:
                                    f.write(f"Content: <{format_name} data>\n")
                            f.write('\n')
                        
                        if self.callback:
                            try:
                                self.callback(current_data)
                            except Exception as e:
                                logging.error(f"Callback error: {str(e)}")
                            
                except Exception as e:
                    logging.error(f"Error in clipboard monitor: {str(e)}")
                
                time.sleep(1)  # Check every second
        
        self.monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
        self.monitor_thread.start()
        return True
    
    def stop_monitoring(self) -> None:
        """Stop clipboard monitoring"""
        if self.monitoring:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
                self.monitor_thread = None
    
    def get_history(self) -> List[Dict]:
        """Get clipboard history
        
        Returns:
            List[Dict]: List of clipboard entries
        """
        return self.history.copy()
    
    def clear_history(self) -> None:
        """Clear clipboard history"""
        self.history.clear()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    monitor = ClipboardMonitor()
    
    def on_clipboard_change(data):
        logging.info(f"Clipboard changed: {data}")
    
    monitor.set_callback(on_clipboard_change)
    
    if monitor.start_monitoring():
        logging.info("Clipboard monitoring started")
        try:
            # Test setting clipboard
            monitor.set_clipboard_text("Test clipboard content")
            time.sleep(5)  # Run for 5 seconds
        finally:
            monitor.stop_monitoring()
            logging.info("Clipboard monitoring stopped")
            logging.info(f"History: {monitor.get_history()}")
    else:
        logging.error("Failed to start clipboard monitoring")