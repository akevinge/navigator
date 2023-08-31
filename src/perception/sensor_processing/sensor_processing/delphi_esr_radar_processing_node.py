'''
Package: sensor_processing
   File: delphi_esr_radar_processing_node.py
 Author: Justin Ruths

Node to receive radar messages from a Delphi ESR radar

This node is intended for real-world use.
'''

import time

import matplotlib.pyplot as plt
import numpy as np
import rclpy
import ros2_numpy as rnp
from scipy.spatial.transform import Rotation as R
# Message definitions
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import OccupancyGrid
from delphi_esr_msgs.msg import EsrTrack, EsrTrackMotionPowerTrack, EsrTrackMotionPowerGroup
from derived_object_msgs.msg import ObjectWithCovarianceArray, ObjectWithCovariance
from visualization_msgs.msg import Marker, MarkerArray
from rclpy.node import Node
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import Float32, ColorRGBA
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener


class DelphiESRRadarProcessingNode(Node):

    def __init__(self):
        super().__init__('delphi_esr_radar_processing_node')

        self.classifications=['Unknown','Unknown Small','Unknown Medium','Unknown Big','Pedestrian','Bike','Car','Truck','Motorcycle','Other Vehicle','Barrier','Sign']
        self.shape_types=['NONE','BOX','SPHERE','CYLINDER','CONE']

        self.power_cached = dict()
        self.track_markers_cached = dict()

        for trackid in range(1,65):
            self.power_cached[trackid] = -100

        self.clock = 0.0
        self.clock_msg = Clock()

        # self.objects_sub = self.create_subscription(
        #     ObjectWithCovarianceArray, '/radar_1/objects', self.objectsCb, 10)
        
        self.track_sub = self.create_subscription(
            EsrTrack, '/radar_1/esr_track', self.trackCb, 10)
        
        self.objects_sub = self.create_subscription(
            EsrTrackMotionPowerGroup, '/radar_1/esr_track_motion_power_group', self.motionCb, 10)

        self.clock_sub = self.create_subscription(
            Clock, '/clock', self.clockCb, 10
        )

        self.radar_pub = self.create_publisher(
            MarkerArray, '/radar/radar_viz', 10
        )

        # Implement a consolidated radar data, that has track data plus amplitude
        # self.radar_pub = self.create_publisher(
        #     MarkerArray, '/radar/radar_data', 10
        # )

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)



    def clockCb(self, msg: Clock):
        self.clock = msg.clock.sec + msg.clock.nanosec * 1e-9
        self.clock_msg = msg

    def objectsCb(self, msg: ObjectWithCovarianceArray):
        for obj in msg.objects:
            if obj.classification > 0:
                self.get_logger().info('%i: class: %s [%1.0f] age: %i' % (obj.id,self.classifications[obj.classification],float(obj.classification_certainty)/255.0*100.0,obj.classification_age))
                self.get_logger().info('PolyPts: %i, ShapeType: %s' % (len(obj.polygon.points),self.shape_types[obj.shape.type]))
            #self.get_logger().info('%1.2f, %1.2f, %1.2f' % (obj.shape.dimensions[0],obj.shape.dimensions[1],obj.shape.dimensions[2]))
        #self.get_logger().info('=========================')
        return

    def motionCb(self, msg: EsrTrackMotionPowerGroup):
        for track in msg.tracks:
            # grab out the power from this message to look up when EsrTrack message comes in
            self.power_cached[track.id] = track.power
        return

    def trackCb(self, msg: EsrTrack):
        #self.get_logger().info('[%i] status:%i %1.2fm, %1.1fdeg, %1.2fdB %1.2f/%1.2f' % (msg.id,msg.status,msg.range,msg.angle,self.power_cached[msg.id],msg.range_rate,msg.range_accel))

        marker = Marker()
        marker.header.frame_id = 'base_link'
        marker.header.stamp = self.clock_msg.clock
        # cylinder
        marker.type = Marker.CYLINDER
        marker.action = Marker.ADD
        marker.ns = 'trk'
        marker.id = msg.id
        #marker.lifetime.sec = 1
        # calculate xy position of track
        x = msg.range*np.cos(msg.angle*np.pi/360.0)
        y = msg.range*np.sin(msg.angle*np.pi/360.0)
        v = self.transformToBaseLink(x,y,0.0)
        marker.pose.position.x = v[0]
        marker.pose.position.y = v[1]
        marker.pose.position.z = v[2]

        marker.pose.orientation.w = 1.0

        # scale the marker by the dB power
        marker.scale.x = 0.25*np.power(10.0,self.power_cached[msg.id]/10.0)
        marker.scale.y = 0.25*np.power(10.0,self.power_cached[msg.id]/10.0)
        marker.scale.z = 0.1

        # choose color based on speed
        color = ColorRGBA()
        color.a = 0.9
        if msg.range_rate > 0:
            color.r = 1.0
            color.g = np.max([1.0 - msg.range_rate/4.0,0.0])
            color.b = np.max([1.0 - msg.range_rate/4.0,0.0])
        else:
            color.r = np.max([1.0 + msg.range_rate/4.0,0.0])
            color.g = np.max([1.0 + msg.range_rate/4.0,0.0])
            color.b = 1.0
        marker.color = color

        # self.get_logger().info('[%i] Position: %1.2f, %1.2f, %1.2f' % (msg.id,marker.pose.position.x,marker.pose.position.y,marker.pose.position.z))
        # self.get_logger().info('[%i] Scale: %1.2f, %1.2f, %1.2f' % (msg.id,marker.scale.x,marker.scale.y,marker.scale.z))
        # self.get_logger().info('[%i] Color: %1.2f, %1.2f, %1.2f' % (msg.id,marker.color.r,marker.color.g,marker.color.b))

        self.track_markers_cached[msg.id] = marker

        marker_array_msg = MarkerArray()
        for mid, mkr in self.track_markers_cached.items():
            marker_array_msg.markers.append(mkr)

        self.radar_pub.publish(marker_array_msg)

        # self.right_pcd_cached: np.array = rnp.numpify(msg)
        # self.right_pcd_cached = self.transformToBaseLink(self.right_pcd_cached, 'radar')

        # merged_x = np.append(
        #     self.left_pcd_cached['x'], self.right_pcd_cached['x'])
        # merged_y = np.append(
        #     self.left_pcd_cached['y'], self.right_pcd_cached['y'])
        # merged_z = np.append(
        #     self.left_pcd_cached['z'], self.right_pcd_cached['z'])
        # merged_i = np.append(
        #     self.left_pcd_cached['intensity'], self.right_pcd_cached['intensity'])

        # total_length = (self.left_pcd_cached.shape[0] + \
        #     self.right_pcd_cached.shape[0]) * 16 # 16 rings

        # msg_array = np.zeros(total_length, dtype=[
        #     ('x', np.float32),
        #     ('y', np.float32),
        #     ('z', np.float32),
        #     ('intensity', np.float32)
        # ])

        # msg_array['x'] = merged_x
        # msg_array['y'] = merged_y
        # msg_array['z'] = merged_z
        # msg_array['intensity'] = merged_i

        # msg_array = self.remove_nearby_points(msg_array, (-4.0,0.5), (-1.3,1.3))
        # # msg_array = self.remove_points_above(msg_array, 2.0)
        # # msg_array = self.remove_ground_points(msg_array, 0.2)

        # # self.publish_occupancy_grid(msg_array, range=40.0, res=0.5)

        # merged_pcd_msg: PointCloud2 = rnp.msgify(PointCloud2, msg_array)
        # merged_pcd_msg.header.frame_id = 'base_link'
        # merged_pcd_msg.header.stamp = self.clock_msg.clock

        # self.clean_lidar_pub.publish(merged_pcd_msg)
        return

    def transformToBaseLink(self, x, y, z):
        '''
        Transform radar point into car's origin frame
        :param x,y,z: Original point in the radar frame
        :returns: Transformed point as a ros2_numpy array
        '''

        try:
            t: TransformStamped = self.tf_buffer.lookup_transform('base_link', 'radar', rclpy.time.Time())
            quat = t.transform.rotation
        except Exception as e:
            self.get_logger().error(str(e))
            return

        v = np.array([x,y,z])

        # First rotate
        r: R = R.from_quat([quat.x, quat.y, quat.z, quat.w])
        v = r.apply(v)

        # Then translate
        v[0] = v[0] + t.transform.translation.x
        v[1] = v[1] + t.transform.translation.y
        v[2] = v[2] + t.transform.translation.z

        return v

    def remove_ground_points(self, pcd: np.array, height: float) -> np.array:
        '''
        Simple function to remove points below a certain height.
        :param pcd: a numpy array of the incoming point cloud, in the format provided by ros2_numpy.
        :param height: points with a z value less than this will be removed
        :returns: an array in ros2_numpy format with low points removed
        '''
        return pcd[pcd['z'] >= height]

    def remove_nearby_points(self, pcd: np.array, x: tuple, y: tuple) -> np.array:
        '''
        Remove points in a rectangle around the sensor

        :param pcd: a numpy array of the incoming point cloud, in the format provided by ros2_numpy.
        :param x_distance, y_distance: points with an x/y value whose absolute value is less than this number will be removed

        :returns: an array in ros2_numpy format with the nearby points removed
        '''

        # Unfortunately, I can't find a way to avoid doing this in one go
        pcd = pcd[np.logical_not(
            np.logical_and(
                np.logical_and(pcd['x'] > x[0],
                               pcd['x'] < x[1]),
                np.logical_and(pcd['y'] > y[0],
                               pcd['y'] < y[1]),
            ))]

        pcd = pcd[pcd['z'] >= -2.0]

        return pcd

    def remove_points_above(self, pcd: np.array, height: float) -> np.array:
        '''
        Remove points above the height of the sensor specified around the sensor

        :param pcd: a numpy array of the incoming point cloud, in the format provided by ros2_numpy.
        :param min_height: points with an z value whose absolute value is greater than this number will be removed

        :returns: an array in ros2_numpy format with the nearby points removed
        '''

        pcd = pcd[pcd['z'] <= height]

        return pcd


def main(args=None):
    rclpy.init(args=args)

    radar_processor = DelphiESRRadarProcessingNode()

    rclpy.spin(radar_processor)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    radar_processor.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
