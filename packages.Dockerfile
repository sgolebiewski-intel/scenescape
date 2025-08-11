ARG BASE_IMAGE=scenescape-camcalibration:latest

FROM ${BASE_IMAGE}

RUN apt update \
    && pip install pip-licenses

# npm scanning
# npm install -g license-checker

COPY generate_notice.py .
