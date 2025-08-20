rm qcam1.mp4 qcam2.mp4 
ffmpeg -i qcam-orig1.mp4 -ss 2.0 -c:v libx264 -c:a copy qcam1.mp4
ffmpeg -i qcam-orig2.mp4 -t 52.10 -c:v libx264 -c:a copy qcam2.mp4
ffmpeg -i qcam1.mp4 
ffmpeg -i qcam2.mp4 
cp qcam1.mp4 qcam1_20f_trim.mp4; cp qcam2.mp4 qcam2_trim_20f.mp4
