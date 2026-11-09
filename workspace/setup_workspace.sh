#!/bin/bash
# One-time setup of the ROS 2 workspace inside the ros2_gazebo_dev container.
# Run from the host by run.sh, or inside the container as:
#   bash /ros2_ws/setup_workspace.sh
#
# Safe to re-run: each step is skipped when its output already exists.
# The ArduPilot build takes a long time on the first run.

set -e

WS=/ros2_ws
SRC=$WS/src

log() { echo; echo "[setup] $*"; }

# ROS must be sourced before importing its Python packages (cv_bridge)
source /opt/ros/humble/setup.bash

# 1. Dependencies come from the Dockerfile. Fail early if the image is outdated.
if ! python3 -c "import torch, ultralyticsplus, cv_bridge" 2>/dev/null; then
    echo "Python or ROS packages are missing from the image." >&2
    echo "Rebuild it with: docker-compose up -d --build" >&2
    exit 1
fi

# 2. ArduPilot source (Copter-4.5), cloned into the mounted workspace
if [ ! -d "$SRC/ardupilot/.git" ]; then
    log "Cloning ArduPilot (Copter-4.5)"
    git clone https://github.com/ArduPilot/ardupilot.git "$SRC/ardupilot"
    git -C "$SRC/ardupilot" checkout Copter-4.5
    git -C "$SRC/ardupilot" submodule update --init --recursive
fi

# 3. ArduCopter SITL binary
if [ ! -x "$SRC/ardupilot/build/sitl/bin/arducopter" ]; then
    log "Building ArduCopter SITL (this takes a while)"
    cd "$SRC/ardupilot"
    ./waf configure --board sitl
    ./waf copter
fi

# 4. Gazebo plugin for ArduPilot (source is in the repo)
if [ ! -f "$SRC/ardupilot_gazebo/build/libArduPilotPlugin.so" ]; then
    log "Building the Gazebo ArduPilot plugin"
    mkdir -p "$SRC/ardupilot_gazebo/build"
    cd "$SRC/ardupilot_gazebo/build"
    cmake ..
    make -j"$(nproc)"
    make install
fi

# Environment variables for interactive shells
BASHRC_LINES=(
    'export GAZEBO_MODEL_PATH=/ros2_ws/src/ardupilot_gazebo/models:${GAZEBO_MODEL_PATH}'
    'export GAZEBO_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/usr/local/lib:${GAZEBO_PLUGIN_PATH}'
)
for line in "${BASHRC_LINES[@]}"; do
    grep -qxF "$line" ~/.bashrc 2>/dev/null || echo "$line" >> ~/.bashrc
done

# 5. ROS 2 packages (swarm_demo)
if [ ! -f "$WS/install/setup.bash" ]; then
    log "Building ROS 2 packages with colcon"
    cd "$WS"
    colcon build --symlink-install --packages-ignore ardupilot_sitl
fi

log "Workspace is ready"
