#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
import json
import math
import cv2
from cv_bridge import CvBridge
from swarm_demo.evidence_logger import EvidenceLogger

from sensor_msgs.msg import Image, NavSatFix
from std_msgs.msg import Float64, String
from mavros_msgs.msg import VfrHud

import torch
_original_torch_load = torch.load

def _hacked_torch_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)

torch.load = _hacked_torch_load

from ultralyticsplus import YOLO

class YoloMappingDetectorNode(Node):
    def __init__(self):
        super().__init__('yolo_mapping_detector_node')
        
        self.bridge = CvBridge()
        
        self.get_logger().info("Downloading & Loading VisDrone AI Model...")
        self.model = YOLO('mshamrai/yolov8s-visdrone') 
        
        self.model.overrides['conf'] = 0.15  
        self.model.overrides['iou'] = 0.45 
        
        self.get_logger().info("VisDrone Model Loaded! Waiting for flight data...")

        self.evidence_saver = EvidenceLogger(cooldown_seconds=3.0)

        self.HOME_LAT = 44.435720
        self.HOME_LON = 26.047583
        self.R = 6378137.0  

        self.drone_lat = 0.0
        self.drone_lon = 0.0
        self.drone_alt = 0.0
        self.drone_heading = 0.0 
        
        self.FOV_H = 2.0  
        self.IMG_W = 640
        self.IMG_H = 480

        self.found_targets = []
        self.target_id_counter = 1
        
        self.DUPLICATE_THRESHOLD_METERS = 18.0 

        self.allowed_targets = ["PERSON", "VEHICLE"]

        self.create_subscription(Image, '/uav1/camera/image_raw', self.image_callback, 10)
        self.create_subscription(NavSatFix, '/mavros/global_position/global', self.gps_callback, qos_profile_sensor_data)
        self.create_subscription(Float64, '/mavros/global_position/rel_alt', self.alt_callback, qos_profile_sensor_data)
        self.create_subscription(VfrHud, '/mavros/vfr_hud', self.vfr_callback, qos_profile_sensor_data)

        self.config_sub = self.create_subscription(String, '/search_and_rescue/target_config', self.config_callback, 10)
        self.target_pub = self.create_publisher(String, '/search_and_rescue/target_found', 10)

    def config_callback(self, msg):
        try:
            self.allowed_targets = json.loads(msg.data)
            self.get_logger().info(f"Web configuration updated! Monitoring fields: {self.allowed_targets}")
        except Exception as e:
            self.get_logger().error(f"Failed to process config map: {e}")

    def gps_callback(self, msg):
        self.drone_lat = msg.latitude
        self.drone_lon = msg.longitude

    def alt_callback(self, msg):
        self.drone_alt = msg.data

    def vfr_callback(self, msg):
        self.drone_heading = msg.heading

    def image_callback(self, msg):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            display_frame = cv_image.copy()
        except Exception:
            return

        if self.drone_alt < 2.0 or self.drone_lat == 0.0:
            try:
                cv2.imshow("UAV VisDrone Targeting", display_frame)
                cv2.waitKey(1)
            except Exception:
                pass
            return

        classes_to_detect = []
        if "PERSON" in self.allowed_targets:
            classes_to_detect.extend([0, 1]) 
        if "VEHICLE" in self.allowed_targets:
            classes_to_detect.extend([3, 4, 5, 8]) 

        if not classes_to_detect:
            try:
                cv2.imshow("UAV VisDrone Targeting", display_frame)
                cv2.waitKey(1)
            except Exception:
                pass
            return

        results = self.model.predict(cv_image, classes=classes_to_detect, verbose=False)

        for box in results[0].boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            
            label = "VEHICLE" if class_id in [3, 4, 5, 8] else "PERSON"
            
            xyxy = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
            
            cX = int((x1 + x2) / 2.0)
            cY = int((y1 + y2) / 2.0)

            # Check if this specific detection is a duplicate BEFORE we draw it
            is_duplicate, target_id = self.check_if_duplicate(cX, cY, label)

            if not is_duplicate:
                # NEW TARGET HIT: Draw bright primary colors + indicator circle
                color = (231, 27, 197) if label == "VEHICLE" else (0, 132, 141) # Match GCS Purple/Olive (BGR format)
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 4) # Thicker box
                cv2.circle(display_frame, (cX, cY), 6, color, -1)
                cv2.putText(display_frame, f"NEW {label} {confidence*100:.0f}%", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                # Commit to backend logs and send to Leaflet web UI
                self.process_new_target(target_id, cX, cY, label, display_frame)
            else:
                #ALREADY TRACKED: Draw a faint, thin gray box so it doesn't distract you
                gray_color = (20, 120, 120)
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), gray_color, 1) # Thin line
                cv2.putText(display_frame, f"Tracked #{target_id}", (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, gray_color, 1)

        try:
            cv2.imshow("UAV VisDrone Targeting", display_frame)
            cv2.waitKey(30)
        except Exception:
            pass

    def check_if_duplicate(self, pixel_x, pixel_y, object_label):
        """Calculates GPS coordinate of the pixel and returns (is_duplicate, target_id)"""
        delta_p_x = pixel_x - (self.IMG_W / 2.0)
        delta_p_y = (self.IMG_H / 2.0) - pixel_y 

        ground_width = 2.0 * self.drone_alt * math.tan(self.FOV_H / 2.0)
        meters_per_pixel = ground_width / self.IMG_W

        x_cam = delta_p_x * meters_per_pixel
        y_cam = delta_p_y * meters_per_pixel

        heading_rad = math.radians(-self.drone_heading)
        x_enu = x_cam * math.cos(heading_rad) - y_cam * math.sin(heading_rad)
        y_enu = x_cam * math.sin(heading_rad) + y_cam * math.cos(heading_rad)

        dLat_drone = (self.drone_lat - self.HOME_LAT) * math.pi / 180.0
        dLon_drone = (self.drone_lon - self.HOME_LON) * math.pi / 180.0
        
        drone_x = dLon_drone * self.R * math.cos(math.radians(self.HOME_LAT))
        drone_y = dLat_drone * self.R

        target_x = drone_x + x_enu
        target_y = drone_y + y_enu

        target_lat = self.HOME_LAT + (target_y / self.R) * (180.0 / math.pi)
        target_lon = self.HOME_LON + (target_x / (self.R * math.cos(math.radians(self.HOME_LAT)))) * (180.0 / math.pi)

        for target in self.found_targets:
            lat_diff = (target_lat - target["lat"]) * (math.pi / 180.0) * self.R
            lon_diff = (target_lon - target["lon"]) * (math.pi / 180.0) * self.R * math.cos(math.radians(self.HOME_LAT))
            distance = math.sqrt(lat_diff**2 + lon_diff**2)

            if distance < self.DUPLICATE_THRESHOLD_METERS and target["type"] == object_label:
                return True, target["id"]

        return False, self.target_id_counter

    def process_new_target(self, target_id, pixel_x, pixel_y, object_label, frame):
        """Converts pixels to GPS coords and fires the telemetry output over ROS2 to the dashboard"""
        delta_p_x = pixel_x - (self.IMG_W / 2.0)
        delta_p_y = (self.IMG_H / 2.0) - pixel_y 

        ground_width = 2.0 * self.drone_alt * math.tan(self.FOV_H / 2.0)
        meters_per_pixel = ground_width / self.IMG_W

        x_cam = delta_p_x * meters_per_pixel
        y_cam = delta_p_y * meters_per_pixel

        heading_rad = math.radians(-self.drone_heading)
        x_enu = x_cam * math.cos(heading_rad) - y_cam * math.sin(heading_rad)
        y_enu = x_cam * math.sin(heading_rad) + y_cam * math.cos(heading_rad)

        dLat_drone = (self.drone_lat - self.HOME_LAT) * math.pi / 180.0
        dLon_drone = (self.drone_lon - self.HOME_LON) * math.pi / 180.0
        
        drone_x = dLon_drone * self.R * math.cos(math.radians(self.HOME_LAT))
        drone_y = dLat_drone * self.R

        target_x = drone_x + x_enu
        target_y = drone_y + y_enu

        target_lat = self.HOME_LAT + (target_y / self.R) * (180.0 / math.pi)
        target_lon = self.HOME_LON + (target_x / (self.R * math.cos(math.radians(self.HOME_LAT)))) * (180.0 / math.pi)

        saved_image_name = self.evidence_saver.log_target(frame, object_label, self.get_logger())

        new_target = {
            "id": target_id,
            "latitude": target_lat,
            "longitude": target_lon,
            "type": f"AI: {object_label}",
            "image": saved_image_name if saved_image_name else "none"
        }
        
        self.found_targets.append({"id": target_id, "lat": target_lat, "lon": target_lon, "type": object_label})
        self.target_id_counter += 1

        msg = String()
        msg.data = json.dumps(new_target)
        self.target_pub.publish(msg)
        
        self.get_logger().info(f"NEW TARGET FOUND! ID: {target_id} | {object_label} | Coords: {target_lat:.5f}, {target_lon:.5f}")

def main(args=None):
    rclpy.init(args=args)
    node = YoloMappingDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()