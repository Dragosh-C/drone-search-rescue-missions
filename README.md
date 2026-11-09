# Drone Search for Rescue Missions

A drone search system for rescue missions in any area. The operator marks zones of interest on a web map and chooses what to look for: people, vehicles, or objects of a given color. The drone then flies a zigzag pattern over the selected zones, detects matching objects with onboard vision, saves evidence images, and reports each detection on the map.

The project includes a sample environment: a 3D mesh of a university campus, reconstructed with COLMAP from photographs and loaded into Gazebo. Any other environment can be used by providing its own Gazebo world.

The simulation uses ArduCopter flying in ArduPilot SITL, rendered in Gazebo 11, and controlled from ROS 2 Humble through MAVROS. A rosbridge WebSocket connects the ROS 2 nodes to the browser. The application is designed to run the same way on a real drone: replacing the Gazebo simulation with an ArduPilot-based vehicle should not require changes to the web interface or the mission nodes.

## Demo

[Watch the demo video](demo.webm) (5 min 13 s, 2560x1440, WebM).

## Components

- **Gazebo world and models** (`workspace/src/ardupilot_gazebo`): the sample campus world (a COLMAP reconstruction of the campus), and an Iris quadcopter with the ArduPilot Gazebo plugin.
- **ROS 2 package `swarm_demo`** (`workspace/src/swarm_demo`):
  - `drone_mission`: receives commands from the web interface (ARM, DISARM, TAKEOFF, RTL) and switches flight modes through MAVROS.
  - `zigzag_mission`: receives a rectangular zone from the web interface, generates a zigzag path at the chosen altitude and spacing, and publishes setpoints.
  - `target_detector`: finds objects by color using HSV thresholding (red/orange, blue and green).
  - `yolo_detector`: runs a YOLOv8 model trained on VisDrone aerial imagery to detect people and vehicles.
  - `evidence_logger`: saves a JPG of each detection, with a cooldown between saves (5 seconds by default).
- **Web ground control station** (`app/frontend/index.html`): a Leaflet map showing the drone position and detected targets, a telemetry panel (altitude, battery, flight mode), flight buttons, and controls for the scan zone and target types.
- **Backend** (`app/backend/server.py`): a small HTTP server that serves the dashboard and the captured evidence images on port 8000.

## Requirements

- Linux host with Docker and Docker Compose
- X11 display for the Gazebo GUI
- tmux (used by `run_all.sh`)
- Enough CPU and memory to run Gazebo, ArduPilot SITL and a YOLO model at the same time

All ROS 2, Gazebo, MAVROS and Python dependencies are installed inside the container. Nothing else needs to be installed on the host.

## Quick start

