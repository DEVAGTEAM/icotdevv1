#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import io
import time
import threading
import logging
from datetime import datetime
from typing import List, Optional, Callable, Union

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logging.warning("OpenCV (cv2) module not available, webcam functionality will be limited")

class WebcamManager:
    """Manages webcam operations including capture and streaming"""
    
    def __init__(self):
        """Initialize the webcam manager"""
        self.streaming: bool = False
        self.stream_thread: Optional[threading.Thread] = None
        self.current_camera: Optional[cv2.VideoCapture] = None
        self.frame_callback: Optional[Callable[[bytes], None]] = None
    
    def list_cameras(self) -> List[int]:
        """List available webcam devices
        
        Returns:
            list: List of available camera indices
        """
        if not CV2_AVAILABLE:
            logging.error("Cannot list cameras: OpenCV not available")
            return []
            
        available_cameras = []
        try:
            for i in range(10):  # Check first 10 camera indices
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    available_cameras.append(i)
                    logging.debug(f"Found camera at index {i}")
                cap.release()
        except Exception as e:
            logging.error(f"Error listing cameras: {e}")
        
        return available_cameras

    def capture_webcam(self, camera_index: int = 0) -> Optional[bytes]:
        """Capture an image from the webcam
    
        Args:
            camera_index: Index of the camera to use (default: 0 for primary camera)
        
        Returns:
            bytes: Webcam image data in PNG format or None if failed
        """
        try:
            if not CV2_AVAILABLE:
                logging.error("Cannot capture webcam: OpenCV not available")
                return None
        
            # Initialize webcam
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                logging.error(f"Failed to open webcam at index {camera_index}")
                cap.release()
                return None
        
            # Capture a frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                logging.error(f"Failed to capture image from webcam at index {camera_index}")
                return None
        
            # Convert BGR to RGB and encode to PNG
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            is_success, buffer = cv2.imencode(".png", frame_rgb)
            if not is_success:
                logging.error("Failed to encode webcam image")
                return None
        
            logging.info(f"Successfully captured image from webcam {camera_index}")
            return buffer.tobytes()
    
        except Exception as e:
            logging.error(f"Error capturing webcam image: {e}")
            return None

    def start_stream(self, camera_index: int = 0, callback: Optional[Callable[[bytes], None]] = None, fps: int = 30) -> bool:
        """Start streaming from the webcam
        
        Args:
            camera_index: Index of the camera to use (default: 0)
            callback: Function to call with each frame (receives PNG bytes)
            fps: Target frames per second (default: 30)
        
        Returns:
            bool: True if streaming started successfully
        """
        if not CV2_AVAILABLE:
            logging.error("Cannot start stream: OpenCV not available")
            return False
        
        if self.streaming:
            logging.warning("Stream already running")
            return False
        
        if fps <= 0:
            logging.error("FPS must be positive")
            return False
        
        self.streaming = True
        self.frame_callback = callback
        
        def stream_worker():
            try:
                cap = cv2.VideoCapture(camera_index)
                if not cap.isOpened():
                    logging.error(f"Failed to open webcam at index {camera_index}")
                    self.streaming = False
                    return
                
                self.current_camera = cap
                frame_time = 1.0 / fps
                last_frame_time = time.time()
                
                while self.streaming:
                    try:
                        ret, frame = cap.read()
                        if not ret:
                            logging.warning(f"Failed to read frame from webcam {camera_index}")
                            time.sleep(0.1)
                            continue
                        
                        # Convert BGR to RGB and encode to PNG
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        is_success, buffer = cv2.imencode(".png", frame_rgb)
                        if not is_success:
                            logging.warning("Failed to encode frame")
                            continue
                        
                        frame_data = buffer.tobytes()
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
                        last_frame_time = current_time
                    
                    except Exception as e:
                        logging.error(f"Error during streaming: {e}")
                        break
            
            finally:
                if cap.isOpened():
                    cap.release()
                self.current_camera = None
                self.streaming = False
                logging.info(f"Webcam stream stopped for camera {camera_index}")
        
        self.stream_thread = threading.Thread(target=stream_worker, daemon=True)
        self.stream_thread.start()
        logging.info(f"Started webcam stream on camera {camera_index} at {fps} FPS")
        return True
    
    def stop_stream(self) -> None:
        """Stop the webcam stream"""
        if not self.streaming:
            return
            
        self.streaming = False
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=2.0)
            self.stream_thread = None
        
        if self.current_camera and self.current_camera.isOpened():
            self.current_camera.release()
            self.current_camera = None
        self.frame_callback = None
        logging.info("Webcam stream fully stopped")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    webcam = WebcamManager()
    
    # List available cameras
    cameras = webcam.list_cameras()
    print(f"Available cameras: {cameras}")
    
    if cameras:
        # Capture single image
        image_data = webcam.capture_webcam(camera_index=cameras[0])
        if image_data:
            with open("webcam_capture.png", "wb") as f:
                f.write(image_data)
            print("Webcam capture saved to webcam_capture.png")
        
        # Test streaming
        def frame_handler(frame_data):
            logging.info(f"Received frame of size {len(frame_data)} bytes")
        
        if webcam.start_stream(camera_index=cameras[0], callback=frame_handler, fps=10):
            try:
                print("Streaming... Press Ctrl+C to stop")
                time.sleep(5)  # Stream for 5 seconds
            except KeyboardInterrupt:
                pass
            finally:
                webcam.stop_stream()
                print("Streaming stopped")