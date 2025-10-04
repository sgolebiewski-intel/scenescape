# SPDX-FileCopyrightText: (C) 2023 - 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
import os

from django import forms
from django.conf import settings
from django.db.models import Q
from django.forms import ModelForm, ValidationError

from manager.models import SingletonSensor, Scene, SceneImport, Cam, ChildScene
from manager.validators import validate_zip_file
from scene_common.options import SINGLETON_CHOICES, AREA_CHOICES

class CamCalibrateForm(forms.ModelForm):
  class Meta:
    model = Cam
    fields = [
      'name', 'sensor_id', 'scene', 'command', 'camerachain', 'threshold', 'aspect',
      'cv_subsystem', 'transforms', 'transform_type', 'width', 'height',
      'intrinsics_fx', 'intrinsics_fy', 'intrinsics_cx', 'intrinsics_cy',
      'distortion_k1', 'distortion_k2', 'distortion_p1', 'distortion_p2', 'distortion_k3',
      'sensor', 'sensorchain', 'sensorattrib', 'window', 'usetimestamps', 'virtual', 'debug',
      'override_saved_intrinstics', 'frames', 'stats', 'waitforstable', 'preprocess', 'realtime',
      'faketime', 'modelconfig', 'rootcert', 'cert', 'cvcores', 'ovcores', 'unwarp', 'ovmshost',
      'framerate', 'maxcache', 'filter', 'disable_rotation', 'maxdistance', 'camera_pipeline'
    ]

  def __init__(self, *args, **kwargs):
    self.advanced_fields = ['cv_subsystem', 'modelconfig' ]
    self.unsupported_fields = ['threshold', 'aspect', 'sensor', 'sensorchain',
                            'sensorattrib', 'window', 'usetimestamps', 'virtual', 'debug', 'override_saved_intrinstics',
                            'frames', 'stats', 'waitforstable', 'preprocess', 'realtime', 'faketime',
                            'rootcert', 'cert', 'cvcores', 'ovcores', 'unwarp', 'ovmshost', 'framerate', 'maxcache',
                            'filter', 'disable_rotation', 'maxdistance']
    self.kubernetes_fields = ['command', 'camerachain', 'camera_pipeline'] + self.advanced_fields
    super().__init__(*args, **kwargs)
    for field in self.unsupported_fields:
      del self.fields[field]
    if not settings.KUBERNETES_SERVICE_HOST:
      for field in self.kubernetes_fields:
        del self.fields[field]
      self.fields['distortion_k1'].widget = forms.TextInput(attrs={'readonly': 'readonly'})
      self.fields['distortion_k2'].widget = forms.TextInput(attrs={'readonly': 'readonly'})
      self.fields['distortion_p1'].widget = forms.TextInput(attrs={'readonly': 'readonly'})
      self.fields['distortion_p2'].widget = forms.TextInput(attrs={'readonly': 'readonly'})
      self.fields['distortion_k3'].widget = forms.TextInput(attrs={'readonly': 'readonly'})
    self.fields['intrinsics_cx'].widget = forms.TextInput(attrs={'disabled': 'disabled'})
    self.fields['intrinsics_cy'].widget = forms.TextInput(attrs={'disabled': 'disabled'})
    self.fields['transform_type'].widget = forms.HiddenInput()
    self.fields['sensor_id'].label = "Camera ID"
    if settings.KUBERNETES_SERVICE_HOST:
      self.fields['camera_pipeline'].widget = forms.Textarea(attrs={
          'rows': 6,
          'cols': 80,
          'style': 'resize: vertical; white-space: pre-wrap; word-wrap: break-word;',
          'placeholder': 'Camera pipeline will be generated automatically when you click "Generate Pipeline Preview" button or save the form.'
      })

class ROIForm(forms.Form):
  rois = forms.CharField()
  tripwires = forms.CharField()

class SingletonCreateForm(forms.ModelForm):
  class Meta:
    model = SingletonSensor
    fields = ['sensor_id', 'name', 'scene', 'singleton_type']
    widgets = {
      'child_type' : forms.RadioSelect(choices=SINGLETON_CHOICES)
    }


class SingletonDetailsForm(ModelForm):
  class Meta:
    model = SingletonSensor
    fields = ('__all__')

class SceneImportForm(ModelForm):
  class Meta:
    model = SceneImport
    fields = ('__all__')

