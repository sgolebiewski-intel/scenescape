#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2022 - 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from tests.functional import FunctionalTest
from tests.common_test_utils import check_event_contains_data
from http import HTTPStatus
from scene_common.rest_client import RESTClient
from scene_common.mqtt import PubSub
import time
import os
import json
from scene_common.timestamp import get_iso_time, get_epoch_time

TEST_NAME = 'NEX-T10430'
ROI_NAME = "Automated_ROI"
FRAMES_PER_SECOND = 10
PERSON = "person"
REGION = "region"
MAX_CONTROLLER_WAIT = 30 # seconds
MAX_ATTEMPTS = 3
roi_deleted = False
message_received_after_delete = False

class ROIMqtt(FunctionalTest):
  def __init__(self, testName, request, recordXMLAttribute):
    super().__init__(testName, request, recordXMLAttribute)
    self.sceneUID = self.params['scene_id']
    self.roiName = ROI_NAME
    self.frameRate = FRAMES_PER_SECOND
    self.rest = RESTClient(self.params['resturl'], rootcert=self.params['rootcert'])
    res = self.rest.authenticate(self.params['user'], self.params['password'])
    assert res, (res.errors)

    self.pubsub = PubSub(self.params['auth'], None, self.params['rootcert'],
                         self.params['broker_url'], int(self.params['broker_port']))

    self.pubsub.connect()
    self.pubsub.loopStart()
    return

  def eventReceived(self, pahoClient, userdata, message):
    data = message.payload.decode("utf-8")
    regionData = json.loads(data)
    check_event_contains_data(regionData, "region")

    if getattr(self, "roi_deleted", False):
      self.message_received_after_delete = True
      print("No event received")
      return

    for regionObj in regionData['objects']:
      for sceneObj in self.sceneData['objects']:
        if regionObj['id'] == sceneObj['id']:
          self.expectedEnter.append(sceneObj['id'])
    self.verifyRegionEvent(regionData)
    return

  def verifyRegionEvent(self, regionEvent):
    self.entered = False
    self.exited = False

    if len(regionEvent['entered']) > 0:
      for event in regionEvent['entered']:
        assert len(self.expectedEnter) > 0
        if event['id'] in self.expectedEnter:
          currPoint = event['translation']
          if self.isWithinRectangle(self.roiPoints[1], self.roiPoints[3], (currPoint[0], currPoint[1])):
            self.expectedExit.append(event['id'])
            self.expectedEnter.remove(event['id'])
            self.entered = True
            print("object with id {} entered region\n".format(event['id']))

    if len(regionEvent['exited']) > 0:
      for event in regionEvent['exited']:
        assert len(self.expectedExit) > 0
        if event['object']['id'] in self.expectedExit:
          self.expectedExit.remove(event['object']['id'])
          self.exited = True
          print("object with id {} exited region\n".format(event['object']['id']))
    return

  def isWithinRectangle(self, bl, tr, curr_point):
    if (curr_point[0] > bl[0] and curr_point[0] < tr[0] and \
      curr_point[1] > bl[1] and curr_point[1] < tr[1]):
      return True
    else:
      return False

  def setupROI(self, roiData):
    res = self.rest.createRegion(roiData)
    assert res.statusCode == HTTPStatus.CREATED, (res.statusCode, res.errors)

    self.roi_uid = res['uid']
    print(f"ROI UID Create: {self.roi_uid}")
    topic = PubSub.formatTopic(PubSub.EVENT, event_type="count", scene_id=self.sceneUID,
                               region_id=self.roi_uid, region_type=REGION)
    self.pubsub.addCallback(topic, self.eventReceived)

    
    assert res['points']
    return res['points']

  def deleteROI(self, roi_uid):
    print(f"ROI UID Delete: {roi_uid}")
    res = self.rest.deleteRegion(roi_uid)
    print(f"status check: {res.statusCode}")
    assert res.statusCode == HTTPStatus.OK, (res.statusCode, res.errors)
    print(f"ROI {roi_uid} deleted successfully")
    self.roi_deleted = True
    return

  def sendDetections(self, objLocation, frame_rate):
    jdata = self.objData()
    for location in objLocation:
      camera_id = jdata['id']
      jdata['timestamp'] = get_iso_time()
      jdata['objects'][PERSON][0]['bounding_box']['y'] = location
      detection = json.dumps(jdata)
      self.pubsub.publish(PubSub.formatTopic(PubSub.DATA_CAMERA,
                                        camera_id=camera_id), detection)
      time.sleep(1 / frame_rate)
    return

  def runROIMqttInitialize(self):
    self.expectedEnter = []
    self.expectedExit = []
    self.sceneData = None
    self.entered = False
    self.exited = False
    self.roiPoints = ((0.9, 4.0), (0.9, 2.4),
                      (8.1, 2.4), (8.1, 4.0))
    self.message_received_after_delete = False
    if self.testName and self.recordXMLAttribute:
      self.recordXMLAttribute("name", self.testName)

    return

  def sceneReady(self, max_attempts, waitTopic, publishTopic, objData):
    attempts = 0
    ready = None

    while attempts < max_attempts:
      attempts += 1
      begin = get_epoch_time()
      ready = self.sceneControllerReady(waitTopic, publishTopic, MAX_CONTROLLER_WAIT,
                                      begin, 1 / self.frameRate, objData)
      if ready:
        break
    else:
      print('reached max number of attemps to wait for scene controller')
    return

  def regulatedReceived(self, pahoClient, userdata, message):
    data = message.payload.decode("utf-8")
    self.sceneData = json.loads(data)
    return

  def runROIMqttPrepare(self):
    objData = self.objData()
    waitTopic = PubSub.formatTopic(PubSub.DATA_SCENE,
                                   scene_id=self.sceneUID, thing_type=PERSON)
    publishTopic = PubSub.formatTopic(PubSub.DATA_CAMERA, camera_id=objData['id'])
    objLocation = self.getLocations()
    objData['objects'][PERSON][0]['bounding_box']['y'] = objLocation[0]
    self.sceneReady(MAX_ATTEMPTS, waitTopic, publishTopic, objData)

    self.getScene()
    roi = {'scene': self.sceneUID,
         'name': self.roiName,
         'points': self.roiPoints}

    points = self.setupROI(roi)

    topic_regulated = PubSub.formatTopic(PubSub.DATA_REGULATED, scene_id=self.sceneUID)
    self.pubsub.addCallback(topic_regulated, self.regulatedReceived)

    print("BottomLeft: ", points[1])
    print("TopRight: ", points[3])
    return

  def runROIMqttExecute(self):
    objLocation = self.getLocations()
    self.sendDetections(objLocation, self.frameRate)
    print("Expected entered list: ", self.expectedEnter)
    print("Expected exited list: ", self.expectedExit)
    return

  def runROIMqttDelete(self):
    self.deleteROI(self.roi_uid)
    objLocation = self.getLocations()
    self.sendDetections(objLocation, self.frameRate)
    time.sleep(2)
    return

  def runROIMqttVerifyPassed(self):
    return self.exited and self.entered == False \
              and len(self.expectedExit) == 0 \
              and len(self.expectedEnter) == 0

  def runROIMqttVerifyNoEventsAfterDelete(self):

    time.sleep(2)
    if self.message_received_after_delete:
      print("Still receiving message from ROI!")
      return False
    print("No events published after ROI deletion")
    return True

  def runROIMqttVerifyPassedExtra(self):
    return True

  def runROIMqttFinally(self):
    self.pubsub.loopStop()
    self.recordTestResult()
    return

  def runROIMqtt(self):
    self.exitCode = 1
    self.runROIMqttInitialize()
    try:
      self.runROIMqttPrepare()
      self.runROIMqttExecute()
      passed = self.runROIMqttVerifyPassed()
      self.runROIMqttDelete()
      passed_after_delete = self.runROIMqttVerifyNoEventsAfterDelete()
      if (passed and passed_after_delete):
        self.exitCode = 0
    finally:
      self.runROIMqttFinally()
    return

def test_roi_mqtt(request, record_xml_attribute):
  test = ROIMqtt(TEST_NAME, request, record_xml_attribute)
  test.runROIMqtt()
  assert test.exitCode == 0
  return

def main():
  return test_roi_mqtt(None, None)

if __name__ == '__main__':
  os._exit(main() or 0)
