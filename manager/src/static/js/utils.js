// SPDX-FileCopyrightText: (C) 2024 - 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

"use strict";

import {
  FX,
  FY,
  CX,
  CY,
  K1,
  K2,
  P1,
  P2,
  K3,
  REST_URL,
  POINT_CORRESPONDENCE,
  EULER,
} from "/static/js/constants.js";

// Convert a point from pixels to meters
function pixelsToMeters(pixels, scale, scene_y_max) {
  var meters = [];

  // Scale-only in x
  meters[0] = parseFloat(pixels[0] / scale);

  // Move y axis to bottom and also scale
  meters[1] = parseFloat((scene_y_max - pixels[1]) / scale);

  if (pixels.length == 3) {
    // Leave z alone
    meters[2] = pixels[2].toFixed(scene_precision);
  }

  return meters;
}

// Convert a point from meters to pixels
function metersToPixels(meters, scale, scene_y_max) {
  var pixels = [];

  // Scale-only in x
  pixels[0] = Math.round(meters[0] * scale);

  // Move y axis to top and also scale
  pixels[1] = Math.round(scene_y_max - meters[1] * scale);

  // z, if provided, remains unchanged since it should be in meters already
  if (meters.length == 3) {
    pixels[2] = meters[2];
  }

  return pixels;
}

function compareIntrinsics(
  intrinsics,
  msgIntrinsics,
  distortion,
  msgDistortion,
) {
  if (
    intrinsics["fx"] === msgIntrinsics[FX] &&
    intrinsics["fy"] === msgIntrinsics[FY] &&
    intrinsics["cx"] === msgIntrinsics[CX] &&
    intrinsics["cy"] === msgIntrinsics[CY] &&
    distortion["k1"] === msgDistortion[K1] &&
    distortion["k2"] === msgDistortion[K2] &&
    distortion["p1"] === msgDistortion[P1] &&
    distortion["p2"] === msgDistortion[P2] &&
    distortion["k3"] === msgDistortion[K3]
  ) {
    return true;
  }
  return false;
}

const waitUntil = (condition, checkInterval, maxWaitTime) => {
  return new Promise((resolve, reject) => {
    let interval = setInterval(() => {
      if (condition()) {
        clearInterval(interval);
        clearTimeout(timeout);
        resolve();
      }
    }, checkInterval);

    let timeout = setTimeout(() => {
      clearInterval(interval);
      reject(new Error("Timeout exceeded"));
    }, maxWaitTime);
  });
};

function initializeOpencv() {
  return new Promise((resolve) => {
    if (cv.getBuildInformation?.() !== undefined) {
      // Already loaded
      resolve(true);
    } else {
      cv.onRuntimeInitialized = () => {
        resolve(true);
      };
    }
  });
}

// Responsive canvas implementation (handle browser window resizing)
// https://threejs.org/manual/#en/responsive
function resizeRendererToDisplaySize(renderer) {
  const canvas = renderer.domElement;
  const pixelRatio = window.devicePixelRatio;
  const width = (canvas.clientWidth * pixelRatio) | 0;
  const height = (canvas.clientHeight * pixelRatio) | 0;
  const needResize = canvas.width !== width || canvas.height !== height;

  if (needResize) {
    renderer.setSize(width, height, false);
  }

  return needResize;
}

function checkWebSocketConnection(url) {
  return new Promise((resolve, reject) => {
    try {
      console.log(`Attempting to connect to: ${url}`);
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log(`Successfully connected to ${url}`);
        ws.close();
        resolve(url);
      };

      ws.onerror = (error) => {
        reject(null);
      };
    } catch (err) {
      console.log(`Error during WebSocket creation for ${url}:`, err);
    }
  });
}

function updateElements(elements, action, condition) {
  elements.forEach(function (e) {
    const element = document.getElementById(e);
    if (element) {
      element[action] = condition;
    }
  });
}

async function bulkCreate(items, scene_id, createFn, label) {
  if (!items || items.length === 0) {
    return null;
  }

  const tasks = items.map((item) => {
    if (scene_id) {
      item.scene = scene_id;
    }
    if (item.uid) {
      delete item.uid;
    }
    if (label === "Sensor" && "sensor_id" in item) {
      delete item.sensor_id;
    }
    return createFn(item)
      .then((response) => {
        const errors = response.errors || null;
        return errors ? [errors, item] : null;
      })
      .catch((err) => {
        console.error(`Error creating ${label}:`, err);
        return [err, item];
      });
  });

  const results = await Promise.all(tasks);
  const filtered = results.filter((res) => res);
  return filtered.length > 0 ? filtered : null;
}

