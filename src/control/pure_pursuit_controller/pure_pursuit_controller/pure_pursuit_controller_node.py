import math

import rclpy
import numpy as np

from numpy import typing as npt

from rclpy.node import Node

from std_msgs.msg import ColorRGBA, Header
from rosgraph_msgs.msg import Clock
from nav_msgs.msg import Path, Odometry
from geometry_msgs.msg import Pose, PoseStamped, Point, Vector3
from visualization_msgs.msg import Marker

from navigator_msgs.msg import VehicleControl, VehicleSpeed


class Constants:
    # Look ahead distance in meters
    LD: float = 3.0
    # Look forward gain in meters (gain in look ahead distance per m/s of speed)
    kf: float = 0.1
    # Wheel base (distance between front and rear wheels) in meter
    WHEEL_BASE: float = 3.5
    # Max throttle and acceleration
    MAX_THROTTLE = 0.6
    # Max speed in m/s
    MAX_SPEED: float = 1.5
    # Path adjustment gain
    PATH_ADJUSTMENT_GAIN: float = 0.5


class VehicleState:
    def __init__(self, l):
        self.l = l
        self.pose: Pose | None = None
        self.velocity: float | None = None

    def loaded(self) -> bool:
        return self.pose is not None and self.velocity is not None

    def calc_throttle_brake(self) -> tuple[float, float] | None:
        if not self.loaded():
            return

        # Our target speed is the max speed
        pid_error = Constants.MAX_SPEED - self.velocity
        if pid_error > 0:
            throttle = min(pid_error * 0.5, Constants.MAX_THROTTLE)
            brake = 0.0
        elif pid_error <= 0:
            brake = pid_error * Constants.MAX_THROTTLE * -1.0
            throttle = 0.0

        return throttle, brake

    def calc_steer(self, target: tuple[float, float]) -> float | None:
        if not self.loaded():
            return

        alpha = math.atan2(target[1], target[0])
        delta = math.atan2(
            2.0 * Constants.WHEEL_BASE * math.sin(alpha), self.lookahead_distance()
        )

        # Normalize the steering angle from [-pi, pi] to [-1, 1]
        return -delta / (math.pi / 2)

    def lookahead_distance(self) -> float:
        return Constants.kf * self.velocity + Constants.LD


class PursuitPath:
    def __init__(self, l, path: list[tuple[float, float]] = []):
        self.l = l
        self.path: npt.NDArray[np.float64] = np.asarray(path)
        self.prev_index: int | None = None

    def set_path(self, path: list[tuple[float, float]]) -> None:
        self.path = np.asarray(path)
        self.prev_index = None

    def _calc_nearest_index(self, vs: VehicleState) -> int:
        if len(self.path) == 0 or not vs.loaded():
            return

        min_dist = float("inf")
        min_index = 0
        for i, (x, y) in enumerate(self.path):
            dist = math.hypot(x, y)
            if dist < min_dist:
                min_dist = dist
                min_index = i

        return min_index

    def get_current_path(self) -> npt.NDArray[np.float64]:
        return np.copy(self.path[: self.prev_index])

    def calc_target_point(self, vs: VehicleState) -> tuple[float, float] | None:
        if len(self.path) == 0 or not vs.loaded():
            return

        if self.prev_index is None:
            self.prev_index = self._calc_nearest_index(vs)

        for i, (x, y) in enumerate(self.path[self.prev_index :]):
            dist = math.hypot(x, y)
            if dist > vs.lookahead_distance():
                self.prev_index = i
                return (x, y)


