
FROM osrf/ros:humble-desktop

ENV DEBIAN_FRONTEND=noninteractive

# Install Gazebo, ROS tools, and dependencies
RUN apt-get update && apt-get install -y \
    gazebo \
    ros-humble-gazebo-ros-pkgs \
    python3-colcon-common-extensions \
    nano git python3-pip python3-dev \
    python3-opencv python3-matplotlib python3-lxml python3-yaml \
    xterm ros-humble-mavros ros-humble-mavros-extras wget \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python

# Install MAVProxy and ArduPilot SITL dependencies
RUN pip3 install PyYAML mavproxy pexpect future pymavlink empy==3.3.4

# Gazebo development files (for the ArduPilot plugin), CycloneDDS and wxPython
RUN apt-get update && apt-get install -y \
    libgazebo-dev ros-humble-rmw-cyclonedds-cpp python3-wxgtk4.0 \
    && rm -rf /var/lib/apt/lists/*

# Detection stack: PyTorch (CPU build), YOLO and its helpers.
# NumPy must stay below 2 for the ROS cv_bridge package.
# The Ubuntu pip is too old for the resolver and crashes on these pins, so upgrade it first.
RUN pip3 install --upgrade pip \
    && pip3 install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip3 install --no-cache-dir "numpy<2" ultralytics ultralyticsplus

# Install GeographicLib datasets for MAVROS
RUN wget -O /tmp/install_geographiclib_datasets.sh https://raw.githubusercontent.com/mavlink/mavros/master/mavros/scripts/install_geographiclib_datasets.sh \
    && chmod +x /tmp/install_geographiclib_datasets.sh \
    && bash /tmp/install_geographiclib_datasets.sh

# Install rosbridge for web interface
RUN apt-get update && apt-get install -y ros-humble-rosbridge-suite

WORKDIR /ros2_ws

COPY ./entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
