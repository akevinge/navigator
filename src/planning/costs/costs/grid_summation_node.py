'''
Package: grids
   File: grid_summation_node.py
 Author: Will Heitman (w at heit dot mn)

Subscribes to cost maps, calculates their weighted sum, and
publishes the result as a finished cost map.
'''

import rclpy
import numpy as np
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
import time
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

# Message definitions
from navigator_msgs.msg import CarlaSpeedometer
from diagnostic_msgs.msg import DiagnosticStatus
from nav_msgs.msg import OccupancyGrid, Path
from navigator_msgs.msg import Egma
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import Float32
from tf2_ros import LookupException, ExtrapolationException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
from ros2_numpy.geometry import quat_to_numpy, numpy_to_quat
from tf_transformations import quaternion_multiply, euler_from_quaternion
from ros2_numpy.occupancy_grid import occupancygrid_to_numpy, numpy_to_occupancy_grid
# to do image rotations/shifts for fast forwarding occupancy grids
from scipy import ndimage

from skimage.morphology import erosion

import matplotlib.pyplot as plt

STALENESS_TOLERANCE = 0.25  # seconds. Grids older than this will be ignored.

CURRENT_OCCUPANCY_SCALE = 1.0 # 0.75
FUTURE_OCCUPANCY_SCALE = 1.0 #3.0
DRIVABLE_GRID_SCALE = 1.0 #0.75
ROUTE_DISTANCE_GRID_SCALE = 1.0
JUNCTION_GRID_SCALE = 1.0