class PursePursuitController(Node):

    def __init__(self):
        super().__init__("pure_pursuit_controler")

        self.vehicle_state = VehicleState(l=self.get_logger())
        self.path = PursuitPath(l=self.get_logger())
        self.target_waypoint = None
        self.clock = Clock().clock

        self.route_subscriber = self.create_subscription(
            Path, "/planning/path", self.route_callback, 1
        )
        self.odometry_subscriber = self.create_subscription(
            Odometry, "/gnss/odometry", self.odometry_callback, 1
        )
        self.speed_subscriber = self.create_subscription(
            VehicleSpeed, "/speed", self.speed_callback, 1
        )
        self.clock_subscriber = self.create_subscription(
            Clock, "/clock", self.clock_callback, 1
        )

        self.command_publisher = self.create_publisher(
            VehicleControl, "/vehicle/control", 1
        )

        self.barrier_marker_pub = self.create_publisher(
            Marker, "/planning/barrier_marker", 1
        )
        self.lookahead_path_publisher = self.create_publisher(Path, "/ppc/path", 1)

        self.control_timer = self.create_timer(0.1, self.control_callback)
        self.visualize_path_timer = self.create_timer(0.1, self.visualize_path_callback)
        self.visualize_waypoint_timer = self.create_timer(
            0.1, self.visualize_waypoint_callback
        )

    def clock_callback(self, msg: Clock):
        self.clock = msg.clock

    def route_callback(self, msg: Path):
        path = [
            (pose_stamped.pose.position.x, pose_stamped.pose.position.y)
            for pose_stamped in msg.poses
        ]
        self.path.set_path(path)
        self.target_waypoint = self.path.calc_target_point(self.vehicle_state)

    def odometry_callback(self, msg: Odometry):
        self.vehicle_state.pose = msg.pose.pose

    def speed_callback(self, msg: VehicleSpeed):
        self.vehicle_state.velocity = msg.speed

    def control_callback(self):
        # If no target waypoint, do nothing.
        if not self.target_waypoint:
            return

        # Calculate throttle, brake, and steer
        throttle_brake = self.vehicle_state.calc_throttle_brake()
        steer = self.vehicle_state.calc_steer(self.target_waypoint)

        self.get_logger().info(f"Steer: {steer} Throttle/Brake: {throttle_brake}")

        # If vehicle state is not loaded, do nothing.
        if throttle_brake is None or steer is None:
            return

        # Set throttle, brake, and steer and publish.
        throttle, brake = throttle_brake
        control_msg = VehicleControl()
        control_msg.throttle = throttle
        control_msg.brake = brake
        control_msg.steer = steer
        self.get_logger().info(
            f"Steer: {control_msg.steer} Throttle: {throttle} Brake: {brake}"
        )
        self.command_publisher.publish(control_msg)

    def visualize_waypoint_callback(self):
        if self.target_waypoint is None:
            return

        relative_waypoint = 0.4 * np.asarray(self.target_waypoint)

        lookahead_dist = self.vehicle_state.lookahead_distance()
        radius_marker = Marker(
            header=Header(frame_id="base_link", stamp=self.clock),
            ns="lookahead",
            id=0,
            type=Marker.CYLINDER,
            action=Marker.ADD,
            scale=Vector3(x=lookahead_dist * 2, y=lookahead_dist * 2, z=0.2),
            color=ColorRGBA(a=0.3, g=1.0, b=1.0),
        )
        self.barrier_marker_pub.publish(radius_marker)

        arrow_marker = Marker(
            header=Header(frame_id="base_link", stamp=self.clock),
            ns="lookahead",
            id=1,
            type=Marker.ARROW,
            action=Marker.ADD,
            scale=Vector3(x=0.5, y=0.8, z=0.3),
            color=ColorRGBA(a=0.7, g=1.0, b=0.6),
            points=[Point(), Point(x=relative_waypoint[0], y=relative_waypoint[1])],
        )

        self.barrier_marker_pub.publish(arrow_marker)

    def visualize_path_callback(self):
        current_path = self.path.get_current_path()

        if len(current_path) == 0:
            return

        path_msg = Path()
        path_msg.header.frame_id = "base_link"
        path_msg.header.stamp = self.clock

        # Each RVIZ grid cell is 0.4m.
        path = np.copy(np.asarray(current_path)) * 0.4

        path_msg.poses = [
            PoseStamped(
                header=path_msg.header,
                pose=Pose(position=Point(x=x, y=y)),
            )
            for x, y in path
        ]

        self.lookahead_path_publisher.publish(path_msg)


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
