"""
Package:   object_detector_3d
Filename:  lidar_detection_model.py
Author:    Gueren Sanford
Email:     guerensanford@gmail.com
Copyright: 2021, Nova UTD
License:   MIT License
Use this class to make object detections with LiDAR data in the format 
[x,y,z,intensity]. We use the model Complex Yolo to make the 
predictions, which requires a birds eye view map of the LiDAR data. 
With the predictions, feed it into the postprocess to filter out and 
format the results.
"""

# Python Imports
import random
import numpy as np
import ros2_numpy as rnp
import torch

# Local Import
from object_detector_3d.complex_yolo.darknet2pytorch import Darknet
from object_detector_3d.lidar_utils import kitti_bev_utils
from object_detector_3d.lidar_utils.evaluation_utils import \
    rescale_boxes, post_processing_v2
import  object_detector_3d.lidar_utils.kitti_config as cnf

# Message definitions
from geometry_msgs.msg import Point
from sensor_msgs.msg import PointCloud2
from navigator_msgs.msg import BoundingBox3D, Object3D, Object3DArray

config_file = './data/perception/configs/complex_yolov4.cfg'
model_path = './data/perception/checkpoints/complex_yolov4_mse_loss.pth'

class LidarDetectionModel():
    def __init__(self, device: torch.device, use_giou_loss: bool = True):
        """! Initializes the node.
        @param device[torch.device]  The device the model will run on
        @param use_giou_loss[bool]   Use generalized intersection over 
            union as a loss function
        """
        self.img_size = 608 # Determined by the birds eye view setup
        self.device = device

        # Setup for the Complex Yolo model
        self.model = Darknet(cfgfile=config_file, 
            use_giou_loss=use_giou_loss)
        self.model.load_state_dict(torch.load(model_path, 
            map_location=self.device))
        self.model.to(device=self.device)

    def preprocess(self, lidar_msg: PointCloud2):
        """! Converts ROS LiDAR message into the bird's eye view input 
            tensor for the model.
        @param lidar_msg[PointCloud2]   The ros2 lidar dmessage data
            formatted as a PointCloud2 message.
        @return torch.Tensor   A 608 x 608 birds eye view image of the
            point cloud data. Red = Intensity, Green = Height, Blue = 
            Density
        """
        
        # Point cloud byte stream -> np array with all fields and dtypes
        lidar_np = rnp.numpify(lidar_msg)
        # Reduces the vertical res from 128 to 64
        lidar_np = lidar_np[::2]   # matches Kitti dataset
        # Combines necessary lidar data into an array [n, n, n, n]]
        lidar_pcd = np.array([ # Avoids np array dtype issues
            lidar_np['x'].flatten(), 
            lidar_np['y'].flatten(), 
            lidar_np['z'].flatten(), 
            lidar_np['reflectivity'].flatten()])
        # Tranforms array to shape [(x y z r), n]
        lidar_pcd = np.transpose(lidar_pcd)
        lidar_pcd[:, 3] /= 255.0 # Normalizes refl.
        
        # Removes the points outside birds eye view (bev) map
        reduced_lidar = kitti_bev_utils.removePoints(lidar_pcd, 
            cnf.boundary)
        # Turns the point cloud into a bev rgb map
        rgb_map = kitti_bev_utils.makeBVFeature(reduced_lidar, 
            cnf.DISCRETIZATION, cnf.boundary)
        
        return rgb_map

    def predict(self, input_bev: torch.Tensor):
        """! Uses the tensor from the preprocess fn to return the 
            bounding boxes for the objects.
        @param input_bev[torch.Tensor]  The result of the preprocess 
            function.
        @return torch.Tensor  The output of the model in the shape
            [1, boxes, x y w l classes], where the classes are Car, 
            Pedestrian, Cyclist, Van, Person_sitting.
        """
        # The model outputs [1, boxes, x y w l classes]
        return self.model(input_bev)

    def postprocess(self, rgb_map: torch.Tensor, 
            predictions: torch.Tensor, conf_thresh: int, 
            nms_thresh: int):
        """! 
        NEEDS OPTIMIZATION

        @param input_bev[torch.Tensor]   The result of the preprocess 
            function.
        @param predictions[torch.Tensor]   The output of the model in 
            the shape [1, boxes, x y w l classes], where the classes 
            are Car, Pedestrian, Cyclist, Van, Person_sitting.
        @param conf_thresh[int]   The mininum confidence value accepted
            for bounding boxes.
        @param nms_thresh[int]   The maximum accepted intersection over
            union value for bounding boxes. 
        @return navigator_msgs.msg.Object3DArray  A ros2 message ready 
            to be published. Before publishing, the header needs to be 
            attached. 
        """
        # Returns detections with shape: (x, y, w, l, im, re, object_conf, class_score, class_pred)
        detections = post_processing_v2(predictions, conf_thresh=conf_thresh, 
            nms_thresh=nms_thresh)[0]

        # Skip if no detections made
        if detections is None:
            return None

        predictions = []
        for x, y, w, l, im, re, cls_conf, *_, cls_pred in detections:
            predictions.append([cls_pred, cls_conf, x / self.img_size, y / self.img_size, 
                w / self.img_size, l / self.img_size, im, re])

        # Returns shape [c, c_conf, x, y, z, w, l, h, yaw]
        predictions = kitti_bev_utils.inverse_yolo_target(np.array(predictions), cnf.boundary) # IMPROVE

        # Turns the predictions into array of Object3D msg types
        object_3d_array = Object3DArray()
        for prediction in predictions:
            # Defines the custom ros2 msgs
            bounding_box = BoundingBox3D()
            object_3d = Object3D()

            # Need x, y, z, x_size, y_size, z_size, yaw
            bounding_box.coordinates = prediction[2:]

            # Returns the corners in the order specified by BoundingBox3D msg
            corners_3d = kitti_bev_utils.get_corners_3d(*bounding_box.coordinates) # IMPROVE get_corners
            # Fills the Point corners array
            for i, corner_3d in enumerate(corners_3d):
                bounding_box.corners[i] = Point(x=corner_3d[0], y=corner_3d[1], z=corner_3d[2])

            object_3d.label = (int(prediction[0]) - 1) % 3 # changes label to match format of message
            object_3d.id = random.randint(0, 2**16-1)
            object_3d.confidence_score = prediction[1]
            object_3d.bounding_box = bounding_box
            
            object_3d_array.objects.append(object_3d)

        return object_3d_array