1. Build the container, set up the workspace and open a shell:

   ```bash
   ./run.sh
   ```

   The first run takes a long time: it builds the container, clones and builds ArduPilot (a large download), builds the Gazebo plugin and builds the ROS 2 packages. Later runs skip finished steps. See [Setup](#setup).

2. Start every component in its own tmux pane:

   ```bash
   ./run_all.sh
   ```

   This runs the same setup step, then creates a tmux session named `drone_swarm_session` with nine panes, opens a container shell in each one, and starts Gazebo, SITL, MAVROS, the mission nodes, the detectors, rosbridge and the web backend.

3. Open the dashboard at `http://localhost:8000`.

## Setup

`workspace/setup_workspace.sh` runs inside the container. It is called by `run.sh` and can be re-run safely. Each step is skipped when its output already exists:

1. Installs the system and Python packages not covered by the Dockerfile (Gazebo development files, CycloneDDS, wxPython, MAVProxy and related tools).
2. Clones ArduPilot `Copter-4.5` with its submodules into `workspace/src/ardupilot`.
3. Builds the ArduCopter SITL binary with `waf`.
4. Builds the Gazebo ArduPilot plugin from `workspace/src/ardupilot_gazebo`.
5. Builds the ROS 2 packages with `colcon` into `workspace/install`.

To run it by hand inside the container:

```bash
bash /ros2_ws/setup_workspace.sh
```

The ArduPilot clone and the build output are not tracked in Git (see `.gitignore`).

### Running the parts by hand

`run_all.sh` starts everything, but each component can also be started separately. Use one terminal per component.

| Terminal | Command |
| --- | --- |
| 1. Gazebo | `source /usr/share/gazebo/setup.sh` then set `GAZEBO_RESOURCE_PATH`, `GAZEBO_MODEL_PATH` and `GAZEBO_PLUGIN_PATH` to the `ardupilot_gazebo` folders, then `gazebo --verbose /ros2_ws/src/ardupilot_gazebo/worlds/iris_arducopter_campus.world` |
| 2. SITL | `cd /ros2_ws/src/ardupilot/ArduCopter && ../Tools/autotest/sim_vehicle.py -v ArduCopter -f gazebo-iris --map --console` |
| 3. MAVROS | `ros2 run mavros mavros_node --ros-args -p fcu_url:=udp://127.0.0.1:14550@` |
| 4. Mission | `ros2 run swarm_demo drone_mission` |
| 5. Zigzag scan | `ros2 run swarm_demo zigzag_mission` |
| 6. Rosbridge | `ros2 run rosbridge_server rosbridge_websocket` |
| 7. Web backend | `python3 /app/backend/server.py` |
| 8. Target detector | `ros2 run swarm_demo target_detector` |
| 9. YOLO detector | `ros2 run swarm_demo yolo_detector` |

Each ROS 2 terminal needs `source /opt/ros/humble/setup.bash` and `source /ros2_ws/install/setup.bash` first.

To start SITL at a specific GPS location, add `-l <lat>,<lon>,0,0` to the `sim_vehicle.py` command. `run_all.sh` uses `--custom-location=44.435720,26.047583,0,0`.

## Using the dashboard

- **Arm, Takeoff, RTL**: send the matching command to `drone_mission`. Takeoff sets GUIDED mode, arms the vehicle and then requests takeoff.
- **Target selection**: choose what to look for. The AI detector covers humans and vehicles. Color signatures cover red/orange, blue and green.
- **Scan zone**: set the rectangle, spacing and altitude. `zigzag_mission` builds the path from the drone's current position and flies it.
- **Detections**: each target appears on the map with its saved image.

Topics used between the browser and ROS 2:

| Topic | Type | Direction | Purpose |
| --- | --- | --- | --- |
| `/webapp/drone_command` | `std_msgs/String` (JSON) | browser to ROS | Flight commands |
| `/webapp/scan_zone` | `std_msgs/String` (JSON) | browser to ROS | Scan rectangle and parameters |

The browser connects to rosbridge at `ws://127.0.0.1:9090`.

## Evidence images

Detections are saved as JPG files to `/ros2_ws/captured_targets` inside the container, which is `./workspace/captured_targets` on the host. The folder is created at runtime and is not tracked in Git. The backend serves the images to the dashboard.

## Camera stream (optional)

To add a camera to the Gazebo gimbal model, edit the model file in the container:

```bash
nano /usr/share/gazebo-11/models/gimbal_small_2d/model.sdf
```

Add the following sensor to the model:

```xml
<sensor name="camera" type="camera">
  <pose>0 0 0 -1.57 -1.57 0</pose>
  <camera>
    <horizontal_fov>2.0</horizontal_fov>
    <image>
      <width>640</width>
      <height>480</height>
    </image>
    <clip>
      <near>0.05</near>
      <far>15000</far>
    </clip>
  </camera>
  <always_on>1</always_on>
  <update_rate>10</update_rate>
  <visualize>1</visualize>
  <plugin name="camera_controller" filename="libgazebo_ros_camera.so">
    <ros>
      <namespace>/uav1</namespace>
      <remapping>~/image_raw:=camera/image_raw</remapping>
    </ros>
    <camera_name>camera</camera_name>
    <frame_name>camera_link</frame_name>
  </plugin>
</sensor>
```

View the camera feed with:

```bash
ros2 run rqt_image_view rqt_image_view
```

## Useful commands

Arm the vehicle and take off to 10 m without the dashboard:

```bash
ros2 service call /mavros/cmd/set_home mavros_msgs/srv/CommandHome "{current_gps: true}"
ros2 service call /mavros/cmd/arming mavros_msgs/srv/CommandBool "{value: true}"
ros2 service call /mavros/cmd/takeoff mavros_msgs/srv/CommandTOL "{altitude: 10.0}"
```

## Project layout

```
.
├── app/
│   ├── backend/server.py        HTTP server for the dashboard and evidence images
│   └── frontend/index.html      Ground control station
├── workspace/                   Mounted as /ros2_ws in the container
│   ├── src/                     Mounted as /ros2_ws/src
│   │   ├── ardupilot_gazebo/    Gazebo plugin source, worlds and models
│   │   └── swarm_demo/          ROS 2 package with the mission and detection nodes
│   └── setup_workspace.sh       One-time workspace setup (run by run.sh)
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── run.sh                       Build the container and open a shell
└── run_all.sh                   Start all components in tmux
```

## Credits

- [ArduPilot](https://github.com/ArduPilot/ardupilot) and [ardupilot_gazebo](https://github.com/khancyr/ardupilot_gazebo)
- [MAVROS](https://github.com/mavlink/mavros) and [rosbridge_suite](https://github.com/RobotWebTools/rosbridge_suite)
- [Ultralytics](https://github.com/ultralytics/ultralytics) and the [VisDrone-trained YOLOv8 model](https://huggingface.co/mshamrai/yolov8s-visdrone)
- [Leaflet](https://leafletjs.com/)
- [COLMAP](https://colmap.github.io/) for the campus reconstruction

## License

MIT. See `LICENSE`.
