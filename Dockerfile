ARG CARLA_WS=/home/share/carla

# multi-stage for caching
FROM ros:foxy

# clone overlay source
RUN . /opt/ros/$ROS_DISTRO/setup.sh && \
    apt-get update && \
    apt install -y git cmake python3-pip && \
    pip3 install -U colcon-common-extensions vcstool

# This variable tells future scripts that user input isn't available during the Docker build.
ENV DEBIAN_FRONTEND noninteractive

COPY ./docker/install-dependencies.sh ./opt/docker_ws/install-dependencies.sh
# RUN apt update && apt install -y software-properties-common
RUN /opt/docker_ws/install-dependencies.sh && rm -rf /var/lib/apt/lists/*

COPY ./docker ./opt/docker_ws

# Copy and build our modified version of CycloneDDS, important ROS middleware
COPY ./src/external/cyclonedds /opt/cyclone_ws/cyclonedds
COPY ./src/external/rmw_cyclonedds /opt/cyclone_ws/rmw_cyclonedds
WORKDIR /opt/cyclone_ws
RUN . /opt/ros/foxy/setup.sh && colcon build

RUN apt update && echo "net.core.rmem_max=8388608\nnet.core.rmem_default=8388608\n" | sudo tee /etc/sysctl.d/60-cyclonedds.conf

ENV ROS_VERSION 2

WORKDIR /navigator
COPY ./docker/entrypoint.sh /opt/entrypoint.sh
ENTRYPOINT [ "/opt/entrypoint.sh" ]