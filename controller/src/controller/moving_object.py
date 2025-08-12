# SPDX-FileCopyrightText: (C) 2021 - 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import base64
import datetime
import struct
import warnings
from dataclasses import dataclass
from threading import Lock
from typing import Dict, List

import cv2
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation

from scene_common.geometry import DEFAULTZ, Line, Point, Rectangle
from scene_common.options import TYPE_1, TYPE_2
from scene_common.transform import normalize, rotationToTarget

warnings.simplefilter('ignore', np.RankWarning)

APRILTAG_HOVER_DISTANCE = 0.5
DEFAULT_EDGE_LENGTH = 1.0
DEFAULT_TRACKING_RADIUS = 2.0
LOCATION_LIMIT = 20
SPEED_THRESHOLD = 0.1

@dataclass
class ChainData:
  regions: Dict
  publishedLocations: List[Point]
  sensors: Dict
  persist: Dict

class Chronoloc:
  def __init__(self, point: Point, when: datetime, bounds: Rectangle):
    if not point.is3D:
      point = Point(point.x, point.y, DEFAULTZ)
    self.point = point
    self.when = when
    self.bounds = bounds
    return

class Vector:
  def __init__(self, camera, point, when):
    if not point.is3D:
      point = Point(point.x, point.y, DEFAULTZ)
    self.camera = camera
    self.point = point
    self.last_seen = when
    return

  def __repr__(self):
    origin = None
    if hasattr(self.camera, 'pose'):
      origin = str(self.camera.pose.translation.log)
    return "Vector: %s %s %s" % \
      (origin, str(self.point.log), self.last_seen)

