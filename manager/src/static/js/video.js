// SPDX-FileCopyrightText: (C) 2024 - 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

/**
 * @file camcanvas.js
 * @description This file defines the CamCanvas class for displaying video frames.
 */

"use strict";

playVideo() {
  const video = document.getElementById('whepVideo');
  let defaultControls = false;
  let reader = null;

  const loadAttributesFromQuery = () => {
    video.controls = false;
    video.muted = true;
    video.autoplay = true;
    video.playsInline = true;
    video.disablepictureinpicture = true;
  };

  window.addEventListener('load', () => {
    loadAttributesFromQuery();

    reader = new MediaMTXWebRTCReader({
      url: new URL('whep', 'http://10.123.233.203:8889/cam'),
      onError: (err) => {
        console.log(err)
      },
      onTrack: (evt) => {
        video.srcObject = evt.streams[0];
      },
    });
  });

  window.addEventListener('beforeunload', () => {
    if (reader !== null) {
      reader.close();
    }
  });
}
