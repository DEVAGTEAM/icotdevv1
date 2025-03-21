#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import io
import time
import threading
import logging
from datetime import datetime
from typing import List, Optional, Callable, Union, Dict

try:
    from PIL import ImageGrab, Image
    import mss
    import mss.tools
    MSS_AVAILABLE = True
    PIL_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False
    PIL_AVAILABLE = False
    logging.warning("PIL or MSS modules not available, screenshot functionality will be limited")

class ScreenCapture:
    """Manages screen capture operations including screenshots and recording"""
    
    def __init__(self):
        """Initialize the screen capture manager"""
        self.recording: bool = False
        self.record_thread: Optional[threading.Thread] = None
        self.frame_callback: Optional[Callable[[bytes], None]] = None
        self.monitors: List[Dict] = self.get_monitors()
    
    def get_monitors(self) -> List[Dict]:
        """Get information about all monitors
        
        Returns:
            list: List of monitor dictionaries with position and resolution
        """
        if not MSS_AVAILABLE:
            return []
            
        try:
            with mss.mss() as sct:
                monitors = [dict(monitor) for monitor in sct.monitors[1:]]  # Skip the 'all monitors' monitor
                for i, monitor in enumerate(monitors):
                    monitor['index'] = i
                    monitor['name'] = f"Monitor {i}"
                return monitors
        except Exception as e:
            logging.error(f"Error getting monitors: {e}")
            return []

    def take_screenshot(self, monitor_index: Optional[int] = None) -> Optional[bytes]:
        """Take a screenshot of the specified monitor or primary monitor
        
        Args:
            monitor_index: Index of the monitor to capture (None for primary)
            
        Returns:
            bytes: PNG image data or None if failed
        """
        try:
            if not MSS_AVAILABLE and not PIL_AVAILABLE:
                logging.error("No screenshot capability available (MSS and PIL missing)")
                return None

            if MSS_AVAILABLE:
                with mss.mss() as sct:
                    if monitor_index is not None:
                        if monitor_index < 0 or monitor_index >= len(sct.monitors) - 1:
                            logging.error(f"Invalid monitor index: {monitor_index}")
                            return None
                        monitor = sct.monitors[monitor_index + 1]  # +1 to skip 'all monitors'
                    else:
                        monitor = sct.monitors[1]  # Default to first physical monitor
                    
                    screenshot = sct.grab(monitor)
                    return mss.tools.to_png(screenshot.rgb, screenshot.size)
            else:
                # Fallback to PIL
                screenshot = ImageGrab.grab()
                img_byte_arr = io.BytesIO()
                screenshot.save(img_byte_arr, format='PNG')
                logging.info("Screenshot taken using PIL fallback")
                return img_byte_arr.getvalue()
    
        except Exception as e:
            logging.error(f"Error taking screenshot: {e}")
            return None

    def start_recording(self, monitor_index: Optional[int] = None, callback: Optional[Callable[[bytes], None]] = None, fps: int = 30) -> bool:
        """Start screen recording
        
        Args:
            monitor_index: Index of the monitor to record (None for primary)
            callback: Function to call with each frame (receives bytes)
            fps: Target frames per second (default: 30)
            
        Returns:
            bool: True if recording started successfully
        """
        if not MSS_AVAILABLE:
            logging.error("Cannot start recording: MSS not available")
            return False
        
        if self.recording:
            logging.warning("Recording already in progress")
            return False
        
        if fps <= 0:
            logging.error("FPS must be positive")
            return False
        
        self.recording = True
        self.frame_callback = callback
        
        def record_worker():
            try:
                with mss.mss() as sct:
                    if monitor_index is not None:
                        if monitor_index < 0 or monitor_index >= len(sct.monitors) - 1:
                            logging.error(f"Invalid monitor index for recording: {monitor_index}")
                            self.recording = False
                            return
                        monitor = sct.monitors[monitor_index + 1]
                    else:
                        monitor = sct.monitors[1]  # Default to first physical monitor
                    
                    frame_time = 1.0 / fps
                    last_frame_time = time.time()
                    
                    while self.recording:
                        try:
                            screenshot = sct.grab(monitor)
                            frame_data = mss.tools.to_png(screenshot.rgb, screenshot.size)
                            
                            if self.frame_callback:
                                try:
                                    self.frame_callback(frame_data)
                                except Exception as e:
                                    logging.error(f"Error in frame callback: {e}")
                            
                            # Maintain target FPS
                            current_time = time.time()
                            sleep_time = frame_time - (current_time - last_frame_time)
                            if sleep_time > 0:
                                time.sleep(sleep_time)
                            last_frame_time = time.time()
                            
                        except Exception as e:
                            logging.error(f"Error during screen recording: {e}")
                            break
            finally:
                self.recording = False
        
        self.record_thread = threading.Thread(target=record_worker, daemon=True)
        self.record_thread.start()
        logging.info(f"Screen recording started on monitor {monitor_index if monitor_index is not None else 'primary'} at {fps} FPS")
        return True
    
    def stop_recording(self) -> None:
        """Stop screen recording"""
        if not self.recording:
            return
            
        self.recording = False
        if self.record_thread and self.record_thread.is_alive():
            self.record_thread.join(timeout=2.0)
            self.record_thread = None
        self.frame_callback = None
        logging.info("Screen recording stopped")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    capture = ScreenCapture()
    
    # Get monitor info
    monitors = capture.get_monitors()
    print("Available monitors:", monitors)
    
    # Take a screenshot
    screenshot = capture.take_screenshot(0)  # Primary monitor
    if screenshot:
        with open("screenshot.png", "wb") as f:
            f.write(screenshot)
        print("Screenshot saved as screenshot.png")
    
    # Test recording
    def frame_handler(frame_data):
        # Example: just log frame size
        logging.info(f"Received frame of size {len(frame_data)} bytes")
    
    if capture.start_recording(monitor_index=0, callback=frame_handler, fps=10):
        try:
            print("Recording... Press Ctrl+C to stop")
            time.sleep(5)  # Record for 5 seconds
        except KeyboardInterrupt:
            pass
        finally:
            capture.stop_recording()
            print("Recording stopped")