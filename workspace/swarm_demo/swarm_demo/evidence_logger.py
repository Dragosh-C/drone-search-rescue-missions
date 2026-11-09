import os
import time
import cv2
from datetime import datetime

class EvidenceLogger:
    def __init__(self, output_dir="/ros2_ws/captured_targets", cooldown_seconds=5.0):
        self.output_dir = output_dir
        self.cooldown = cooldown_seconds
        
        self.last_saved_time = {}
        
        os.makedirs(self.output_dir, exist_ok=True)

    def log_target(self, frame, label, ros_logger=None):
        current_time = time.time()
        
        if label not in self.last_saved_time:
            self.last_saved_time[label] = 0.0

        if current_time - self.last_saved_time[label] > self.cooldown:
            
            safe_label = label.replace("/", "_").replace(" ", "_").lower()
            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.output_dir}/{safe_label}_{time_str}.jpg"
            
            cv2.imwrite(filename, frame)
            
            self.last_saved_time[label] = current_time
            
            if ros_logger:
                ros_logger.info(f"EVIDENCE SAVED: {filename}")
            
            return os.path.basename(filename) 
            
        return None