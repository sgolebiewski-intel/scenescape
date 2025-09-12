# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import itertools
from typing import Optional

import cv2
import numpy as np

from scene_common import log
from scene_common.camera import Camera
from scene_common.earth_lla import convertLLAToECEF, calculateTRSLocal2LLAFromSurfacePoints
from scene_common.geometry import Line, Point, Region, Tripwire
from scene_common.scene_model import SceneModel
from scene_common.timestamp import get_epoch_time, get_iso_time
from scene_common.transform import CameraPose
from scene_common.mesh_util import getMeshAxisAlignedProjectionToXY, createRegionMesh, createObjectMesh

from controller.ilabs_tracking import IntelLabsTracking
from controller.tracking import (MAX_UNRELIABLE_TIME,
                                 NON_MEASUREMENT_TIME_DYNAMIC,
                                 NON_MEASUREMENT_TIME_STATIC)

DEBOUNCE_DELAY = 0.5

class TripwireEvent:
  def __init__(self, object, direction):
    self.object = object
    self.direction = direction
    return

class Scene(SceneModel):
  DEFAULT_TRACKER = "intel_labs"
  available_trackers = {
    'intel_labs': IntelLabsTracking,
  }

  def __init__(self, name, map_file, scale=None,
               max_unreliable_time = MAX_UNRELIABLE_TIME,
               non_measurement_time_dynamic = NON_MEASUREMENT_TIME_DYNAMIC,
               non_measurement_time_static = NON_MEASUREMENT_TIME_STATIC):
    log.info("NEW SCENE", name, map_file, scale, max_unreliable_time,
             non_measurement_time_dynamic, non_measurement_time_static)
    super().__init__(name, map_file, scale)
    self.ref_camera_frame_rate = None
    self.max_unreliable_time = max_unreliable_time
    self.non_measurement_time_dynamic = non_measurement_time_dynamic
    self.non_measurement_time_static = non_measurement_time_static
    self.tracker = None
    self.trackerType = None
    self.persist_attributes = {}
    self._setTracker(self.DEFAULT_TRACKER)
    self._trs_xyz_to_lla = None
    self.use_tracker = True

    # FIXME - only for backwards compatibility
    self.scale = scale

    return

  def _setTracker(self, trackerType):
    if trackerType not in self.available_trackers:
      log.error("Chosen tracker is not available")
      return
    self.trackerType = trackerType
    self.tracker = self.available_trackers[self.trackerType](self.max_unreliable_time,
                                           self.non_measurement_time_dynamic,
                                           self.non_measurement_time_static)
    return

  def updateScene(self, scene_data):
    self.parent = scene_data.get('parent', None)
    self.cameraPose = None
    if 'transform' in scene_data:
      self.cameraPose = CameraPose(scene_data['transform'], None)
    self.use_tracker = scene_data.get('use_tracker', True)
    self.output_lla = scene_data.get('output_lla', False)
    self.map_corners_lla = scene_data.get('map_corners_lla', None)
    self._updateChildren(scene_data.get('children', []))
    self.updateCameras(scene_data.get('cameras', []))
    self._updateRegions(self.regions, scene_data.get('regions', []))
    self._updateTripwires(scene_data.get('tripwires', []))
    self._updateRegions(self.sensors, scene_data.get('sensors', []))
    tracker_config = scene_data.get('tracker_config', None)
    if tracker_config:
      self.updateTracker(tracker_config[0], tracker_config[1], tracker_config[2])
    self.name = scene_data['name']
    if 'scale' in scene_data:
      self.scale = scene_data['scale']
    if 'regulated_rate' in scene_data:
      self.regulated_rate = scene_data['regulated_rate']
    if 'external_update_rate' in scene_data:
      self.external_update_rate = scene_data['external_update_rate']
    self._invalidate_trs_xyz_to_lla()
    # Access the property to trigger initialization
    _ = self.trs_xyz_to_lla
    return

  def updateTracker(self, max_unreliable_time, non_measurement_time_dynamic,
                    non_measurement_time_static):
    # Only update tracker if the values have changed to avoid losing tracking data
    if max_unreliable_time != self.max_unreliable_time or \
       non_measurement_time_dynamic != self.non_measurement_time_dynamic or \
       non_measurement_time_static != self.non_measurement_time_static:
      self.max_unreliable_time = max_unreliable_time
      self.non_measurement_time_dynamic = non_measurement_time_dynamic
      self.non_measurement_time_static = non_measurement_time_static
      self._setTracker(self.trackerType)
    return

  def _createMovingObjectsForDetection(self, detectionType, detections, when, camera):
    objects = []
    scene_map_triangle_mesh = self.map_triangle_mesh
    scene_map_translation = self.mesh_translation
    scene_map_rotation = self.mesh_rotation

    for info in detections:
      mobj = self.tracker.createObject(detectionType, info, when, camera, self.persist_attributes.get(detectionType, {}))
      mobj.map_triangle_mesh = scene_map_triangle_mesh
      mobj.map_translation = scene_map_translation
      mobj.map_rotation = scene_map_rotation
      objects.append(mobj)
    return objects

  def _convertPixelBoundingBoxToMeters(self, obj, camera):
    if 'bounding_box' not in obj and 'bounding_box_px' in obj:
      x, y, w, h = (obj['bounding_box_px'][key] for key in ['x', 'y', 'width', 'height'])
      agnosticx, agnosticy, agnosticw, agnostich = self._computePixelsToMeterPlane(
        x, y, w, h, camera.pose.intrinsics.intrinsics, camera.pose.intrinsics.distortion
      )
      obj['bounding_box'] = {'x': agnosticx, 'y': agnosticy, 'width': agnosticw, 'height': agnostich}
    return

  def processCameraData(self, jdata, when=None, ignoreTimeFlag=False):
    camera_id = jdata['id']
    camera = None

    if not when:
      if ignoreTimeFlag:
        when = get_epoch_time()
      else:
        when = get_epoch_time(jdata['timestamp'])

    if camera_id in self.cameras:
      camera = self.cameras[camera_id]
      if 'frame_rate' in jdata:
        self.ref_camera_frame_rate = min(jdata['frame_rate'], self.ref_camera_frame_rate) if self.ref_camera_frame_rate is not None else jdata["frame_rate"]
    else:
      log.error("Unknown camera", camera_id, self.cameras)
      return False

    if not hasattr(camera, 'pose'):
      log.info("DISCARDING: camera has no pose")
      return True
    for detection_type, detections in jdata['objects'].items():
      if "intrinsics" not in jdata:
        for parent_obj in detections:
          self._convertPixelBoundingBoxToMeters(parent_obj, camera)
          for key in parent_obj.get('sub_detections', []):
            for obj in parent_obj[key]:
              self._convertPixelBoundingBoxToMeters(obj, camera)
      objects = self._createMovingObjectsForDetection(detection_type, detections, when, camera)
      self._finishProcessing(detection_type, when, objects)
    return True

  def processSceneData(self, jdata, child, cameraPose,
                       detectionType, when=None):
    new = jdata['objects']

    if 'frame_rate' in jdata:
      self.ref_camera_frame_rate = min(jdata['frame_rate'], self.ref_camera_frame_rate) if self.ref_camera_frame_rate is not None else jdata["frame_rate"]

    objects = []
    child_objects = []
    for info in new:
      if 'lat_long_alt' in info:
        if 'translation' in info:
          log.warn("Input data must have only one of 'lat_long_alt' and 'translation'")
          return True
        info['translation'] = convertLLAToECEF(info.pop('lat_long_alt'))
      translation = Point(info['translation'])
      translation = np.hstack([translation.asNumpyCartesian, [1]])
      translation = np.matmul(cameraPose.pose_mat, translation)
      info['translation'] = translation[:3]

      # Remove reid vector from the object info as tracker does not support reid from scene hierarchy
      if 'reid' in info:
        info.pop('reid')

      mobj = self.tracker.createObject(detectionType, info, when, child, self.persist_attributes.get(detectionType, {}))
      log.debug("RX SCENE OBJECT",
              "id=%s" % (mobj.oid), mobj.sceneLoc)
      if child.retrack:
        objects.append(mobj)
      else:
        child_objects.append(mobj)

    self._finishProcessing(detectionType, when, objects, child_objects)
    return True
  
  distance_threshold = 1  # meters
  def clusterObjects(self, objects, distance_threshold):
    """Cluster objects based on their spatial proximity using a simple distance threshold."""
    log.debug("Clustering %d objects with threshold %.2f meters" % (len(objects), distance_threshold))
    clustered = []
    objects_count = len(objects)
    close_pairs = []
    if objects_count >= 2:
      for i in range(objects_count):
        for j in range(i + 1, objects_count):
          if objects[i].category == objects[j].category:
            dist = np.sqrt((objects[i].sceneLoc.as2Dxy.x - objects[j].sceneLoc.as2Dxy.x)**2 + 
                          (objects[i].sceneLoc.as2Dxy.y - objects[j].sceneLoc.as2Dxy.y)**2)
            if dist < distance_threshold:
              close_pairs.append((i, j, dist, objects[i].category))
        clustered.append(objects[i])
      objects[:] = clustered
    return

  def finishProcessing(self, detectionType, when, objects, already_tracked_objects=[]):
    self.updateVisible(objects)
    self.clusterObjects(objects, self.distance_threshold)
    self.tracker.trackObjects(objects, already_tracked_objects, when, [detectionType],
                              self.ref_camera_frame_rate,
                              self.max_unreliable_time,
                              self.non_measurement_time_dynamic,
                              self.non_measurement_time_static,
                              self.use_tracker)
    self._updateEvents(detectionType, when)
    return

  def _updateSensorObjects(self, name, sensor, objects=None):
    if not hasattr(sensor, 'value'):
      return

    if objects is None:
      objects = itertools.chain.from_iterable(sensor.objects.values())

    for obj in objects:
      if name not in obj.chain_data.sensors:
        obj.chain_data.sensors[name] = []
      ts_str = get_iso_time(sensor.lastWhen)
      existing = [x[0] for x in obj.chain_data.sensors[name]]
      if ts_str not in existing:
        obj.chain_data.sensors[name].append((ts_str, sensor.value))
    return

  def processSensorData(self, jdata, when):
    sensor_id = jdata['id']
    sensor = None

    if sensor_id in self.sensors:
      sensor = self.sensors[sensor_id]
    else:
      log.error("Unknown sensor", sensor_id, self.sensors)
      return False

    if hasattr(sensor, 'lastWhen') and sensor.lastWhen is not None and when <= sensor.lastWhen:
      log.info("DISCARDING PAST DATA", sensor_id, when)
      return True

    self.events = {}
    old_value = getattr(sensor, 'value', None)
    cur_value = jdata['value']
    self.events['value'] = [(sensor_id, sensor)]
    sensor.value = cur_value
    sensor.lastValue = old_value
    sensor.lastWhen = when
    self._updateSensorObjects(sensor_id, sensor)

    return True

  def _updateEvents(self, detectionType, now):
    self.events = {}
    now_str = get_iso_time(now)
    curObjects = self.tracker.currentObjects(detectionType)
    for obj in curObjects:
      obj.chain_data.publishedLocations.insert(0, obj.sceneLoc)

    self._updateRegionEvents(detectionType, self.regions, now, now_str, curObjects)
    self._updateRegionEvents(detectionType, self.sensors, now, now_str, curObjects)

    self._updateTripwireEvents(detectionType, now, curObjects)
    return

  def _updateTripwireEvents(self, detectionType, now, curObjects):
    for key in self.tripwires:
      tripwire = self.tripwires[key]
      tripwireObjects = tripwire.objects.get(detectionType, [])
      objects = []
      for obj in curObjects:
        age = now - obj.when
        if obj.frameCount > 3 \
           and len(obj.chain_data.publishedLocations) > 1:
          d = tripwire.lineCrosses(Line(obj.chain_data.publishedLocations[0].as2Dxy,
                                        obj.chain_data.publishedLocations[1].as2Dxy))
          if d != 0:
            event = TripwireEvent(obj, -d)
            objects.append(event)

      if len(tripwireObjects) != len(objects) \
         and now - tripwire.when > DEBOUNCE_DELAY:
        log.debug("TRIPWIRE EVENT", tripwireObjects, len(objects))
        tripwire.objects[detectionType] = objects
        tripwire.when = now
        if 'objects' not in self.events:
          self.events['objects'] = []
        self.events['objects'].append((key, tripwire))
    return

  def _updateRegionEvents(self, detectionType, regions, now, now_str, curObjects):
    updated = set()
    for key in regions:
      region = regions[key]
      regionObjects = region.objects.get(detectionType, [])
      objects = []
      for obj in curObjects:
        # When tracker is disabled, skip the frameCount check and consider all objects;
        # otherwise, only consider objects with frameCount > 3 as reliable.
        if (obj.frameCount > 3 or not self.use_tracker) \
           and (region.isPointWithin(obj.sceneLoc) or self.isIntersecting(obj, region)):
          objects.append(obj)

      cur = set(x.gid for x in objects)
      prev = set(x.gid for x in regionObjects)
      new = cur - prev
      old = prev - cur
      newObjects = [x for x in objects if x.gid in new]
      for obj in newObjects:
        if key not in obj.chain_data.regions:
          obj.chain_data.regions[key] = {'entered': now_str}
          updated.add(key)

      # For sensors add the current sensor value to any new objects
      if hasattr(region, 'value') and region.singleton_type=="environmental":
        for obj in newObjects:
          obj.chain_data.sensors[key] = []
        self._updateSensorObjects(key, region, newObjects)

      if (len(new) or len(old)) and now - region.when > DEBOUNCE_DELAY:
        log.debug("REGION EVENT", key, now_str, regionObjects, len(objects))
        entered = []
        for obj in objects:
          if obj.gid in new and key in obj.chain_data.regions:
            entered.append(obj)
        if not hasattr(region, 'entered'):
          region.entered = {}
        region.entered[detectionType] = entered

        exited = []
        for obj in regionObjects:
          if obj.gid in old:
            if key in obj.chain_data.regions:
              entered = get_epoch_time(obj.chain_data.regions[key]['entered'])
              dwell = now - entered
              exited.append((obj, dwell))
            obj.chain_data.regions.pop(key, None)
        if not hasattr(region, 'exited'):
          region.exited = {}
        region.exited[detectionType] = exited

        region.objects[detectionType] = objects
        updated.add(key)
        region.when = now
        if 'objects' not in self.events:
          self.events['objects'] = []
        self.events['objects'].append((key, region))
        if len(cur) != len(prev):
          if 'count' not in self.events:
            self.events['count'] = []
          self.events['count'].append((key, region))

    return updated

  def isIntersecting(self, obj, region):
    if not region.compute_intersection:
      return False

    if region.mesh is None:
      createRegionMesh(region)

    try:
      createObjectMesh(obj)
    except ValueError as e:
      log.info(f"Error creating object mesh for intersection check: {e}")
      return False

    return obj.mesh.is_intersecting(region.mesh)

  def _updateVisible(self, curObjects):
    """! Update the visibility of objects from cameras in the scene."""
    for obj in curObjects:
      vis = []

      for sname in self.cameras:
        camera = self.cameras[sname]
        if hasattr(camera, 'pose') and hasattr(camera.pose, 'regionOfView') \
           and camera.pose.regionOfView.isPointWithin(obj.sceneLoc):
          vis.append(camera.cameraID)

      obj.visibility = vis
    return

  @classmethod
  def deserialize(cls, data):
    tracker_config = data.get('tracker_config', [])
    scene = cls(data['name'], data.get('map', None), data.get('scale', None),
                *tracker_config)
    scene.uid = data['uid']
    scene.mesh_translation = data.get('mesh_translation', None)
    scene.mesh_rotation = data.get('mesh_rotation', None)
    scene.use_tracker = data.get('use_tracker', True)
    scene.output_lla = data.get('output_lla', None)
    scene.map_corners_lla = data.get('map_corners_lla', None)
    scene.retrack = data.get('retrack', True)
    scene.regulated_rate = data.get('regulated_rate', None)
    scene.external_update_rate = data.get('external_update_rate', None)
    scene.persist_attributes = data.get('persist_attributes', {})
    if 'cameras' in data:
      scene.updateCameras(data['cameras'])
    if 'regions' in data:
      scene._updateRegions(scene.regions, data['regions'])
    if 'tripwires' in data:
      scene._updateTripwires(data['tripwires'])
    if 'sensors' in data:
      scene._updateRegions(scene.sensors, data['sensors'])
    if 'children' in data:
      scene.children = [x['name'] for x in data['children']]
    if 'parent' in data:
      scene.parent = data['parent']
    if 'transform' in data:
      scene.cameraPose = CameraPose(data['transform'], None)
    if 'tracker_config' in data:
      tracker_config = data['tracker_config']
      scene.updateTracker(tracker_config[0], tracker_config[1], tracker_config[2])
    # Access the property to trigger initialization
    _ = scene.trs_xyz_to_lla
    return scene

  def _updateChildren(self, newChildren):
    self.children = [x['name'] for x in newChildren]
    return

  def updateCameras(self, newCameras):
    old = set(self.cameras.keys())
    new = set([x['uid'] for x in newCameras])
    for cameraData in newCameras:
      camID = cameraData['uid']
      self.cameras[camID] = Camera(camID, cameraData, resolution=cameraData['resolution'])
    deleted = old - new
    for camID in deleted:
      self.cameras.pop(camID)
    return

  def _updateRegions(self, existingRegions, newRegions):
    old = set(existingRegions.keys())
    new = set([x['uid'] for x in newRegions])
    for regionData in newRegions:
      region_uuid = regionData['uid']
      region_name = regionData['name']
      if region_uuid in existingRegions:
        existingRegions[region_uuid].updatePoints(regionData)
        existingRegions[region_uuid].updateSingletonType(regionData)
        existingRegions[region_uuid].updateVolumetricInfo(regionData)
        existingRegions[region_uuid].name = region_name
      else:
        existingRegions[region_uuid] = Region(region_uuid, region_name, regionData)
    deleted = old - new
    for region_uuid in deleted:
      existingRegions.pop(region_uuid)
    return

  def _updateTripwires(self, newTripwires):
    old = set(self.tripwires.keys())
    new = set([x['uid'] for x in newTripwires])
    for tripwireData in newTripwires:
      tripwire_uuid = tripwireData["uid"]
      tripwire_name = tripwireData['name']
      self.tripwires[tripwire_uuid] = Tripwire(tripwire_uuid, tripwire_name, tripwireData)
    deleted = old - new
    for tripwireID in deleted:
      self.tripwires.pop(tripwireID)
    return

  def _computePixelsToMeterPlane(self, x,y,width,height, cameraintrinsicsmatrix, distortionmatrix):
    """
    ! Convert pixel coordinates to undistorted normalized image coordinates using camera intrinsics and distortion matrices.
      Compute the undistorted coordinates for the given pixel point and its opposite corner.

    @param   x                        X-coordinate of the top-left corner of the pixel region (in pixels).
    @param   y                        Y-coordinate of the top-left corner of the pixel region (in pixels).
    @param   width                    Width of the pixel region (in pixels).
    @param   height                   Height of the pixel region (in pixels).
    @param   cameraintrinsicsmatrix   Camera intrinsics matrix as a numpy array.
    @param   distortionmatrix         Distortion coefficients matrix as a numpy array.

    @return  Tuple containing:
         - X-coordinate of the undistorted point (in normalized image coordinates).
         - Y-coordinate of the undistorted point (in normalized image coordinates).
         - Width of the undistorted region (in normalized image coordinates).
         - Height of the undistorted region (in normalized image coordinates).
    """
    pxpoint = np.array([x,y], dtype='float64').reshape(-1, 1, 2)
    pt = cv2.undistortPoints(pxpoint, cameraintrinsicsmatrix, distortionmatrix)
    oppositepxpoint = np.array([x + width, y + height], dtype='float64').reshape(-1, 1, 2)
    opppt = cv2.undistortPoints(oppositepxpoint, cameraintrinsicsmatrix, distortionmatrix)
    return pt[0][0][0], pt[0][0][1], opppt[0][0][0] - pt[0][0][0], opppt[0][0][1] - pt[0][0][1]

  @property
  def trs_xyz_to_lla(self) -> Optional[np.ndarray]:
    """
    Get the transformation matrix from TRS (Translation, Rotation, Scale) coordinates to LLA (Latitude, Longitude, Altitude) coordinates.

    The matrix is calculated lazily on first access and cached for subsequent calls.
    """
    if self._trs_xyz_to_lla is None and self.output_lla and self.map_corners_lla is not None:
      mesh_corners_xyz = getMeshAxisAlignedProjectionToXY(self.map_triangle_mesh)
      self._trs_xyz_to_lla = calculateTRSLocal2LLAFromSurfacePoints(mesh_corners_xyz, self.map_corners_lla)
    return self._trs_xyz_to_lla

  def _invalidate_trs_xyz_to_lla(self):
    """
    Invalidate the cached transformation matrix from TRS to LLA coordinates.
    This method should be called when the scene geospatial mapping parameters change.
    """
    self._trs_xyz_to_lla = None
    return
