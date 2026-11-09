#!/bin/bash

SESSION_NAME="drone_swarm_session"
WINDOW_NAME="swarm"

tmux kill-session -t $SESSION_NAME 2>/dev/null

# Build the container and prepare the workspace once, before any pane starts
./run.sh --no-shell || exit 1

tmux new-session -d -s $SESSION_NAME -n $WINDOW_NAME

for i in {1..8}; do
    tmux split-window -v
    tmux select-layout tiled
done

echo "Opening a shell in the container in all panes..."

for i in {0..8}; do
    tmux send-keys -t "$SESSION_NAME:$WINDOW_NAME.$i" "docker exec -it ros2_gazebo_dev bash" C-m
done

sleep 4 

# --- PANE 0: Gazebo Simulator ---
tmux send-keys -t "$SESSION_NAME:$WINDOW_NAME.0" \
"source /opt/ros/humble/setup.bash && \
source /usr/share/gazebo/setup.sh && \
export GAZEBO_RESOURCE_PATH=\$GAZEBO_RESOURCE_PATH:/usr/share/gazebo-11:/ros2_ws/src/ardupilot_gazebo/worlds && \
export GAZEBO_MODEL_PATH=\$GAZEBO_MODEL_PATH:/ros2_ws/src/ardupilot_gazebo/models && \
export GAZEBO_PLUGIN_PATH=\$GAZEBO_PLUGIN_PATH:/ros2_ws/src/ardupilot_gazebo/build && \
gazebo --verbose /ros2_ws/src/ardupilot_gazebo/worlds/iris_arducopter_campus.world" C-m


# --- PANE 1: ArduPilot SITL ---
tmux send-keys -t "$SESSION_NAME:$WINDOW_NAME.1" \
"source /ros2_ws/install/setup.bash && \
cd /ros2_ws/src/ardupilot/ArduCopter && \
../Tools/autotest/sim_vehicle.py -v ArduCopter -f gazebo-iris --map --console --custom-location=44.435720,26.047583,0,0" C-m

# ../Tools/autotest/sim_vehicle.py -v ArduCopter -f gazebo-iris --map --console -l 44.434947172540795,26.046744063553334,0,0" C-m

# --- PANE 2: MAVROS Translator ---
tmux send-keys -t "$SESSION_NAME:$WINDOW_NAME.2" \
"source /ros2_ws/install/setup.bash && \
source /opt/ros/humble/setup.bash && \
ros2 run mavros mavros_node --ros-args -p fcu_url:=udp://127.0.0.1:14550@" C-m

# --- PANE 3: Drone control---

tmux send-keys -t "$SESSION_NAME:$WINDOW_NAME.3" \
"source /ros2_ws/install/setup.bash && \
source /opt/ros/humble/setup.bash && \
ros2 run swarm_demo drone_mission" C-m

# --- PANE 4: ROS2 Bridge Websocket ---
tmux send-keys -t "$SESSION_NAME:$WINDOW_NAME.4" \
"source /opt/ros/humble/setup.bash && \
ros2 run rosbridge_server rosbridge_websocket" C-m

# --- PANE 5: Web Interface Backend ---
tmux send-keys -t "$SESSION_NAME:$WINDOW_NAME.5" \
"python3 /app/backend/server.py" C-m


# --- PANE 6: Target Detector Node ---
tmux send-keys -t "$SESSION_NAME:$WINDOW_NAME.6" \
"source /ros2_ws/install/setup.bash && \
source /opt/ros/humble/setup.bash && \
ros2 run swarm_demo target_detector" C-m

# --- PANE 7: AI Mapping Node ---
tmux send-keys -t "$SESSION_NAME:$WINDOW_NAME.7" \
"source /ros2_ws/install/setup.bash && \
source /opt/ros/humble/setup.bash && \
ros2 run swarm_demo yolo_detector" C-m


# --- PANE 8: Zigzag Mission Node ---
tmux send-keys -t "$SESSION_NAME:$WINDOW_NAME.8" \
"source /ros2_ws/install/setup.bash && \
source /opt/ros/humble/setup.bash && \
ros2 run swarm_demo zigzag_mission" C-m

# ==========================================
# 7. ATTACH TO THE SESSION
# ==========================================
tmux attach-session -t $SESSION_NAME
