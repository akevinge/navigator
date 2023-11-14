import cv2
import os
import numpy as np
dir = os.listdir("test")

cap = cv2.VideoCapture("test/" + dir[1])

if (cap.isOpened() == False):
    print("Error opening video stream or file")
# Read until video is completed
while (cap.isOpened()):
    # Capture frame-by-frame
    ret, frame = cap.read()
    if ret == True:
        # Display the resulting frame
        cv2.imshow('Frame', frame)
        # Press Q on keyboard to  exit
        if cv2.waitKey(25) & 0xFF == ord('q'):
            break