class GridSummationNode(Node):

    def __init__(self):
        """Subscribe to the desired cost maps

        - Drivable surface  (~5 Hz)
        - Route distance
        - Current occupancy (~8 Hz)

        """
        super().__init__('grid_summation_node')

        # Subscriptions and publishers
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.current_occupancy_sub = self.create_subscription(
            OccupancyGrid, '/grid/occupancy/current', self.currentOccupancyCb, 1)
        self.current_occupancy_grid = None

        self.future_occupancy_sub = self.create_subscription(
            OccupancyGrid, '/grid/predictions_combined', self.futureOccupancyCb, 1)
        self.future_occupancy_grid = None

        self.drivable_grid_sub = self.create_subscription(
            OccupancyGrid, '/grid/drivable', self.drivableGridCb, 1)
        self.drivable_grid = None

        self.junction_grid_sub = self.create_subscription(
            OccupancyGrid, '/grid/stateful_junction', self.junctionGridCb, 1)
        self.junction_grid = None

        self.route_dist_grid_sub = self.create_subscription(
            OccupancyGrid, '/grid/route_distance', self.routeDistGridCb, 1)
        self.route_dist_grid = None

        self.junction_occupancy_pub = self.create_publisher(
            OccupancyGrid, '/grid/junction_occupancy', 1)

        self.speed_sub = self.create_subscription(
            CarlaSpeedometer, '/carla/hero/speedometer', self.speedometerCb, 1)

        self.steering_cost_pub = self.create_publisher(
            OccupancyGrid, '/grid/steering_cost', 1)

        self.speed_cost_pub = self.create_publisher(
            OccupancyGrid, '/grid/speed_cost', 1)

        self.combined_egma_pub = self.create_publisher(
            Egma, '/egma/cost', 1)

        self.status_pub = self.create_publisher(
            DiagnosticStatus, '/node_status', 1)
        self.status = DiagnosticStatus()

        self.combine_timer = self.create_timer(0.05, self.createCostMap, callback_group=MutuallyExclusiveCallbackGroup())

        self.clock_sub = self.create_subscription(
            Clock, '/clock', self.clockCb, 1)

        self.clock = Clock()

        self.speed = 0.0
        self.ego_has_stopped = False
        self.last_stop_time = time.time()

    def speedometerCb(self, msg: CarlaSpeedometer):
        self.speed = msg.speed

        # seconds. If the ego has stopped less than ten seconds ago, we still say that the ego has stopped
        STOP_COOLDOWN = 5.0

        if time.time() - self.last_stop_time < STOP_COOLDOWN:
            self.ego_has_stopped = True
        elif self.speed < 0.1:
            self.last_stop_time = time.time()
            self.ego_has_stopped = True
        else:
            self.ego_has_stopped = False
            print("Ego has NOT stopped")

    def clockCb(self, msg: Clock):
        self.clock = msg

    # Make sure we're only keeping the newest grid messages
    def currentOccupancyCb(self, msg: OccupancyGrid):
        if self.current_occupancy_grid is None or msg.header.stamp.sec + msg.header.stamp.nanosec*1e-9 > self.current_occupancy_grid.header.stamp.sec + self.current_occupancy_grid.header.stamp.nanosec*1e-9:
            self.current_occupancy_grid = msg

    def futureOccupancyCb(self, msg: OccupancyGrid):
        if self.future_occupancy_grid is None or msg.header.stamp.sec + msg.header.stamp.nanosec*1e-9 > self.future_occupancy_grid.header.stamp.sec + self.future_occupancy_grid.header.stamp.nanosec*1e-9:
            self.future_occupancy_grid = msg

    def drivableGridCb(self, msg: OccupancyGrid):
        if self.drivable_grid is None or msg.header.stamp.sec + msg.header.stamp.nanosec*1e-9 > self.drivable_grid.header.stamp.sec + self.drivable_grid.header.stamp.nanosec*1e-9:
            self.drivable_grid = msg

    def junctionGridCb(self, msg: OccupancyGrid):
        if self.junction_grid is None or msg.header.stamp.sec + msg.header.stamp.nanosec*1e-9 > self.junction_grid.header.stamp.sec + self.junction_grid.header.stamp.nanosec*1e-9:
            self.junction_grid = msg

    def routeDistGridCb(self, msg: OccupancyGrid):
        if self.route_dist_grid is None or msg.header.stamp.sec + msg.header.stamp.nanosec*1e-9 > self.route_dist_grid.header.stamp.sec + self.route_dist_grid.header.stamp.nanosec*1e-9:
            self.route_dist_grid = msg

    def checkForStaleness(self, grid: OccupancyGrid): #, status: DiagnosticStatus):
        stamp = grid.header.stamp
        stamp_in_seconds = stamp.sec + stamp.nanosec*1e-9
        current_time_in_seconds = self.clock.clock.sec + self.clock.clock.nanosec*1e-9
        stale = current_time_in_seconds - stamp_in_seconds > STALENESS_TOLERANCE
        if stale:
        #     self.get_logger().info("staleness %1.2f" % (current_time_in_seconds - stamp_in_seconds))
            # if status.level == DiagnosticStatus.OK:
            #     status.level = DiagnosticStatus.WARN
            #     status.message = "Current occupancy was stale."
            # else:
            #     status.level = DiagnosticStatus.ERROR
            #     status.message = "More than one layer was stale!"
            return current_time_in_seconds - stamp_in_seconds
        else:
            return 0

    # TODO: Eventually we would like to avoid any fastforwarding by having satisfactory publishing frequencies
    def fastforward(self, grid: OccupancyGrid):
        if grid is None:
            return grid
        
        # convert the grid to numpy array, we'll treat it as an image
        grid_img = occupancygrid_to_numpy(grid)
        old_dim = grid_img.shape[0]
        grid_res = grid.info.resolution

        if old_dim == 128:  # TODO: migrate static occupancy map to same size as others
            grid_img = self.resizeOccupancyGrid(grid_img)
            old_dim = grid_img.shape[0]
            grid_res = 0.4 # should avoid hard coding this

        # find that transform between base_link frames from when the message was made until now
        t = self.tf_buffer.lookup_transform_full(
            target_frame='base_link',
            target_time=rclpy.time.Time(),  # this requests the most recent time available, self.clock.clock might ask for a time more recent that we have data for...
            source_frame='base_link',
            source_time=grid.header.stamp,
            fixed_frame='map',
            timeout=rclpy.duration.Duration(seconds=5.0))

        #self.get_logger().info("x: %1.2f, y: %1.2f, z: %1.2f" % (t.transform.translation.x,t.transform.translation.y,t.transform.translation.z))
        #self.get_logger().info("%1.2f x: %1.2f, y: %1.2f, z: %1.2f" % (grid_res,t.transform.translation.x/grid_res,t.transform.translation.y/grid_res,t.transform.translation.z/grid_res))
        #grid.info.orgin.orientation = numpy_to_quat(quaternion_multiply( quat_to_numpy(t.transform.rotation), quat_to_numpy(grid.info.origin.orientation)))
        roll, pitch, yaw = euler_from_quaternion(quat_to_numpy(t.transform.rotation))

        #pad the image to make the car the center of the occupancy grid image
        #grid_img = np.block( [ [np.zeros((151,25)), grid_img, np.zeros((151,25))] , [np.zeros((50,201))] ] )
        #old_dim = grid_img.shape[0]

        # x = grid.info.origin.position.x*np.cos(-yaw) - grid.info.origin.position.y*np.sin(-yaw) + t.transform.translation.x
        # y = grid.info.origin.position.x*np.sin(-yaw) + grid.info.origin.position.y*np.cos(-yaw) + t.transform.translation.y
        # use 10 here because it is the distance from the center of the occupancy grid to the vehicle
        x = t.transform.translation.x + (10.0-10.0*np.cos(-yaw))
        y = t.transform.translation.y - 10.0*np.sin(-yaw)
        
        shift = [y/grid_res, x/grid_res]
        #shift = [t.transform.translation.y/grid_res,t.transform.translation.x/grid_res]
        #self.get_logger().info("tranform: rpy: [%1.2f,%1.2f,%1.2f trans: [%1.2f,%1.2f]" % (np.degrees(roll),np.degrees(pitch),np.degrees(yaw),shift[0],shift[1]))

        #grid_img = ndimage.shift(grid_img,shift)
        grid_img = ndimage.rotate(grid_img, np.degrees(-yaw), reshape=True)
        new_dim = grid_img.shape[0]
        diff = int((new_dim-old_dim)/2)
        grid_img = ndimage.shift(grid_img,shift)
        grid_img = grid_img[diff:new_dim-diff,diff:new_dim-diff]
        #grid_img = grid_img[0:151,25:176]


        # sometimes grid_img emerges with 152 pixels..
        if grid_img.shape[0] != 151:
            #self.get_logger().info("grid size was %i x %i" % grid_img.shape)
            grid_img = ndimage.zoom(grid_img, 151.0/float(grid_img.shape[0]))
            #self.get_logger().info("grid size became %i x %i" % grid_img.shape)

        grid_out = OccupancyGrid()
        grid_out.info.map_load_time = self.clock.clock
        grid_out.info.resolution = 0.4 # should avoid hard coding this
        grid_out.info.width = grid_img.shape[0]
        grid_out.info.height = grid_img.shape[1]
        grid_out.info.origin.position.x = -20.0 # should avoid hard coding this
        grid_out.info.origin.position.y = -30.0 # should avoid hard coding this
        grid_out.header.stamp = self.clock.clock
        grid_out.header.frame_id = 'base_link'
        grid_out.data = grid_img.astype(np.int8).flatten().tolist()

        return grid_out

    def getWeightedArray(self, msg: OccupancyGrid, scale: float) -> np.ndarray:
        """Converts the OccupancyGrid message into a numpy array, then multiplies it by scale

        Args:
            msg (OccupancyGrid)
            scale (float)

        Returns:
            np.ndarray: Weighted ndarray
        """
        arr = np.asarray(msg.data, dtype=np.float16).reshape(
            msg.info.height, msg.info.width)

        arr *= scale

        return arr

    def resizeOccupancyGrid(self, original: np.ndarray) -> np.ndarray:
        # This is a temporary measure until our current occ. grid's params
        # match the rest of our stack. Basically, due to the difference in cell size,
        # 1 out of 6 cells in the array needs to be deleted.

        downsampled = np.delete(original, np.arange(0, 128, 6), axis=0)
        downsampled = np.delete(downsampled, np.arange(
            0, 128, 6), axis=1)  # 106x106 result

        # trim the bottom columns (behind the car)
        downsampled = downsampled[:, 3:]

        background = np.zeros((151, 151))

        background[22:128, 0:103] = downsampled
        return background  # Correct scale

    def createCostMap(self):
        # self.get_logger().info('Composing aggregate costmap...')
        steering_cost = np.zeros((151, 151))
        speed_cost = np.zeros((151, 151))

        # Calculate the weighted cost map layers
        grids = [('occupancy', self.current_occupancy_grid, CURRENT_OCCUPANCY_SCALE),
                 #('future_occupancy', self.future_occupancy_grid, FUTURE_OCCUPANCY_SCALE),
                 ('drivable', self.drivable_grid, DRIVABLE_GRID_SCALE),
                 ('route_dist', self.route_dist_grid, ROUTE_DISTANCE_GRID_SCALE)] #,
                 # temporarily removing the junction from the speed calc...
                 #('junction', self.junction_grid, JUNCTION_GRID_SCALE)] 
        
        try:
            for grid_name, grid, scale in grids:
                if grid is None or len(grid.data) == 0:
                    # self.get_logger().warn('Costmap [%s] is empty.' % grid_name)
                    return
                
                stale = self.checkForStaleness(grid)
                if stale > 0:
                    #self.get_logger().warn('Costmap [%s] is stale (%1.2f sec).' % (grid_name,stale))
                    ff_grid = self.fastforward(grid)
                    weighted_grid_arr = self.getWeightedArray(ff_grid, scale)
                else:
                    ff_grid = occupancygrid_to_numpy(grid)
                    if grid_name == 'occupancy' or grid_name == 'future_occupancy':
                        ff_grid = self.resizeOccupancyGrid(ff_grid)
                    weighted_grid_arr = ff_grid*scale

                # weighted_grid_arr = self.getWeightedArray(ff_grid, scale)
                #if grid_name == 'occupancy' or grid_name == 'future_occupancy':
                #    weighted_grid_arr = self.resizeOccupancyGrid(weighted_grid_arr)

                if grid_name == 'drivable':
                    #pass
                    #steering_cost += weighted_grid_arr
                    steering_cost = np.maximum( steering_cost , weighted_grid_arr )
                elif grid_name == 'junction':
                    pass
                    # speed_cost += weighted_grid_arr
                    # speed_cost = np.maximum( speed_cost , weighted_grid_arr )
                else:
                    # steering_cost += weighted_grid_arr
                    # speed_cost += weighted_grid_arr
                    steering_cost = np.maximum( steering_cost , weighted_grid_arr )

            # Cap this to 100
            steering_cost = np.clip(steering_cost, 0, 100)
            speed_cost = np.clip(speed_cost, 0, 100)

            # plt.show()

            # Publish as an OccupancyGrid
            steering_cost_msg = OccupancyGrid()
            steering_cost_msg.info.map_load_time = self.clock.clock
            steering_cost_msg.info.resolution = 0.4 # should avoid hard coding this
            steering_cost_msg.info.width = steering_cost.shape[0]
            steering_cost_msg.info.height = steering_cost.shape[1]
            steering_cost_msg.info.origin.position.x = -20.0 # should avoid hard coding this
            steering_cost_msg.info.origin.position.y = -30.0 # should avoid hard coding this
            steering_cost_msg.header.stamp = self.clock.clock
            steering_cost_msg.header.frame_id = 'base_link'
            steering_cost_msg.data = steering_cost.astype(np.int8).flatten().tolist()
            self.steering_cost_pub.publish(steering_cost_msg)

            speed_cost_msg = OccupancyGrid()
            speed_cost_msg.info.map_load_time = self.clock.clock
            speed_cost_msg.info.resolution = 0.4 # should avoid hard coding this
            speed_cost_msg.info.width = speed_cost.shape[0]
            speed_cost_msg.info.height = speed_cost.shape[1]
            speed_cost_msg.info.origin.position.x = -20.0 # should avoid hard coding this
            speed_cost_msg.info.origin.position.y = -30.0 # should avoid hard coding this
            speed_cost_msg.header.stamp = self.clock.clock
            speed_cost_msg.header.frame_id = 'base_link'
            speed_cost_msg.data = speed_cost.astype(np.int8).flatten().tolist()
            self.speed_cost_pub.publish(speed_cost_msg)
        except(Exception) as e:
            self.get_logger().warn('Error composing aggregate cost map - likely waiting for Transform Buffer.')
            self.get_logger().warn(str(e))


    #     # Temporarily commenting out...
    #     # egma_msg = Egma()
    #     # egma_msg.header = steering_cost_msg.header

    #     # current_stamp = steering_cost_msg.header.stamp
    #     # t = current_stamp.sec + current_stamp.nanosec * 1e-9
    #     # for i in range(15):
    #     #     frame = steering_cost_msg

    #     #     t += 0.1  # dt = 0.1 seconds
    #     #     next_stamp = current_stamp
    #     #     next_stamp.sec = int(t)
    #     #     next_stamp.nanosec = int(t * 1e9 % 1e9)

    #     #     steering_cost_msg.header.stamp = next_stamp
    #     #     steering_cost_msg.header.frame_id = 'base_link'

    #     #     egma_msg.egma.append(frame)

    #     # self.combined_egma_pub.publish(egma_msg)


def main(args=None):
    rclpy.init(args=args)
    node = GridSummationNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
    # try:
    #     rclpy.spin(node)
    # except KeyboardInterrupt:
    #     pass
    # node.destroy_node()
    # rclpy.shutdown()


if __name__ == '__main__':
    main()
