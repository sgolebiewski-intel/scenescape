#!/bin/bash

# SPDX-FileCopyrightText: (C) 2022 - 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

PERF_TEST_BASE=tests/perf_tests
SCENEPERF_TEST_BASE=${PERF_TEST_BASE}/scene_perf
COMPOSE=tests/compose

TEST_NAME="Scene Performance test"

source tests/test_utils.sh

TESTINPUTRATE=${INPUT_RATE:-30}
TESTINPUTFRAMES=${INPUT_FRAMES:-1000}
TESTINPUTFILES=${INPUT_FILES:-"${SCENEPERF_TEST_BASE}/data/amcrest01.json"}
TESTMONITORINTERVAL=${MONITORINTERVAL:-3}
TEST_DURATION=${DURATION:-120}

export SCENETEST_INPUTRATE=${TESTINPUTRATE}
export SCENETEST_INPUTFRAMES=${TESTINPUTFRAMES}
export SCENETEST_MONITORINTERVAL=${TESTMONITORINTERVAL}
export SCENETEST_INPUTS=${TESTINPUTFILES}

export LOG=test_mqtt_recorder_log.txt

export SECRETSDIR=./manager/secrets
export DBROOT=test_data/scene_perf_full

export WAITFORCONTAINERS="pgserver web scene "
export LOGSFORCONTAINER="${WAITFORCONTAINERS} mqtt_recorder "

rm -f ${LOG}

tests/runtest sample_data/docker-compose-dls-perf.yml \
    sleep ${TEST_DURATION}

RESULT=$?

if [[ $RESULT -eq 0 ]]
then
    echo "${TEST_NAME}: Test Passed"
else
    echo "${TEST_NAME}: Test Failed"
fi

exit $RESULT
