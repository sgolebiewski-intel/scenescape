#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2022 - 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import argparse
from datetime import datetime
import json
import os
import base64
import paho.mqtt.client as mqtt

MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', None)
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', None)
ROOT_CA = os.getenv('ROOT_CA', None)

class CalibrationImageSaver:
    def __init__(self):
        self.client = mqtt.Client(client_id="", clean_session=True, userdata=None, protocol=mqtt.MQTTv311, transport="tcp")
        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        if ROOT_CA:
            self.client.tls_set(ROOT_CA)
        self.client.on_connect = self.on_connect
        self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
        self.client.on_message = self.save_image
        self.client.loop_forever()
        return

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        self.client.subscribe("scenescape/image/calibration/camera/camera1")
        return

    def save_image(self, client, userdata, msg):
        print(f"Received message on topic {msg.topic}")
        try:
            topic_parts = msg.topic.split('/')
            camera_id = topic_parts[1] if len(topic_parts) > 1 else "unknown"

            msg = json.loads(msg.payload)
            image_binary = base64.b64decode(msg['image'])

            filename = f"percebro_undistorted_image_full.jpg"
            filepath = os.path.join(filename)
            with open(filepath, 'wb') as f:
                f.write(image_binary)
            print(f"Saved calibration image: {filepath}")
            print(f"Camera ID: {camera_id}")
            print(f"Image size: {len(image_binary)} bytes")
            exit(0)
        except Exception as e:
            print(f"Error saving image: {e}")
        return

def build_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', required=True, type=str, help='Path to the sensor data file')
    return parser.parse_args()

def main():
    CalibrationImageSaver()
    return

if __name__ == "__main__":
    main()