class MovingObject:
  ## Fields that are specific to a single detection:
  # 'tracking_radius', 'camera', 'boundingBox', 'boundingBoxPixels',
  # 'confidence', 'oid', 'reidVector', 'visibility'

  ## Fields that really are shared across the chain:
  # 'gid', 'frameCount', 'velocity', 'intersected',
  # 'first_seen', 'category'

  gid_counter = 0
  gid_lock = Lock()

  def __init__(self, info, when, camera, min_size_ratio, max_size_ratio):
    self.chain_data = None
    self.size = None
    self.buffer_size = None
    self.tracking_radius = DEFAULT_TRACKING_RADIUS
    self.shift_type = TYPE_1
    self.project_to_map = False
    self.map_triangle_mesh = None
    self.map_translation = None
    self.map_rotation = None
    self.rotation_from_velocity = False

    # Only ratio-based filtering config is injected
    self.min_size_ratio = min_size_ratio
    self.max_size_ratio = max_size_ratio

    self.first_seen = when
    self.last_seen = None
    self.camera = camera
    self.info = info.copy()

    self.category = self.info.get('category', 'object')
    self.boundingBox = None
    if 'bounding_box_px' in self.info:
      self.boundingBoxPixels = Rectangle(self.info['bounding_box_px'])
      self.info.pop('bounding_box_px')
      if not 'bounding_box' in self.info:
        agnostic = self.camera.pose.intrinsics.infer3DCoordsFrom2DDetection(self.boundingBoxPixels)
        self.boundingBox = agnostic
    if 'bounding_box' in self.info:
      self.boundingBox = Rectangle(self.info['bounding_box'])
      self.info.pop('bounding_box')
    self.confidence = self.info['confidence'] if 'confidence' in self.info else None
    self.oid = self.info['id']
    self.info.pop('id')
    self.gid = None
    self.frameCount = 1
    self.velocity = None
    self.location = None
    self.rotation = np.array([0, 0, 0, 1]).tolist()
    self.intersected = False
    self.reidVector = None
    reid = self.info.get('reid', None)
    if reid is not None:
      self._decodeReIDVector(reid)
    return

  def _decodeReIDVector(self, reid):
    try:
      vector = base64.b64decode(reid)
      self.reidVector = np.array(struct.unpack("256f", vector)).reshape(1, -1)
      self.info.pop('reid')
    except TypeError:
      if type(reid) == list:
        self.reidVector = reid
    return

  def setPersistentAttributes(self, info, persist_attributes):
    if self.chain_data is None:
      self.chain_data = ChainData(regions={}, publishedLocations=[], sensors={}, persist={})
    for attribute in persist_attributes:
      attr, sub_attrs = (list(attribute.items())[0] if isinstance(attribute, dict) else (attribute, None))
      if attr in info:
        result = info[attr][0] if isinstance(info[attr], list) and info[attr] else info[attr]
        self.chain_data.persist.setdefault(attr, {})
        if sub_attrs:
          for sub_attr in sub_attrs.split(','):
            if sub_attr in result:
              self.chain_data.persist[attr][sub_attr] = result[sub_attr]
        else:
          self.chain_data.persist[attr] = result
    return

  def setGID(self, gid):
    if self.chain_data is None:
      self.chain_data = ChainData(regions={}, publishedLocations=[], sensors={}, persist={})
    self.gid = gid
    self.first_seen = self.when
    return

  def setPrevious(self, otherObj):
    # log.debug("MATCHED", self.__class__.__name__,
    #     "id=%i/%i:%i" % (otherObj.gid, otherObj.oid, self.oid),
    #     otherObj.sceneLoc, self.sceneLoc)
    self.location = [self.location[0]] + otherObj.location[:LOCATION_LIMIT - 1]

    persistent_attributes = self.chain_data.persist if self.chain_data else {}
    for attr, new_value in persistent_attributes.items():
      old_value = otherObj.chain_data.persist.get(attr, None)
      if isinstance(new_value, dict) and isinstance(old_value, dict):
        new_value.update({k: v for k, v in old_value.items() if v is not None})
      persistent_attributes[attr] = new_value if new_value is not None else old_value

    self.chain_data = otherObj.chain_data
    self.chain_data.persist = persistent_attributes

    # FIXME - should these fields be part of chain_data?
    self.gid = otherObj.gid
    self.first_seen = otherObj.first_seen
    self.frameCount = otherObj.frameCount + 1

    del self.chain_data.publishedLocations[LOCATION_LIMIT:]
    
    return

  def inferRotationFromVelocity(self):
    if self.rotation_from_velocity and self.velocity:
      speed = np.linalg.norm([self.velocity.x, self.velocity.y, self.velocity.z])
      if speed > SPEED_THRESHOLD:
        velocity = np.array([self.velocity.x, self.velocity.y, self.velocity.z])
        velocity = normalize(velocity)
        direction = np.array([1, 0, 0])
        self.rotation = rotationToTarget(direction, velocity).as_quat().tolist()

  @property
  def camLoc(self):
    """Object location in camera coordinate system"""
    bounds = self.boundingBox
    if self.shift_type == TYPE_2:
      if not hasattr(self, 'baseAngle'):
        self._projectBounds()
      return Point(bounds.x + bounds.width / 2,
                 bounds.y + bounds.height - (bounds.height / 2) * (self.baseAngle / 90))
    else:
      pt = Point(bounds.x + bounds.width / 2, bounds.y2)
      if bounds.origin.is3D:
        pt = Point(pt.x, pt.y, bounds.origin.z)
    return pt

  def mapObjectDetectionToWorld(self, info, when, camera):
    """Maps detected object pose to world coordinate system"""
    if info is not None and 'size' in info:
      self.size = info['size']
    if info is not None and 'translation' in info:
      self.orig_point = Point(info['translation'])
      if camera and hasattr(camera, 'pose'):
        if 'rotation' in info:
          rotation_as_matrix = Rotation.from_quat(np.array(info['rotation'])).as_matrix()
          info['rotation'] = list(Rotation.from_matrix(np.matmul(
            camera.pose.pose_mat[:3, :3],
            rotation_as_matrix)).as_quat())
          self.rotation = info['rotation']
        if self.project_to_map:
          # Always use 4-point surface projection for 3D bounding boxes
          world_point = camera.pose.cameraPointToWorldPoint(Point(info['translation']))
          projected_translation, projected_rotation, projected_size = self.project_vertices_to_surface(
            [world_point.x, world_point.y, world_point.z],
            info['rotation'],
            info['size']
          )
          bottom_center_point = [projected_translation[0], projected_translation[1], 0.0]
          self.orig_point = Point(bottom_center_point)
          info['translation'] = projected_translation
          info['rotation'] = projected_rotation
          info['size'] = projected_size
          self.rotation = info['rotation']
          self.size = info['size']
        else:
          # Use standard camera-to-world transformation
          self.orig_point = camera.pose.cameraPointToWorldPoint(Point(info['translation']))
          self.size = info['size']
    else:
      if camera and hasattr(camera, 'pose'):
        self.orig_point = camera.pose.cameraPointToWorldPoint(self.camLoc)
        if not self.camLoc.is3D:
          line1 = Line(camera.pose.translation, self.orig_point)
          line2 = Line(self.orig_point, Point(np.mean([self.size[0], self.size[1]]) / 2, line1.angle, 0, polar=True), relative=True)
          self.orig_point = line2.end
    self.location = [Chronoloc(self.orig_point, when, self.boundingBox)]
    self.vectors = [Vector(camera, self.orig_point, when)]
    if hasattr(self, 'buffer_size') and self.buffer_size is not None:
      self.size = [x + y for x, y in zip(self.size, self.buffer_size)]
    return

  @property
  def sceneLoc(self):
    """Object location in world coordinate system"""
    if self.intersected:
      return self.adjusted[1]
    if not hasattr(self, 'location') or not self.location:
      self._projectBounds()
      self.mapObjectDetectionToWorld(self.info, self.first_seen, self.camera)
    return self.location[0].point

  def _projectBounds(self):
    if hasattr(self.camera, "pose") and self.boundingBox:
      self.bbMeters, self.bbShadow, self.baseAngle = \
        self.camera.pose.projectBounds(self.boundingBox)
      if self.size is None:
        self.size = [self.bbMeters.width, self.bbMeters.width, self.bbMeters.height]
    return

  @property
  def when(self):
    return self.location[0].when

  def __repr__(self):
    return "%s: %s/%s %s %s vectors: %s" % \
      (self.__class__.__name__,
       str(self.gid), self.oid,
       str(self.sceneLoc.log),
       str(self.location[1].point.log) if len(self.location) > 1 else None,
       str(self.vectors))

  @classmethod
  def createSubclass(cls, subclassName, methods=None, additionalAttributes=None):
    """ Dynamically creates a subclass with specified methods and additional attributes.
    @param    subclassName              The name of the new subclass.
    @param    methods                   A dictionary of methods to add to the subclass.
    @param    additionalAttributes     A dictionary of additional attributes for the subclass.
    @returns  class                     The dynamically created subclass.
    """

    classDict = {'baseClass': cls}
    classDict.update('')
    if methods:
      classDict.update(methods)

    newClass = type(subclassName, (cls,), classDict)
    def custom_init(self, *args, **kwargs):
      cls.__init__(self, *args, **kwargs)
      if additionalAttributes:
        classDict.update(additionalAttributes)

    setattr(newClass, '__init__', custom_init)
    return newClass

  ### Below section is for methods that support native tracker or tracker debugger
  def displayIntersections(self, img, ms, pad):
    # for o1 in range(len(self.vectors) - 1):
    #   org1 = self.vectors[o1]
    #   pt = org1.point
    #   l1 = (org1.camera.pose.translation, pt)
    #   for o2 in range(o1 + 1, len(self.vectors)):
    #     org2 = self.vectors[o2]
    #     pt = org2.point
    #     l2 = (org2.camera.pose.translation, pt)
    #     point = scenescape.intPoint(scenescape.lineIntersection(l1, l2))
    #     cv2.line(img, (point[0] - 5, point[1]), (point[0] + 5, point[1]), (128,128,128), 2)
    #     cv2.line(img, (point[0], point[1] - 5), (point[0], point[1] + 5), (128,128,128), 2)
    #     label = "%i" % (self.gid)
    #     cv2.putText(img, label, point, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 3)
    #     cv2.putText(img, label, point, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
    for org in self.vectors:
      pt1 = ms(pad, org.camera.pose.translation)
      pt2 = ms(pad, org.point)
      point = Point((pt1.x + (pt2.x - pt1.x) / 2, pt1.y + (pt2.y - pt1.y) / 2))
      label = "%i %0.3f,%0.3f" % (self.gid, org.point.x, org.point.y)
      cv2.putText(img, label, point.cv, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 3)
      cv2.putText(img, label, point.cv, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
    return

  def dump(self):
    dd = {
      'category': self.category,
      'bounding_box': self.boundingBox.asDict,
      'gid': self.gid,
      'frame_count': self.frameCount,
      'reid': self.reidVector,
      'first_seen': self.first_seen,
      'location': [{'point': (v.point.x, v.point.y, v.point.z),
                    'timestamp': v.when,
                    'bounding_box': v.bounds.asDict} for v in self.location],
      'vectors': [{'camera': v.camera.cameraID,
                   'point': (v.point.x, v.point.y, v.point.z),
                   'timestamp': v.last_seen} for v in self.vectors],
      'intersected': self.intersected,
      'scene_loc': self.sceneLoc.asNumpyCartesian.tolist(),
    }
    if 'reid' in dd and isinstance(dd['reid'], np.ndarray):
      vector = dd['reid'].flatten().tolist()
      vector = struct.pack("256f", *vector)
      vector = base64.b64encode(vector).decode('utf-8')
      dd['reid'] = vector
    if self.intersected:
      dd['adjusted'] = {'gid': self.adjusted[0],
                        'point': (self.adjusted[1].x, self.adjusted[1].y, self.adjusted[1].z)}
    return dd

  def load(self, info, scene):
    self.category = info['category']
    self.boundingBox = Rectangle(info['bounding_box'])
    self.gid = info['gid']
    self.frameCount = info['frame_count']
    self.reidVector = info['reid']
    if self.reidVector is not None:
      vector = base64.b64decode(self.reidVector)
      self.reidVector = np.array(struct.unpack("256f", vector)).reshape(1, -1)
    self.first_seen = info['first_seen']
    self.location = [Chronoloc(Point(v['point']), v['timestamp'], Rectangle(v['bounding_box']))
                     for v in info['location']]
    self.vectors = [Vector(scene.cameras[v['camera']], Point(v['point']), v['timestamp'])
                    for v in info['vectors']]
    if 'intersected' in info:
      self.intersected = info['intersected']
      if self.intersected:
        self.adjusted = [info['adjusted']['gid'], Point(info['adjusted']['point'])]
        if not self.adjusted[1].is3D:
          self.adjusted[1] = Point(self.adjusted[1].x, self.adjusted[1].y, DEFAULTZ)
    return

  def calculate_bottom_corners_world(self, world_object_center, world_rotation_quat, size):
    """Calculate the 4 bottom corners of the bounding box in world coordinates"""
    if hasattr(world_object_center, 'x'):
      center_x, center_y, center_z = world_object_center.x, world_object_center.y, world_object_center.z
    else:
      center_x, center_y, center_z = world_object_center[0], world_object_center[1], world_object_center[2]

    half_width = size[0] / 2.0   # x-axis (width)
    half_depth = size[1] / 2.0   # y-axis (depth)

    relative_corners = [
      [-half_width, -half_depth, 0],  # bottom-left-back
      [half_width, -half_depth, 0],   # bottom-right-back
      [half_width, half_depth, 0],    # bottom-right-front
      [-half_width, half_depth, 0]    # bottom-left-front
    ]

    from scipy.spatial.transform import Rotation
    rotation = Rotation.from_quat(world_rotation_quat)

    world_corners = []
    for corner in relative_corners:
      rotated_corner = rotation.apply(corner)
      world_corner = [
        center_x + rotated_corner[0],
        center_y + rotated_corner[1],
        center_z + rotated_corner[2]
      ]
      world_corners.append(world_corner)
    return world_corners

  def project_vertices_to_surface(self, world_translation, world_rotation_quat, size):
    """Project the object's actual bottom corners to the ground plane and fit the bounding rectangle to those points only. Scale height using the average of projected width/depth ratios."""
    try:
      # Step 1: Get the 4 bottom corners of the detected bounding box in world coordinates
      if hasattr(world_translation, 'x'):
        center = np.array([world_translation.x, world_translation.y, world_translation.z], dtype=float)
      else:
        center = np.array(world_translation, dtype=float)

      world_bottom_corners = self.calculate_bottom_corners_world(center, world_rotation_quat, size)

      # Step 2: Project each bottom corner to the ground plane (z=0) along the vector from the camera
      camera_pos = self.camera.pose.translation
      camera_world = np.array([camera_pos.x, camera_pos.y, camera_pos.z], dtype=float)
      world_bottom_corners_np = np.array(world_bottom_corners, dtype=float)
      projected_corners = np.empty((4, 3), dtype=float)
      for i in range(4):
        ray = world_bottom_corners_np[i] - camera_world
        if abs(ray[2]) < 1e-6:
          projected_corners[i] = [world_bottom_corners_np[i][0], world_bottom_corners_np[i][1], 0.0]
        else:
          t = (0.0 - camera_world[2]) / ray[2]
          projected_corners[i] = [camera_world[0] + t * ray[0], camera_world[1] + t * ray[1], 0.0]

      # Step 3: Fit a rectangle to the projected points (no expansion/rectification)
      points_2d = projected_corners[:, :2].astype(np.float32)
      rect = cv2.minAreaRect(points_2d)
      (cx, cy), (w, h), angle_deg = rect
      angle_rad = np.deg2rad(angle_deg)
      if w < h:
        w, h = h, w
        angle_rad += np.pi/2
      center_z = 0.0
      projected_center = np.array([cx, cy, center_z])

      # Step 4: Apply size ratio filtering (post-projection)
      width_ratio = w / size[0] if size[0] > 0 else 1.0
      depth_ratio = h / size[1] if size[1] > 0 else 1.0
      if not (self.min_size_ratio <= width_ratio <= self.max_size_ratio and self.min_size_ratio <= depth_ratio <= self.max_size_ratio):
        raise ValueError(f"Projected size ratio out of bounds: width_ratio={width_ratio}, depth_ratio={depth_ratio}")

      # Step 5: Scale height using the average of the width and depth ratios
      scale_factor = (width_ratio + depth_ratio) / 2.0
      scaled_height = size[2] * scale_factor

      # Step 6: Set rotation to match the optimal angle found for the inscribed rectangle (yaw only)
      rotation_obj = Rotation.from_euler('z', angle_rad, degrees=False)
      new_rotation = rotation_obj.as_quat().tolist()

      # Step 7: Set the new object center above the ground plane
      half_height = scaled_height / 2.0
      new_object_center = [projected_center[0], projected_center[1], 0.0 + half_height]
      new_size = [w, h, scaled_height]
      return new_object_center, new_rotation, new_size
    except (ValueError, IndexError, TypeError) as e:
      print(f"[DEBUG] Exception in project_vertices_to_surface: {e}")
      return world_translation, world_rotation_quat, size

  def filter_3d_size_ratio(self, size, reference_size=None):
    """Filter 3D object by size ratio, using configured min/max ratios. If reference_size is None, use asset size."""
    ref = reference_size if reference_size is not None else self.size
    if not ref or not size or len(ref) < 2 or len(size) < 2:
      return True  # Accept if not enough info
    width_ratio = size[0] / ref[0] if ref[0] > 0 else 1.0
    depth_ratio = size[1] / ref[1] if ref[1] > 0 else 1.0
    return self.min_size_ratio <= width_ratio <= self.max_size_ratio and self.min_size_ratio <= depth_ratio <= self.max_size_ratio

class ATagObject(MovingObject):
  def __init__(self, info, when, sensor):
    super().__init__(info, when, sensor)

    self.tag_id = "%s-%s-%s" % (info['category'], info['tag_family'], info['tag_id'])
    return

  def mapObjectDetectionToWorld(self, info, when, sensor):
    super().mapObjectDetectionToWorld(info, when, sensor)

    if not hasattr(sensor, 'pose'):
      return

    # Do the math to make the tag hover above the floor at hover_dist
    hover_dist = APRILTAG_HOVER_DISTANCE # Tag is this many meters above the floor

    # Scale the triangle down to a Z of hover_dist to find point above floor
    pt = sensor.pose.translation - self.orig_point
    if not pt.z == 0:
      pt = Point(hover_dist * pt.x / pt.z, hover_dist * pt.y / pt.z, hover_dist * pt.z / pt.z)
      pt = pt + self.orig_point
      self.orig_point = pt

    bbox = getattr(self, "boundingBox", None)
    self.location = [Chronoloc(self.orig_point, when, bbox)]
    self.vectors = [Vector(sensor, self.orig_point, when)]
    return

  def __repr__(self):
    rep = super().__repr__()
    rep += " %s" % (self.tag_id)
    return rep
