import math

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Path, Odometry
from geometry_msgs.msg import Pose, PoseStamped, Point

from navigator_msgs.msg import VehicleControl, VehicleSpeed


class Constants:
    LD: float = 6.0  # lookahead distance in meters
    kf: float = 0.1  # look forward gain in meters

def calculate_throttle_brake(current_speed, target_speed):

    delta = 0.6 # Controls max throttle and acceleration will be
    maxSpeed = 1.5 # MAX SPEED ~ 10mph

    # Max speed is set to 1.5
    if(target_speed > maxSpeed):
        target_speed = maxSpeed

    # PID logic sources from RTP node
    pid_error = target_speed - current_speed

    if pid_error > 0:
        throttle = min(pid_error * 0.5, delta)
        brake = 0.0
    elif pid_error <= 0:
        brake = pid_error * delta * -1.0
        throttle = 0.0

    return throttle, brake

class VehicleState:
    def __init__(self):
        self.pose: Pose | None = None
        self.velocity: float | None = None

    def loaded(self) -> bool:
        return self.pose is not None and self.velocity is not None

    def lookahead_distance(self) -> float:
        return Constants.kf * self.velocity + Constants.LD

    def _calc_distance(self, x: float, y: float) -> float:
        return math.hypot(
            x - self.pose.position.x,
            y - self.pose.position.y,
        )


class PursuitPath:
    def __init__(self, cx: list[float] = [], cy: list[float] = []):
        self.cx = cx
        self.cy = cy
        self.prev_index: int | None = None

    def _calc_nearest_index(self, vs: VehicleState) -> int:
        if len(self.cx) == 0 or len(self.cy) == 0 or not vs.loaded():
            return

        min_dist = float("inf")
        min_index = 0
        for i in range(len(self.cx)):
            dist = vs._calc_distance(self.cx[i], self.cy[i])
            if dist < min_dist:
                min_dist = dist
                min_index = i

        return min_index 

    def calc_target_point(self, vs: VehicleState) -> tuple[float, float] | None:
        if len(self.cx) == 0 or len(self.cy) == 0 or not vs.loaded():
            return

        if self.prev_index is None:
            self.prev_index = self._calc_nearest_index(vs)

        for i in range(self.prev_index, len(self.cx)):
            dist = vs._calc_distance(self.cx[i], self.cy[i])
            if dist > vs.lookahead_distance():
                self.prev_index = i
                return [self.cx[i], self.cy[i]]

class PursePursuitController(Node):

    def __init__(self):
        super().__init__("pure_pursuit_controler")

        self.vehicle_state = VehicleState()
        self.path = PursuitPath()
        self.target_waypoint = None

        self.first_route = None

        self.route_subscriber = self.create_subscription(
            Path, "/planning/route", self.route_callback, 1
        )
        self.odometry_subscriber = self.create_subscription(
            Odometry, "/gnss/odometry", self.odometry_callback, 1
        )
        self.speed_subscriber = self.create_subscription(
            VehicleSpeed, "/speed", self.speed_callback, 1
        )

        self.timer = self.create_timer(0.5, self.timer_callback)

    def route_callback(self, msg: Path):
        # Only use the first route for now. TODO: how will routes be updated in the future?
        if self.first_route is None:
            self.first_route = msg
            route = [
                [pose_stamped.pose.position.x, pose_stamped.pose.position.y]
                for pose_stamped in msg.poses
            ]
            self.get_logger().info(f"Route: {route}\n")
            self.path.cx = [pose_stamped.pose.position.x for pose_stamped in msg.poses]
            self.path.cy = [pose_stamped.pose.position.y for pose_stamped in msg.poses]

    def odometry_callback(self, msg: Odometry):
        self.vehicle_state.pose = msg.pose.pose

    def speed_callback(self, msg: VehicleSpeed):
        self.vehicle_state.velocity = msg.speed

    def timer_callback(self):
        self.target_waypoint = self.path.calc_target_point(self.vehicle_state)
        if self.target_waypoint is not None:
            self.get_logger().info(f"Target waypoint: {self.target_waypoint}")


def main(args=None):
    rclpy.init(args=args)

    minimal_publisher = PursePursuitController()

    rclpy.spin(minimal_publisher)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    minimal_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
