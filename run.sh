#!/bin/bash
# Build the container, prepare the ROS 2 workspace once, then open a shell.
#
#   ./run.sh              build, set up the workspace, open a shell
#   ./run.sh --no-shell   build and set up only (used by run_all.sh)

# Allow local Docker to connect to your host's X11 server for the GUI
xhost +local:root

docker-compose up -d --build || exit 1

# First run takes a long time (ArduPilot build). Later runs skip finished steps.
docker exec ros2_gazebo_dev bash /ros2_ws/setup_workspace.sh || exit 1

if [ "$1" != "--no-shell" ]; then
    docker exec -it ros2_gazebo_dev bash
fi
