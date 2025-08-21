#!/bin/bash
echo "container: scenescape-queuing-video-1 FPS: " \
$(docker logs scenescape-queuing-video-1 | tr '}' '\n' | grep '"fps":' | awk '{print $NF}' | tail -n +401 | awk '{sum+=$1; sumsq+=$1*$1; n++} END {if(n>0){avg=sum/n; stddev=sqrt(sumsq/n - avg*avg)*sqrt(n/(n-1)); print "avg=" avg ", stddev=" stddev}}')
echo "container: scenescape-retail-video-1 FPS: " \
$(docker logs scenescape-retail-video-1 | tr '}' '\n' | grep '"fps":' | awk '{print $NF}' | tail -n +401 | awk '{sum+=$1; sumsq+=$1*$1; n++} END {if(n>0){avg=sum/n; stddev=sqrt(sumsq/n - avg*avg)*sqrt(n/(n-1)); print "avg=" avg ", stddev=" stddev}}')
