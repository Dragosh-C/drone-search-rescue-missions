# #!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from mavros_msgs.srv import CommandBool, SetMode, CommandTOL, CommandHome
from mavros_msgs.msg import State
from std_msgs.msg import String
import json
import time
import threading

class DroneController(Node):
    def __init__(self):
        super().__init__('drone_mission_node')
        self.state = State()
        
        # 1. Listen to Drone State
        self.state_sub = self.create_subscription(State, '/mavros/state', self.state_cb, 10)
        
        # 2. NEW: Listen to Web Dashboard Commands!
        self.cmd_sub = self.create_subscription(String, '/webapp/drone_command', self.command_cb, 10)
        
        # 3. MAVROS Service Clients
        self.mode_cli = self.create_client(SetMode, '/mavros/set_mode')
        self.arm_cli = self.create_client(CommandBool, '/mavros/cmd/arming')
        self.takeoff_cli = self.create_client(CommandTOL, '/mavros/cmd/takeoff')
        self.set_home_cli = self.create_client(CommandHome, '/mavros/cmd/set_home')

        self.get_logger().info('Web Command Listener Ready & Waiting...')

    def state_cb(self, msg):
        self.state = msg

    # --- THE WEB COMMAND INTERCEPTOR ---
    def command_cb(self, msg):
        try:
            payload = json.loads(msg.data)
            cmd = payload.get('command', '')

            self.get_logger().info(f"Received Web Command: {cmd}")

            # Run the command in a background thread so ROS doesn't freeze!
            thread = threading.Thread(target=self.execute_command, args=(cmd,))
            thread.start()

        except Exception as e:
            self.get_logger().error(f"Failed to parse command: {e}")

    # --- THE COMMAND SWITCHBOARD ---
    def execute_command(self, cmd):
        if cmd == 'ARM':
            self.set_mode('GUIDED')
            self.set_arm(True)
        elif cmd == 'DISARM':
            self.set_arm(False)
        elif cmd == 'RTL':
            self.set_mode('RTL')
        elif cmd == 'TAKEOFF':
            self.smart_takeoff()

    # --- CORE FUNCTIONS ---
    def set_mode(self, custom_mode):
        self.get_logger().info(f'Switching Mode to {custom_mode}...')
        req = SetMode.Request(custom_mode=custom_mode)
        self.mode_cli.call_async(req)
        
        # Wait up to 5 seconds for the mode to change
        start = time.time()
        while self.state.mode != custom_mode and (time.time() - start) < 5.0:
            time.sleep(0.5)

    def set_arm(self, arm_state):
        state_str = "Arming" if arm_state else "Disarming"
        self.get_logger().info(f'{state_str} motors...')
        req = CommandBool.Request(value=arm_state)
        self.arm_cli.call_async(req)
        
        # Wait up to 5 seconds for the motors to spin up/down
        start = time.time()
        while self.state.armed != arm_state and (time.time() - start) < 5.0:
            time.sleep(0.5)

    def smart_takeoff(self):
        self.get_logger().info("Initiating Takeoff Sequence...")
        
        if not self.state.connected:
            self.get_logger().warn('Abort: Drone not connected to MAVROS yet!')
            return

        # 1. Auto-switch to GUIDED if needed
        if self.state.mode != 'GUIDED':
            self.set_mode('GUIDED')

        # 2. Auto-ARM if needed
        if not self.state.armed:
            self.set_arm(True)

        # 3. Takeoff!
        if self.state.armed and self.state.mode == 'GUIDED':
            self.get_logger().info('Launching to 20 meters!')
            tk_req = CommandTOL.Request(altitude=20.0) # Matched to 20m for the web dashboard default
            self.takeoff_cli.call_async(tk_req)
        else:
            self.get_logger().error('Takeoff failed: Could not arm or set GUIDED.')

def main(args=None):
    rclpy.init(args=args)
    node = DroneController()
    
    # rclpy.spin() keeps the script running forever, listening for your button clicks
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()