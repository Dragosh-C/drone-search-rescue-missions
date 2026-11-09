from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='mavros',
            executable='mavros_node',
            name='mavros',
            parameters=[{
                # This is the UDP port ArduPilot SITL uses to talk to ROS
                'fcu_url': 'udp://127.0.0.1:14550@14550',
                'gcs_url': 'udp://@14555', # For QGroundControl to connect too
                'target_system_id': 1,
                'target_component_id': 1,
                'fcu_protocol': 'v2.0',
            }]
        )
    ])