class SceneUpdateForm(ModelForm):
  class Meta:
    model = Scene
    fields = ('__all__')

  def checkDuplicatePolycamData(self, zip_file, field_name):
    file_hash = hashlib.sha256(zip_file.read()).hexdigest()
    if self.instance.polycam_hash == file_hash:
      self.add_error(field_name, "Uploading a duplicate zip file is not allowed. Please clear the field and upload again.")
    else:
      self.instance.polycam_hash = file_hash
    return

  def clean(self):
    cleaned_data = super().clean()
    new_polycam_file = cleaned_data.get('polycam_data')
    new_map_file = cleaned_data.get('map')
    map_file_ext = os.path.splitext(self.instance.map.name)[1].lower() if self.instance.map else None

    if new_map_file:
      map_file_ext = os.path.splitext(new_map_file.name)[1].lower()
      if map_file_ext == ".zip":
        self.checkDuplicatePolycamData(new_map_file, 'map')
        validate_zip_file(new_map_file)
    if new_polycam_file:
      self.checkDuplicatePolycamData(new_polycam_file, 'polycam_data')
      validate_zip_file(new_polycam_file, map_file_ext == ".glb")
    else:
      self.instance.polycam_hash = ""

    if cleaned_data['output_lla'] and (cleaned_data.get('map_corners_lla') is None or cleaned_data.get('map') is None):
      raise forms.ValidationError("If 'Output geospatial coordinates' is enabled then map corners LLA and map file are required.")
    return cleaned_data

class SingletonForm(forms.Form):
  area = forms.ChoiceField(choices=AREA_CHOICES,
                           widget=forms.RadioSelect())
  name = forms.CharField()
  sensor_id = forms.CharField()
  scene = forms.ModelChoiceField(queryset=Scene.objects.all())
  sensor_x = forms.CharField()
  sensor_y = forms.CharField()
  sensor_r = forms.CharField(required=False)
  rois = forms.CharField(required=False)
  singleton_type = forms.ChoiceField(choices=SINGLETON_CHOICES)
  sectors = forms.CharField(required=False)

  def clean(self):
    cleaned_data = super().clean()

    rois = json.loads(cleaned_data["rois"])
    area = cleaned_data["area"]
    if area == "poly":
      if len(rois) < 1:
        raise ValidationError("Please draw a custom region (polygon) with at least 3 vertices")
      if len(rois[0]["points"]) < 3:
        raise ValidationError("The custom region (polygon) must have at least 3 vertices")
      for point in rois[0]["points"]:
        try:
          for coord in point:
            float(coord)
        except ValueError:
          raise ValidationError("The polygon vertex coordinates must be floating point numbers.")
    return cleaned_data

class CamCreateForm(forms.ModelForm):
  class Meta:
    model = Cam
    fields = ['sensor_id', 'name', 'scene']
    labels = {
      'sensor_id': 'Camera ID',
    }

    if settings.KUBERNETES_SERVICE_HOST:
      fields.extend(['command', 'camerachain'])

class ChildSceneForm(forms.ModelForm):
  class Meta:
    model = ChildScene
    child_types = [
      ('local', 'local'),
      ('remote', 'remote')
    ]
    fields = ['child_type', 'child', 'remote_child_id', 'child_name', 'parent', 'host_name', \
          'mqtt_username', 'mqtt_password', 'retrack', 'transform_type', \
          'transform1', 'transform2', 'transform3', 'transform4', \
          'transform5', 'transform6', 'transform7', 'transform8', \
          'transform9', 'transform10', 'transform11', 'transform12', \
          'transform13', 'transform14', 'transform15', 'transform16']
    widgets = {
      'child_type' : forms.RadioSelect(choices=child_types),
      'retrack': forms.CheckboxInput(),
    }

  def __init__(self, *args, **kwargs):
    super(ChildSceneForm, self).__init__(*args, **kwargs)
    childScenes = ChildScene.objects.all()
    filteredScenes = Scene.objects.all()
    is_update = hasattr(self.instance, "parent")

    if is_update:
      parent = self.instance.parent
      self.fields['parent'].queryset = Scene.objects.filter(name=self.instance.parent)
      self.fields['child'].queryset = Scene.objects.filter(name=self.instance.child)
    else:
      parent = self.initial.get('parent', None)
      self.fields['parent'].queryset = Scene.objects.all()
      self.fields['child'].queryset = Scene.objects.none()

    # Filter out all the Scenes that have a parent and ones that create circular dependencies
    for childObj in childScenes:
      filteredScenes = filteredScenes.filter(~Q(name=childObj.child))
      if self._isParentInHierarchy(parent, childObj):
        filteredScenes = filteredScenes.filter(~Q(name=childObj.parent))

    self.fields['child'].queryset |= filteredScenes
    return

  def _isParentInHierarchy(self, parent, child):
    stack = [child]
    while stack:
      current_child = stack.pop()
      if parent == current_child.child:
        return True
      for childObj in ChildScene.objects.filter(parent=current_child.child):
        stack.append(childObj)
    return False

  def clean(self):
    cleaned_data = super().clean()
    if cleaned_data['child_type'] == 'remote':
      if cleaned_data['child_name'] == cleaned_data['parent'].name:
        self.add_error('child_name', "Parent and child cannot have same name.")
      elif cleaned_data['remote_child_id'] == cleaned_data['parent'].id:
        self.add_error('remote_child_id', "Parent and child cannot have same id.")
      elif Scene.objects.filter(id=cleaned_data['remote_child_id']).exists():
        self.add_error('remote_child_id', "Scene with this id already exists. Create a local child scene.")
    return cleaned_data
