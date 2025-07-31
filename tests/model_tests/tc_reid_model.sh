#!/bin/bash
# SPDX-FileCopyrightText: (C) 2021 - 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

TEST_NAME="reid-test"
echo "Executing test: ${TEST_NAME}"

SAFE_TEST_NAME=$(echo "${TEST_NAME}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]//g')

TESTBASE="tests/model_tests"
COMPOSEDIR="${TESTBASE}/compose"
YMLFILE="docker-compose-reid.yml"

docker compose \
  --project-name "${SAFE_TEST_NAME}" \
  -f "${COMPOSEDIR}/${YMLFILE}" \
  --project-directory "${PWD}" \
  up --abort-on-container-exit

CONTAINER_NAME=$(docker ps -a --filter "name=${SAFE_TEST_NAME}" --format "{{.Names}}" | head -n 1)

if [ -z "$CONTAINER_NAME" ]; then
  echo "Error: No container found for project ${SAFE_TEST_NAME}"
  exit 1
fi

LOG_OUTPUT=$(docker logs "$CONTAINER_NAME")
docker compose --project-name "${SAFE_TEST_NAME}" -f "${COMPOSEDIR}/${YMLFILE}" --project-directory "${PWD}" down -v

if echo "$LOG_OUTPUT" | grep -q 'reid not found after checking'; then
  echo "Test failed: 'reid' not found in one or more camera topics."
  exit 1
else
  echo "Test passed: 'reid' field found in at least one message."
  exit 0
fi
