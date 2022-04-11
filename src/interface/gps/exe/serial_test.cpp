#include <iostream>
#include "gps/GPSNode.hpp"

int main(int argc, char ** argv) {
  if(argc < 2) {
    std::cout << "Please provide a device name" << std::endl;
    return 1;
  }

  std::string device(argv[1]);

  navigator::gps::gps_params params = {
				       device,
  };

  rclcpp::init(0, nullptr);
  rclcpp::spin(std::make_shared<navigator::gps::GPSNode>(params));
  rclcpp::shutdown();
}
