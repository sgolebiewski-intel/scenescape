# Intel® Edge Spatial Intelligence Overview and Architecture

Scene-based AI software framework.

## Overview

Intel® Edge Spatial Intelligence is a software framework that enables spatial awareness by integrating data from cameras and other sensors into scenes. It simplifies application development by providing near-real-time, actionable data about the state of the scene, including what, when, and where objects are present, along with their sensed attributes and environment. This scene-based approach makes it easy to incorporate and fuse sensor inputs, enabling analysis of past events, monitoring of current activities, and prediction of future outcomes from scene data.

Even with a single camera, transitioning to a scene paradigm offers significant advantages. Applications are written against the scene data directly, allowing for flexibility in modifying the sensor setup. You can move, modify, remove, or add cameras and sensors without changing your application or business logic. As you enhance your sensor array, the data quality improves, leading to better insights and decisions without altering your underlying application logic.

Intel® Edge Spatial Intelligence turns raw sensor data into actionable insights by representing objects, people, and vehicles within a scene. Applications can access this information to make informed decisions, such as identifying safety hazards, detecting equipment issues, managing queues, correcting product placements, or responding to emergencies.

## How It Works

Intel® Edge Spatial Intelligence uses advanced AI algorithms and hardware to process data from cameras and sensors, maintaining a dynamic scene graph that includes 3D spatial information and time-based changes. This enables developers to write applications that interact with a digital version of the environment in near real-time, allowing for responsive and adaptive application behavior based on the latest sensor data.

The framework leverages the Intel® Distribution of OpenVINO™ toolkit to efficiently handle sensor data, enabling developers to write applications that can be deployed across various Intel® hardware accelerators like CPUs, GPUs, VPUs, FPGAs, and GNAs. This ensures optimized performance and scalability.

A key goal of Intel® Edge Spatial Intelligence is to make writing applications and business logic faster, simpler, and easier. By defining each scene with a fixed local coordinate system, spatial context is provided to sensor data. Scenes can represent various environments, such as buildings, ships, aircraft, or campuses, and can be linked to a global geographical coordinate system if needed. Intel® Edge Spatial Intelligence manages:

- Multiple scenes, each with its own coordinate system.
- A single parent scene for each sensor at any given time.
- The precise location and orientation of cameras and sensors within the scene, stored in the Intel® Edge Spatial Intelligence database. This information is crucial for interpreting sensor data correctly.
- Compatibility with glTF scene graph representations.

Intel® Edge Spatial Intelligence is built on a collection of containerized services that work together to deliver comprehensive functionality, ensuring seamless integration and operation.

![Edge Spatial Intelligence architecture diagram](images/architecture.png)
Figure 1: Architecture Diagram

### Scene Controller

Maintains the current state of the scene, including tracked objects, cameras, and sensors. For more information, refer to [Scene Controller Microservice](https://github.com/open-edge-platform/scenescape/blob/main/controller/README.md)

### Deep Learning Streamer Pipeline Server

Deep Learning Streamer Pipeline Server (DL Streamer Pipeline Server) is a Python-based, interoperable containerized microservice for easy development and deployment of video analytics pipelines. For more information, refer to [Deep Learning Streamer Pipeline Server](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/dlstreamer-pipeline-server/docs/user-guide)

### Auto Camera Calibration

Computes camera parameters utilizing known priors and camera feed. For more information, refer to [Auto Camera Calibration](https://github.com/open-edge-platform/scenescape/blob/main/autocalibration/README.md)

### MQTT Broker

Mosquitto MQTT broker which acts as the primary message bus connecting sensors, internal components, and applications, including the web interface.

### Web Server

Apache web server providing a Django-based web UI which allows users to view updates to the scene graph and manage scenes, cameras, sensors, and analytics. It also serves the Intel® Edge Spatial Intelligence REST API.

### NTP Server

Time server which maintains the reference clock and keeps clients in sync.

### SQL Database

PostgreSQL database server which stores static information used by the web UI and the scene controller. No video or object location data is stored by Intel® Edge Spatial Intelligence.

## Supporting Resources

- [Getting Started Guide](Getting-Started-Guide.md)
- [API Reference](api-reference.md)
- How camera normalization is implemented in Intel® Edge Spatial Intelligence [Camera normalization](convert-object-detections-to-normalized-image-space.md)
