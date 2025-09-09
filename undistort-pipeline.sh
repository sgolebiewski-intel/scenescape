#!/bin/bash

INPUT_VIDEO="/home/intel/fresh/sample_data/02_frame1.jpg"

echo "Input video: $INPUT_VIDEO"

# Camera Intrinsics and Distortion Coefficients in XML format for the parking lot dataset
DATA="<?xml version=\"1.0\"?><opencv_storage><cameraMatrix type_id=\"opencv-matrix\"><rows>3</rows><cols>3</cols><dt>f</dt><data>3.146e+03 0. 1.920e+03 0. 3.146e+03 1.080e+03 0. 0. 1.</data></cameraMatrix><distCoeffs type_id=\"opencv-matrix\"><rows>5</rows><cols>1</cols><dt>f</dt><data>0.25 0. 0. 0. 0.</data></distCoeffs></opencv_storage>"

# Pipeline to undistort with input as video file and output to screen
# gst-launch-1.0 -v multifilesrc loop=TRUE location=$INPUT_VIDEO name=source ! decodebin ! videoconvert ! cameraundistort settings="$DATA" ! videoconvert ! autovideosink

# Pipeline to undistort with input as JPEG image and output as JPEG image
gst-launch-1.0 -v multifilesrc location=$INPUT_VIDEO name=source ! jpegdec ! videoconvert ! cameraundistort settings="$DATA" alpha=1.0 ! videoconvert ! jpegenc ! filesink location=gstreamer_undistorted_full.jpg

