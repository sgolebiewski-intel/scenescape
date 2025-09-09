## Camera Undistortion

### Gstreamer

Run the gstreamer undistortion pipeline. Ensure input file exists in the path

`./undistort-pipeline.sh` pipeline starts, hit ctrl+C to stop and save an image frame into `gstreamer_undistorted_full.jpg`

### Percebro

Get the undistorted camera frame under IMAGE_CALIBRATE. After , building on this branch , `SUPASS=<> docker compose -f percebro_undistorted_calibration_frame.yml up -d`.

Get into the shell, `./tools/scenescape-start --shell` and run the script to save the calibration image frame `./tools/calibration_image_saver.py`

### Compare images

Compare images `percebro_undistorted_image_full.jpg` and `gstreamer_undistorted_full.jpg`.