async function getResource(folder, window, type) {
  try {
    const response = await fetch(
      `https://${window.location.hostname}/media/list/${folder}/`,
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch: ${response.statusText}`);
    }
    const data = await response.json();

    let files;
    if (type === "json") {
      files = data.files.filter((filename) => filename.endsWith(".json"));
    } else {
      files = data.files.filter((filename) => !filename.endsWith(".json"));
    }

    console.log("Resource files", files);
    return files;
  } catch (err) {
    console.error("Error fetching file list:", err);
    return [];
  }
}

async function uploadResource(file, authToken, jsonData) {
  const formData = new FormData();
  formData.append("map", file);
  formData.append("name", jsonData.name);
  let responseText;
  let data;
  let errors = false;
  try {
    const response = await fetch(`${REST_URL}/scene`, {
      method: "POST",
      headers: {
        Authorization: authToken,
      },
      body: formData,
    });

    responseText = await response.text();
    if (!response.ok) {
      console.error(
        `Failed to create scene: ${response.status} ${response.statusText}`,
      );
      errors = true;
    }

    try {
      data = JSON.parse(responseText);
    } catch (parseErr) {
      console.warn("Response is not valid JSON:", responseText);
    }

    return { data, errors };
  } catch (err) {
    console.error("Error in scene creation:", err);
    errors = true;
    data = JSON.parse(responseText);
    return { data, errors };
  }
}

async function importScene(
  zipURL,
  restClient,
  basename,
  window,
  authToken,
  child = null,
  parent = null,
) {
  let errors = {
    scene: null,
    cameras: null,
    tripwires: null,
    regions: null,
    sensors: null,
  };

  let jsonData = null;

  try {
    const jsonFile = await getResource(basename, window, "json");
    const resourceFiles = await getResource(basename, window, null);

    if (jsonFile.length === 0 || resourceFiles.length === 0) {
      errors.scene = { scene: ["Cannot find JSON or resource file"] };
      return errors;
    }

    const jsonResponse = await fetch(`${zipURL}/${jsonFile[0]}`);
    if (!jsonResponse.ok) {
      errors.scene = { scene: ["Failed to import scene"] };
      return errors;
    }

    if (child) {
      jsonData = child;
    } else {
      try {
        jsonData = await jsonResponse.json();
      } catch (err) {
        errors.scene = { scene: ["Failed to parse JSON"] };
        return errors;
      }
    }

    const matchedFile = resourceFiles.find((f) => f.includes(jsonData.name));
    const resourceUrl = `/media/${basename}/${matchedFile}`;
    const response = await fetch(resourceUrl);
    if (!response.ok) {
      errors.scene = { scene: ["Failed to import scene"] };
      return errors;
    }

    const blob = await response.blob();
    const blobType = blob.type.split("/")[1];

    const validExtensions = ["png", "jpeg", "gltf-binary"];
    if (!validExtensions.includes(blobType)) {
      errors.scene = { scene: ["Invalid resource type"] };
      return errors;
    }
    let fileType = `.${blobType}`;
    if (blobType === "gltf-binary") {
      fileType = ".glb";
    }
    console.log("resource type", fileType);
    const file = new File([blob], `${jsonData.name}${fileType}`, {
      type: blob.type,
    });
    const resp = await uploadResource(file, authToken, jsonData);
    console.log(resp.errors);
    if (resp.errors) {
      errors.scene = resp.data;
      return errors;
    }

    const scene_id = resp.data.uid;
    const sceneData = {
      scale: jsonData.scale,
      regulate_rate: jsonData.regulate_rate,
      external_update_rate: jsonData.external_update_rate,
      camera_calibration: jsonData.camera_calibration,
      apriltag_size: jsonData.apriltag_size,
      number_of_localizations: jsonData.number_of_localizations,
      global_feature: jsonData.global_feature,
      minimum_number_of_matches: jsonData.minimum_number_of_matches,
      inlier_threshold: jsonData.inlier_threshold,
      output_lla: jsonData.output_lla,
      map_corners_lla: jsonData.map_corners_lla
    };

    if (child) {
      sceneData.parent = parent;
    }

    let updateResponse = await restClient.updateScene(scene_id, sceneData);
    console.log("Scene updated:", updateResponse);

    if (child) {
      if (Object.hasOwn(child, "link")) {
        delete child.link.uid;
        delete child.link.transform;
        let child_uid = updateResponse.content.uid;
        let parent_uid = updateResponse.content.parent;
        child.link.child = child_uid;
        child.link.parent = parent_uid;
        updateResponse = restClient.updateChildScene(child_uid, child.link);
        console.log("Child link updated:", updateResponse);
      }
    }

    errors.cameras = await bulkCreate(
      (jsonData.cameras || []).map((cam) => {
        let camData = {
          name: cam.name,
          sensor_id: cam.uid,
          scale: cam.scale,
          intrinsics: cam.intrinsics,
        };

        if (Object.hasOwn(cam, "transform_type")) {
          if (cam.transform_type == POINT_CORRESPONDENCE) {
            camData.transforms = cam.transforms;
            camData.transform_type = POINT_CORRESPONDENCE;
          } else {
            camData.transform_type = EULER;
            camData.translation = cam.translation;
            camData.rotation = cam.rotation;
          }
        }
        return camData;
      }),
      scene_id,
      restClient.createCamera.bind(restClient),
      "Camera",
    );

    errors.regions = await bulkCreate(
      jsonData.regions,
      scene_id,
      restClient.createRegion.bind(restClient),
      "Region",
    );
    errors.tripwires = await bulkCreate(
      jsonData.tripwires,
      scene_id,
      restClient.createTripwire.bind(restClient),
      "Tripwire",
    );
    errors.sensors = await bulkCreate(
      jsonData.sensors,
      scene_id,
      restClient.createSensor.bind(restClient),
      "Sensor",
    );

    if (Array.isArray(jsonData.children)) {
      for (const child of jsonData.children) {
        let childErrors = await importScene(
          zipURL,
          restClient,
          basename,
          window,
          authToken,
          child,
          scene_id,
        );
        if (childErrors.scene) {
          return childErrors;
        }
        if (
          childErrors.cameras ||
          childErrors.tripwires ||
          childErrors.regions ||
          childErrors.sensors
        ) {
          return childErrors;
        }
      }
    }
    return errors;
  } catch (err) {
    errors.scene = { scene: ["Error processing scene import"] };
    return errors;
  }
}

export {
  pixelsToMeters,
  metersToPixels,
  compareIntrinsics,
  waitUntil,
  initializeOpencv,
  resizeRendererToDisplaySize,
  checkWebSocketConnection,
  updateElements,
  importScene,
};
