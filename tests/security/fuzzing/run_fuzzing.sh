#!/usr/bin/env sh

# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

cd /workspace || { echo "Failed to change directory"; exit 1; }

. .env

cp scenescape-ca.pem /usr/local/share/ca-certificates
update-ca-certificates

# shellcheck disable=SC2154
https_proxy=$https_proxy apk add curl jq

# shellcheck disable=SC2154
echo "$instance_ip web.scenescape.intel.com" >> /etc/hosts

cp token /tmp
# shellcheck disable=SC2154
auth_token=$(curl "https://web.scenescape.intel.com/api/v1/auth" -d "username=$auth_username&password=$auth_password" | jq -r '.token')
sed -i "s/##TOKEN##/$auth_token/" /tmp/token

/RESTler/restler/Restler compile --api_spec fuzzing_openapi.yaml
# shellcheck disable=SC2154
/RESTler/restler/Restler $restler_mode --time_budget $time_budget_hours --grammar_file Compile/grammar.py --dictionary_file Compile/dict.json --settings settings.json
