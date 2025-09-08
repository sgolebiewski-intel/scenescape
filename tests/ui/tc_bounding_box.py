#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2022 - 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import cv2
import json
import time
import base64
import numpy as np
import tests.ui.common_ui_test_utils as common

from scene_common import log
from scene_common.mqtt import PubSub
from scene_common.timestamp import get_epoch_time

TEST_WAIT_TIME = 10
MAX_TEST_WAIT_TIME = 60
MAX_IMAGES = 100
MIN_PIXELS_VALUE = 1000

used_camera = "camera1"
timestamp_detections = []
timestamp_bbox = []
counter_bbox = 0
counter_detections = 0
counter_bad_bbox = 0
connected = False
keep = []

def on_connect(mqttc, data, flags, rc):
  """! Call back function for MQTT client on establishing a connection, which subscribes to the topic.
  @param    mqttc     The mqtt client object.
  @param    data      The private user data.
  @param    flags     The response sent by the broker.
  @param    rc        The connection result.
  """
  global connected
  connected = True
  log.info("Connected")
  topic = PubSub.formatTopic(PubSub.IMAGE_CAMERA, camera_id=used_camera)
  mqttc.subscribe(topic, 0)
  topic = PubSub.formatTopic(PubSub.DATA_CAMERA, camera_id=used_camera)
  mqttc.subscribe(topic, 0)
  return

def on_message(mqttc, data, msg):
  """! Call back function for the MQTT client on receiving messages.
  Checks that a minimum number of red pixels are in the received image.
  This check is a proxy way of checking that the image contains a red bounding box.
  @param    mqttc     The mqtt client object.
  @param    data      The private user data.
  @param    msg       The instance of MQTTMessage.
  """
  global counter_bbox
  global counter_detections
  global counter_bad_bbox

  real_msg = str(msg.payload.decode("utf-8"))
  log.debug("Msg received (Topic {})".format(msg.topic))
  json_data = json.loads(real_msg)
  topic = PubSub.parseTopic(msg.topic)
  camName = topic['camera_id']
  if topic['_topic_id'] == PubSub.IMAGE_CAMERA and camName == used_camera:
    if counter_bbox < MAX_IMAGES:
      assert 'timestamp' in json_data, "json_data missing 'timestamp'"
      assert 'image' in json_data, "json_data missing 'image'"
      # Ignore images we already looked at, by timestamp.
      if json_data['timestamp'] not in timestamp_bbox:
        img_bytes = base64.b64decode(json_data['image'])
        log.debug("message {}".format(counter_bbox))
        im_arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img_processed = cv2.imdecode(im_arr, flags=cv2.IMREAD_COLOR)

        result = img_processed.copy()
        image = cv2.cvtColor(img_processed.astype(np.uint8), cv2.COLOR_BGR2HSV)
        # lower boundary RED color range values; Hue (0 - 10)
        lower1 = np.array([0, 100, 20], np.uint8)
        upper1 = np.array([10, 255, 255], np.uint8)

        # upper boundary RED color range values; Hue (160 - 180)
        lower2 = np.array([160, 100, 20], np.uint8)
        upper2 = np.array([179, 255, 255], np.uint8)

        # locations of the red bounding box.
        lower_mask = cv2.inRange(image, lower1, upper1)
        upper_mask = cv2.inRange(image, lower2, upper2)
        full_mask = lower_mask + upper_mask

        result = cv2.bitwise_and(result, result, mask=full_mask)
        numRed = cv2.countNonZero(full_mask)
        log.debug('The number of red pixels is: ' + str(numRed))
        if numRed > MIN_PIXELS_VALUE:
          keep.append(result)
          log.debug("Msg at {} with {} pels ".format(json_data['timestamp'], numRed))

          timestamp_bbox.append(json_data['timestamp'])
          # Only increment counter_bbox if timestamp is in timestamp_detections
          if json_data['timestamp'] in timestamp_detections:
            counter_bbox += 1
          # Otherwise, wait for DATA_CAMERA to arrive and handle matching there
  elif topic['_topic_id'] == PubSub.DATA_CAMERA and camName == used_camera:
    detections = 0
    if 'objects' in json_data:
      for _, detection in json_data['objects'].items():
        if len(detection) > 0:
          counter_detections += 1
          timestamp_detections.append(json_data['timestamp'])
          detections += len(detection)
      if detections > 0:
        log.debug("Msg at {} with {} detections".format(json_data['timestamp'], detections))
        # If IMAGE_CAMERA for this timestamp already arrived, increment counter_bbox
        if json_data['timestamp'] in timestamp_bbox:
          counter_bbox += 1
    else:
      log.warning("DATA_CAMERA message missing 'objects' key")
  mqttc.publish(PubSub.formatTopic(PubSub.CMD_CAMERA, camera_id=used_camera), "getimage")
  return

def test_bounding_box(params, record_xml_attribute):
  """! Checks that red object detection bounding boxes appear in the camera 1 image stream.
  @param    params                  Dict of test parameters.
  @param    record_xml_attribute    Pytest fixture recording the test name.
  @return   exit_code               Indicates test success or failure.
  """
  global counter_bbox
  global counter_detections
  global counter_bad_bbox

  TEST_NAME = "NEX-T10419"
  record_xml_attribute("name", TEST_NAME)
  log.info("Executing: " + TEST_NAME)

  client = PubSub(params['auth'], None, params['rootcert'], params['broker_url'])
  exit_code = 1

  client.onConnect = on_connect
  client.onMessage = on_message
  client.connect()

  testStart = get_epoch_time()
  while(counter_bbox < MAX_IMAGES):
    client.loopStart()
    time.sleep(TEST_WAIT_TIME)
    client.loopStop()
    log.info("{} bounding boxes so far".format(counter_bbox))
    testTime = get_epoch_time()
    if testTime - testStart > MAX_TEST_WAIT_TIME:
      log.error("Test seems stuck, aborting")
      break

  if connected:
    log.info("{} snapshots containing bounding boxes were detected around {} expected, {} bad ones".format(counter_bbox, counter_detections, counter_bad_bbox))
    # Missed images are ok, but not false positives
    if counter_detections >= counter_bbox and counter_bad_bbox == 0 and counter_bbox >= MAX_IMAGES:
      exit_code = 0
  else:
    log.error("Failed to connect!")

  common.record_test_result(TEST_NAME, exit_code)
  assert exit_code == 0
  return
