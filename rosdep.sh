# If you're having troubles running your build, run this script to ensure you have all dependencies
# This only works on debian based distributions of linux, if you have a different distro, you'll have to source them elsehow
# To run: Make sure you're in the navigator folder and run ./rosdep.sh

# !/bin/sh

apt-get install -y ros-foxy-ros-testing
apt-get install -y python3-psutil
apt-get install -y ros-foxy-qt-dotgraph
apt-get install -y ros-foxy-osrf-testing-tools-cpp
apt-get install -y ros-foxy-lanelet2-core
apt-get install -y ros-foxy-lanelet2-io
apt-get install -y ros-foxy-lanelet2-projection
apt-get install -y ros-foxy-lanelet2
apt-get install -y libgeographic-dev
apt-get install -y ros-foxy-apex-test-tools
apt-get install -y ros-foxy-raptor-dbw-msgs
apt-get install -y ros-foxy-ros2-socketcan
apt-get install -y ros-foxy-lgsvl-msgs
apt-get install -y libcgal-dev
apt-get install -y ros-foxy-point-cloud-msg-wrapper
apt-get install -y ros-foxy-acado-vendor
apt-get install -y ros-foxy-ament-cmake-google-benchmark
apt-get install -y ros-foxy-rviz2
apt-get install -y ros-foxy-osqp-vendor
apt-get install -y python3-tornado
apt-get install -y python3-twisted
apt-get install -y ros-foxy-rosauth
apt-get install -y libomp-dev
apt-get install -y libpcl-dev
apt-get install -y ros-foxy-lanelet2-traffic-rules
apt-get install -y ros-foxy-lanelet2-routing
apt-get install -y python3-matplotlib
apt-get install -y python3-scipy
apt-get install -y libboost-system-dev
apt-get install -y ros-foxy-automotive-platform-msgs
apt-get install -y ros-foxy-casadi-vendor
apt-get install -y libopenblas-dev
apt-get install -y libopencv-dev
apt-get install -y ros-foxy-tvm-vendor
apt-get install -y ros-foxy-pcl-conversions
apt-get install -y libyaml-cpp-dev
apt-get install -y ros-foxy-vision-opencv
apt-get install -y ros-foxy-cv-bridge
apt-get install -y python3-pil
apt-get install -y python3-bson
apt-get install -y ros-foxy-udp-driver
apt-get install -y ros-foxy-joy
apt-get install -y ros-foxy-joy-linux
apt-get install -y ros-foxy-rviz-common
apt-get install -y ros-foxy-rviz-default-plugins
apt-get install -y qtbase5-dev
apt-get install -y libqt5widgets5