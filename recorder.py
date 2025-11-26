import cv2
import numpy as np
import threading
import time
import logging
import os

class ScreenRecorder:
    def __init__(self, driver, output_path, fps=5.0):
        self.driver = driver
        self.output_path = output_path
        self.fps = fps
        self.stop_event = threading.Event()
        self.thread = None
        self.logger = logging.getLogger(__name__)

    def start(self):
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._record_loop)
        self.thread.start()
        self.logger.info(f"Started screen recording to {self.output_path}")

    def stop(self):
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join()
            self.logger.info(f"Stopped screen recording. Saved to {self.output_path}")

    def _record_loop(self):
        video_writer = None
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        try:
            while not self.stop_event.is_set():
                start_time = time.time()
                
                try:
                    # Capture screenshot as PNG binary
                    png_data = self.driver.get_screenshot_as_png()
                    
                    # Convert to numpy array
                    nparr = np.frombuffer(png_data, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if img is None:
                        continue

                    # Initialize video writer on first frame
                    if video_writer is None:
                        height, width, _ = img.shape
                        # MJPG is more compatible in headless docker
                        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                        video_writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, (width, height))
                    
                    video_writer.write(img)
                    
                except Exception as e:
                    self.logger.warning(f"Error capturing frame: {e}")
                
                # Maintain FPS
                elapsed = time.time() - start_time
                wait_time = max(0, (1.0 / self.fps) - elapsed)
                time.sleep(wait_time)
                
        finally:
            if video_writer:
                video_writer.release()
