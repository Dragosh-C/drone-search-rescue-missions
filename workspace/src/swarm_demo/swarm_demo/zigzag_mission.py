import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from rclpy.qos import qos_profile_sensor_data
import math
import json

class ZigzagMissionNode(Node):
    def __init__(self):
        super().__init__('zigzag_mission_node')
        
        self.publisher = self.create_publisher(PoseStamped, '/mavros/setpoint_position/local', 10)
        self.subscriber = self.create_subscription(PoseStamped, '/mavros/local_position/pose', self.pose_callback, qos_profile_sensor_data)
        
        # Listen for web commands
        self.web_sub = self.create_subscription(String, '/webapp/scan_zone', self.web_callback, 10)
        self.timer = self.create_timer(0.1, self.publish_setpoint) # 10Hz timer
        
        self.waypoints = []
        self.current_wp_index = 0
        self.current_pose = None
        self.is_flying = False

    def web_callback(self, msg):
        # When the web page sends a zone, decode the JSON
        data = json.loads(msg.data)
        self.get_logger().info(f"Received scan request: {data}")
        
        # Generate the path
        self.generate_zigzag(data['x'], data['y'], data['width'], data['height'], data['spacing'], data['altitude'])
        self.is_flying = True

    def generate_zigzag(self, start_x, start_y, width, height, spacing, altitude):
        self.waypoints = []

        #  ADD TAKEOFF WAYPOINT
        if self.current_pose:
            self.waypoints.append((self.current_pose.x, self.current_pose.y, altitude))
        else:
            self.waypoints.append((0.0, 0.0, altitude))

        x_current = start_x
        direction = 1 # 1 moves Y up, -1 moves Y down
        
        while x_current <= start_x + width:
            if direction == 1:
                self.waypoints.append((x_current, start_y, altitude))          # Bottom edge
                self.waypoints.append((x_current, start_y + height, altitude)) # Top edge
            else:
                self.waypoints.append((x_current, start_y + height, altitude)) # Top edge
                self.waypoints.append((x_current, start_y, altitude))          # Bottom edge
            
            x_current += spacing # Move right
            direction *= -1      # Flip Y direction
            
        self.current_wp_index = 0
        self.get_logger().info(f"Generated {len(self.waypoints)} waypoints for zigzag scan!")

    def pose_callback(self, msg):
        self.current_pose = msg.pose.position
        
        if self.current_pose and self.is_flying and self.current_wp_index < len(self.waypoints):
            target_x, target_y, target_z = self.waypoints[self.current_wp_index]
            distance = math.sqrt((self.current_pose.x - target_x)**2 + (self.current_pose.y - target_y)**2 + (self.current_pose.z - target_z)**2)
            
            if distance < 1.5:
                self.get_logger().info(f"Reached waypoint {self.current_wp_index + 1}/{len(self.waypoints)}")
                self.current_wp_index += 1
                if self.current_wp_index >= len(self.waypoints):
                    self.get_logger().info("Scan Complete. Hovering.")
                    self.is_flying = False

    def publish_setpoint(self):
        if self.is_flying and self.current_wp_index < len(self.waypoints):
            msg = PoseStamped()
            
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = "map"
            
            msg.pose.orientation.x = 0.0
            msg.pose.orientation.y = 0.0
            msg.pose.orientation.z = 0.0
            msg.pose.orientation.w = 1.0 

            msg.pose.position.x = float(self.waypoints[self.current_wp_index][0])
            msg.pose.position.y = float(self.waypoints[self.current_wp_index][1])
            msg.pose.position.z = float(self.waypoints[self.current_wp_index][2])
            
            self.publisher.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = ZigzagMissionNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
