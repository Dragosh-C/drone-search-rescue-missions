import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    pkg_dir = get_package_share_directory('swarm_demo')
    urdf_file = os.path.join(pkg_dir, 'urdf', 'simple_drone.urdf')

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(
            get_package_share_directory('gazebo_ros'), 'launch', 'gazebo.launch.py')]),
    )

    ld = LaunchDescription([gazebo])

    for i in range(1, 4):
        y_pos = str((i - 2) * 1.5)
        spawn_node = Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            arguments=[
                '-entity', f'drone{i}', '-file', urdf_file,
                '-x', '0.0', '-y', y_pos, '-z', '1.0',
                '-robot_namespace', f'/drone{i}'
            ],
            output='screen'
        )
        ld.add_action(spawn_node)

    return ld
