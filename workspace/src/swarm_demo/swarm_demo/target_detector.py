#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
import json
import math
import numpy as np
import cv2
from cv_bridge import CvBridge

from sensor_msgs.msg import Image, NavSatFix
from std_msgs.msg import Float64, String
from mavros_msgs.msg import VfrHud

class GeneralizedTargetDetectorNode(Node):
    def __init__(self):
        super().__init__('generalized_target_detector_node')
        
        self.bridge = CvBridge()
        
        # Gazebo Origin Constants
        self.HOME_LAT = 44.435720
        self.HOME_LON = 26.047583
        self.R = 6378137.0  # Earth's radius in meters

        self.drone_lat = 0.0
        self.drone_lon = 0.0
        self.drone_alt = 0.0
        self.drone_heading = 0.0 
        
        self.FOV_H = 2.0  
        self.IMG_W = 640
        self.IMG_H = 480

        # --- MULTI-TARGET DATABASE ---
        # Stores already discovered targets to prevent duplicate pins
        # Format: {"target_id": {"lat": X, "lon": Y, "color": "red"}}
        self.found_targets = []
        self.target_id_counter = 1
        self.DUPLICATE_THRESHOLD_METERS = 3.0 # If a detection is within 3m of an old one, ignore it


        self.color_profiles = {
    "Red/Orange Target": {
        "masks": [
            {"lower": np.array([0, 80, 60]), "upper": np.array([10, 255, 255])},
            {"lower": np.array([170, 80, 60]), "upper": np.array([180, 255, 255])}
        ],
        "bgr_draw_color": (0, 0, 255)
    },
    "Blue Target": {
        "masks": [
            {"lower": np.array([100, 100, 60]), "upper": np.array([130, 255, 255])}
        ],
        "bgr_draw_color": (255, 0, 0)
    },
    "Green/Yellow Target": {
        "masks": [
            {"lower": np.array([35, 80, 60]), "upper": np.array([85, 255, 255])}
        ],
        "bgr_draw_color": (0, 255, 0)
    }
}

        # --- Subscriptions ---
        self.create_subscription(Image, '/uav1/camera/image_raw', self.image_callback, 10)
        self.create_subscription(NavSatFix, '/mavros/global_position/global', self.gps_callback, qos_profile_sensor_data)
        self.create_subscription(Float64, '/mavros/global_position/rel_alt', self.alt_callback, qos_profile_sensor_data)
        self.create_subscription(VfrHud, '/mavros/vfr_hud', self.vfr_callback, qos_profile_sensor_data)


        self.active_targets = ["Red/Orange Target", "Blue Target", "Green/Yellow Target"]
        self.create_subscription(String, '/search_and_rescue/target_config', self.config_callback, 10)

        # --- Publishers ---
        self.target_pub = self.create_publisher(String, '/search_and_rescue/target_found', 10)
        
        self.get_logger().info("Multi-Target Detector Active! Hunting Red, Blue, and Green...")

    def gps_callback(self, msg):
        self.drone_lat = msg.latitude
        self.drone_lon = msg.longitude

    def alt_callback(self, msg):
        self.drone_alt = msg.data

    def vfr_callback(self, msg):
        self.drone_heading = msg.heading

    def config_callback(self, msg):
        try:
            self.active_targets = json.loads(msg.data)
            self.get_logger().info(f"Updated Hunting Signatures: {self.active_targets}")
        except Exception as e:
            pass

    def image_callback(self, msg):
        # Safety height check
        if self.drone_alt < 2.0 or self.drone_lat == 0.0:
            return

        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception:
            return

        hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)

        # Iterate over every color target profile we care about
        for color_name, profile in self.color_profiles.items():
            if color_name not in self.active_targets:
                continue # Skip this color entirely!
            combined_mask = None
            for mask_range in profile["masks"]:
                m = cv2.inRange(hsv, mask_range["lower"], mask_range["upper"])
                if combined_mask is None:
                    combined_mask = m
                else:
                    combined_mask = cv2.bitwise_or(combined_mask, m)

            # Find object contours for this specific color
            contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                if cv2.contourArea(contour) > 400: # Filter out noise
                    M = cv2.moments(contour)
                    if M["m00"] == 0: continue
                    
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])

                    # Process geolocation
                    self.geolocate_target(cX, cY, color_name)

                    cv2.circle(cv_image, (cX, cY), 15, profile["bgr_draw_color"], 2)
                    cv2.putText(cv_image, f"LOCK: {color_name}", (cX - 60, cY - 25), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, profile["bgr_draw_color"], 2)

        # Open background view feed window
        try:
            cv2.imshow("Multi-Target Onboard Vision System", cv_image)
            cv2.waitKey(1)
        except Exception:
            pass

    def geolocate_target(self, pixel_x, pixel_y, color_label):
        # Translate pixel to camera-frame offset metric vectors
        delta_p_x = pixel_x - (self.IMG_W / 2.0)
        delta_p_y = (self.IMG_H / 2.0) - pixel_y 

        ground_width = 2.0 * self.drone_alt * math.tan(self.FOV_H / 2.0)
        meters_per_pixel = ground_width / self.IMG_W

        x_cam = delta_p_x * meters_per_pixel
        y_cam = delta_p_y * meters_per_pixel

        # Compensate for drone heading rotation orientation
        heading_rad = math.radians(-self.drone_heading)
        x_enu = x_cam * math.cos(heading_rad) - y_cam * math.sin(heading_rad)
        y_enu = x_cam * math.sin(heading_rad) + y_cam * math.cos(heading_rad)

        # Project back to global GPS decimal coordinate spaces
        dLat_drone = (self.drone_lat - self.HOME_LAT) * math.pi / 180.0
        dLon_drone = (self.drone_lon - self.HOME_LON) * math.pi / 180.0
        
        drone_x = dLon_drone * self.R * math.cos(math.radians(self.HOME_LAT))
        drone_y = dLat_drone * self.R

        target_x = drone_x + x_enu
        target_y = drone_y + y_enu

        target_lat = self.HOME_LAT + (target_y / self.R) * (180.0 / math.pi)
        target_lon = self.HOME_LON + (target_x / (self.R * math.cos(math.radians(self.HOME_LAT)))) * (180.0 / math.pi)

        # DUPLICATE FILTER CHECK (Haversine/Euclidean approximation)
        is_duplicate = False
        for target in self.found_targets:
            lat_diff = (target_lat - target["lat"]) * (math.pi / 180.0) * self.R
            lon_diff = (target_lon - target["lon"]) * (math.pi / 180.0) * self.R * math.cos(math.radians(self.HOME_LAT))
            distance = math.sqrt(lat_diff**2 + lon_diff**2)

            if distance < self.DUPLICATE_THRESHOLD_METERS:
                is_duplicate = True
                break

        # Save new physical object and transmit to the Web GCS
        if not is_duplicate:
            new_target = {
                "id": self.target_id_counter,
                "latitude": target_lat,
                "longitude": target_lon,
                "type": color_label
            }
            # Append target coordinates locally
            self.found_targets.append({"lat": target_lat, "lon": target_lon})
            self.target_id_counter += 1

            # Package up the structured JSON and broadcast it to the web network
            msg = String()
            msg.data = json.dumps(new_target)
            self.target_pub.publish(msg)
            
            self.get_logger().info(
                f"NEW TARGET DISCOVERED! ID: {new_target['id']} | "
                f"Type: {color_label} | Lat: {target_lat:.6f}, Lon: {target_lon:.6f}"
            )

def main(args=None):
    rclpy.init(args=args)
    node = GeneralizedTargetDetectorNode()
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