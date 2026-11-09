#!/bin/bash
set -e

# Source the main ROS 2 installation
source /opt/ros/humble/setup.bash

if [ -f "/ros2_ws/install/setup.bash" ]; then
    source /ros2_ws/install/setup.bash
fi

# Execute the command passed into the container
exec "$@"




