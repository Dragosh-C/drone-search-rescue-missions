
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
RUN pip3 install PyYAML mavproxy pexpect future pymavlink

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
