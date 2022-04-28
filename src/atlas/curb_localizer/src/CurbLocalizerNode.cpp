/*
 * Package:   curb_localizer
 * Filename:  CurbLocalizerNode.cpp
 * Author:    Egan Johnson
 * Email:     egan.johnson@utdallas.edu
 * Copyright: 2022, Voltron UTD
 * License:   MIT License
 */

#include "curb_localizer/CurbLocalizerNode.hpp"

#include <pcl_conversions/pcl_conversions.h>
#include <pcl/conversions.h>
#include <pcl/common/transforms.h>

using namespace navigator::curb_localizer;

CurbLocalizerNode::CurbLocalizerNode() : Node("curb_localizer"){
    this->declare_parameter<std::string>("map_file_path", "data/maps/grand_loop/grand_loop.xodr");
    this->map_file_path = this->get_parameter("map_file_path").as_string();
    this->map = opendrive::load_map(this->map_file_path)->map;

    // curb detector class also outputs all candidate pts if necessary

    this->left_curb_points_sub = this->create_subscription<sensor_msgs::msg::PointCloud2>("curb_points/left",
        rclcpp::QoS(rclcpp::KeepLast(1)),
        std::bind(&CurbLocalizerNode::left_curb_points_callback, this, std::placeholders::_1));
    this->right_curb_points_sub = this->create_subscription<sensor_msgs::msg::PointCloud2>("curb_points/right",
        rclcpp::QoS(rclcpp::KeepLast(1)),
        std::bind(&CurbLocalizerNode::right_curb_points_callback, this, std::placeholders::_1));
    this->odom_in_sub = this->create_subscription<nav_msgs::msg::Odometry>("/sensors/gnss/odom",
        rclcpp::QoS(rclcpp::KeepLast(1)),
        std::bind(&CurbLocalizerNode::odom_in_callback, this, std::placeholders::_1));
    this->odom_out_pub = this->create_publisher<nav_msgs::msg::Odometry>("odom_out",
        rclcpp::QoS(rclcpp::KeepLast(1)));
}

void convert_to_pcl(const sensor_msgs::msg::PointCloud2::SharedPtr msg, pcl::PointCloud<pcl::PointXYZ> &out_cloud) {
    pcl::PCLPointCloud2 pcl_cloud;
    pcl_conversions::toPCL(*msg, pcl_cloud);
    pcl::fromPCLPointCloud2(pcl_cloud, out_cloud);
}

void CurbLocalizerNode::left_curb_points_callback(const sensor_msgs::msg::PointCloud2::SharedPtr msg){
    convert_to_pcl(msg, this->left_curb_points);
}

void CurbLocalizerNode::right_curb_points_callback(const sensor_msgs::msg::PointCloud2::SharedPtr msg){
    convert_to_pcl(msg, this->right_curb_points);
}

void CurbLocalizerNode::odom_in_callback(const nav_msgs::msg::Odometry::SharedPtr msg){
    this->odom_in = msg;
    this->current_position_x = msg->pose.pose.position.x;
    this->current_position_y = msg->pose.pose.position.y;
    publish_odom();
}

void CurbLocalizerNode::publish_odom() {
    
    std::vector<std::vector<std::string>> path_roads = {
        {"81", "1"},
		{"953", "1"}
    };

    // get lane from current position
    std::shared_ptr<odr::Lane> current_lane = navigator::opendrive::get_lane_from_xy(map, current_position_x, current_position_y);

    // get road from current lane
    std::string road_id = current_lane->road.lock()->id;
    std::shared_ptr<odr::Road> current_road = map->roads[road_id];

    // get current s value
    double s = current_road->ref_line->match(current_position_x, current_position_y);    

    std::shared_ptr<odr::Road> target_road;
    std::shared_ptr<odr::LaneSection> target_lanesection;

    // if adding 20m to current s goes out of road bounds, then next road has curb

    if ((current_lane <= 0 && (s + 20) > current_road->length) || (current_lane > 0 && (s - 20) < 0.0)) {

        double next_s = abs(current_road->length - (s + 20));

        int i = 0;
        for (auto &stringVector : path_roads) {
            if (stringVector[0] == road_id && i != path_roads.size() - 1) {
                target_road = map->roads[path_roads[i + 1][0]];
                if (path_roads[i + 1][1] == "-1" || path_roads[i + 1][1] == "-2" || path_roads[i + 1][1] == "-3")  {
                    target_lanesection = target_road->get_lanesection(next_s);
                } else {
                    target_lanesection = target_road->get_lanesection(target_road->length - next_s);
                }
            }
            i++;
        }

    } else {
        target_road = current_road;
        target_lanesection = current_road->get_lanesection(s);
    }

    // iterate road lanes and find both curb lanes
    std::shared_ptr<odr::Lane> right_curb;
    std::shared_ptr<odr::Lane> left_curb;

    for (auto lane : target_lanesection->get_lanes()) {
        if (lane->type == "shoulder" && lane->id <= 0) {
            right_curb = lane;
        } else if (lane->type == "shoulder" && lane->id > 0) {
            left_curb = lane;
        }
    }

    // // get centerline for those lanes
    odr::Line3D right_curb_line = navigator::opendrive::get_centerline_as_xy(*right_curb, target_lanesection->s0, target_lanesection->get_end(), 0.25, false);
    odr::Line3D left_curb_line = navigator::opendrive::get_centerline_as_xy(*left_curb, target_lanesection->s0, target_lanesection->get_end(), 0.25, true);


    odom_out_pub->publish(*odom_out);
}

/**
 * @brief Translates the given point cloud to the given pose.
 *  (car reference --> map reference)
 * @param in_cloud 
 * @param odom 
 * @param out_cloud 
 */
void transform_points_to_odom(const pcl::PointCloud<pcl::PointXYZ> &in_cloud,
    const nav_msgs::msg::Odometry &odom,
    pcl::PointCloud<pcl::PointXYZ> &out_cloud) {

    Eigen::Affine3d odom_pose;
    odom_pose.rotate(Eigen::Quaterniond(odom.pose.pose.orientation.w,
        odom.pose.pose.orientation.x,
        odom.pose.pose.orientation.y,
        odom.pose.pose.orientation.z));

    odom_pose.translate(Eigen::Vector3d(odom.pose.pose.position.x,
        odom.pose.pose.position.y,
        odom.pose.pose.position.z));

    pcl::transformPointCloud(in_cloud, out_cloud, odom_pose);
}

/**
 * Algorithm:
 *  1. Start with GPS estimate of current position 
 *  2. Find left, right curb linestrings
 *      a. Find current lane
 *      b. Find current road
 *      c. ????
 *          i. Behavior near intersections/end of road warrents
 *              a few extra ??
 *      d. get descriptions of the curb
 *      e. a lot of parsing?
 *      f. linestring
 *      (may be able to assume lane boundary is curb since we are
 *      in the rightmost lane. Need ability to get next road for full curb)
 *  3. For each point in the cloud, find the minumum translation
 *      vector that will move the point to the curb linestring
 *  4. The odometry translation is the average point translation
 *  5. The confidence of the translation is some measure of how
 *    consistent the translation vector is- vectors pointing in 
 *      different directions are more likely to be wrong. 
 *      Try confidence 
 *          C = ||sum(displacement vectors)|| / sum(||displacement vectors||),
 *      or maybe ||sum_vec||^2 / sum(||displacement vectors||^2)
 * 
 * 
 */