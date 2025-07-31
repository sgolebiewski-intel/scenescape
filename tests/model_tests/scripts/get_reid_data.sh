#!/bin/bash
# SPDX-FileCopyrightText: (C) 2021 - 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

BROKER="broker.scenescape.intel.com"
PORT=1883
CAMERA1_TOPIC="scenescape/data/camera/camera1"
CAMERA2_TOPIC="scenescape/data/camera/camera2"
CAFILE="/run/secrets/certs/scenescape-ca.pem"
NUM_MESSAGES=100

if [ ! -f "$CAFILE" ]; then
  echo "Error: CA file not found at $CAFILE" >&2
  exit 1
fi

verify_reid_field() {
  local topic=$1
  local camera_name=$2
  echo "Checking up to $NUM_MESSAGES messages from topic: $topic (Camera: $camera_name)"

  mosquitto_sub -h "$BROKER" -p "$PORT" -t "$topic" --cafile "$CAFILE" \
    | awk -v limit="$NUM_MESSAGES" -v cam="$camera_name" '
      BEGIN { count = 0 }
      {
        if ($0 ~ /"reid":/) {
          printf("[%s] reid found in message %d\n", cam, count+1)
          print "Stopping early — reid found.\n"
          exit
        } else {
          printf("[%s] reid NOT found in message %d\n", cam, count+1)
        }
        count++
        if (count >= limit) {
          print "reid not found after checking", limit, "messages.\n"
          exit
        }
      }'
}

verify_reid_field "$CAMERA1_TOPIC" "camera1"
verify_reid_field "$CAMERA2_TOPIC" "camera2"
