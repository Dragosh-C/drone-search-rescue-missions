#!/bin/bash

# Allow local Docker to connect to your host's X11 server for the GUI
xhost +local:root

docker-compose up -d --build

docker exec -it ros2_gazebo_dev bash