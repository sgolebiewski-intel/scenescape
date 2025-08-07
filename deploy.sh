#!/bin/sh

# SPDX-FileCopyrightText: (C) 2021 - 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

. tools/yaml_parse.sh

set -e

if ! command -v apt-get > /dev/null ; then
    echo This script will only work on a Debian or Ubuntu based system.
    echo Cannot proceed.
    exit 1
fi

if ! command -v sudo > /dev/null ; then
    echo Please install sudo.
    echo Cannot proceed.
    exit 1
fi

CUID=$(id -u)
if [ $CUID -lt 1000 ] ; then
    echo Cannot run as system user.
    exit 1
fi
OWNER=$(stat -c '%u' .)
if [ $CUID -ne $OWNER ] ; then
    echo Directory owner is not the same as current user.
    echo Cannot proceed.
    exit 1
fi

if egrep '\^M\$?$' scene_common/src/scenescape.py >/dev/null ; then
    echo Line endings have been mangled.
    echo Cannot proceed.
    exit 1
fi

#Define port numbers
BROKER_PORT=${BROKER_PORT:-1883}
HTTPS_PORT=${HTTPS_PORT:-443}

REQPORTS="$BROKER_PORT $HTTPS_PORT"
for p in $REQPORTS
do
    if command nc -z 127.0.0.1 $p ; then
        echo "Service already running at port $p. Please terminate services on ports ${REQPORTS}."
        exit 1
    fi
done

PACKAGES=""
for cmd in git curl make openssl unzip ; do
    if ! dpkg -s ${cmd} > /dev/null ; then
        PACKAGES="${PACKAGES} ${cmd}"
    fi
done
if [ -n "${PACKAGES}" ] ; then
    echo Running sudo to install needed packages: ${PACKAGES}
    sudo apt-get update
    sudo apt-get install -y ${PACKAGES}
fi

version_check()
{
    printf '%s\n%s\n' "$2" "$1" | sort --check=quiet --version-sort
}

if ! (docker compose version 2>/dev/null| grep "Docker Compose version" > /dev/null); then
    echo '########################################'
    echo Installing docker
    echo '########################################'
    sh tools/get_docker.sh
else
    DOCKER_MINIMUM=20.10.23
    DOCKER_VERSION=$(docker --version | sed -E -e 's/.* ([0-9]+[.][0-9]+[.][0-9]+)([-+][0-9a-zA-Z]+)?[, ].*/\1/')
    if ! version_check ${DOCKER_VERSION} ${DOCKER_MINIMUM} ; then
        echo Docker version ${DOCKER_VERSION} is too old, need ${DOCKER_MINIMUM} or higher
        exit 1
    fi
    COMPOSE_MINIMUM=2.24.2
    COMPOSE_VERSION=$(docker compose version | sed -E -e 's/.*v([0-9]+[.][0-9]+[.][0-9]+)(-[0-9a-zA-Z]+)?.*/\1/')
    if ! version_check ${COMPOSE_VERSION} ${COMPOSE_MINIMUM} ; then
        echo Docker Compose plugin version ${COMPOSE_VERSION} is too old, need ${COMPOSE_MINIMUM} or higher
        exit 1
    fi
fi

if [ "${SKIPYML}" != "1" ] ; then
    if [ -e docker-compose.yml ] ; then
        while true ; do
            read -p "docker-compose.yml already exists. Replace it with docker compose example file? " yn
            case $yn in
                [Yy]*)
                    break
                    ;;
                [Nn]*)
                    if ! tools/yaml_validator docker-compose.yml ; then
                        echo "docker-compose.yml is not valid"
                        exit 1
                    fi
                    SKIPYML=1
                    break
                    ;;
                *)
                    echo "Please answer yes or no."
                    ;;
            esac
        done
    fi

    if [ "${SKIPYML}" != "1" ] ; then
        rm -f docker-compose.yml
        make docker-compose.yml
    fi
fi

COMPOSE=docker-compose.yml
COMPOSE_services=$(parse_yaml ${COMPOSE} COMPOSE_ | grep COMPOSE_services | sed -E -e 's/COMPOSE_services_([^_+]+)[+_]?.*/\1/'|sort -u)

DIRNAME=$(basename ${PWD})
for s in ${COMPOSE_services}
do
    SVC="${DIRNAME}_${s}_1"
    if [ -n "$(docker ps -q -f name=^/${SVC}$)" ] ; then
        echo "Service $s already running. Please terminate all SceneScape services."
        exit 1
    fi
done

SUPASS=$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9!@#$%^&*()_+-=[]{}|;:,.<>?/~' | head -c 24)

if ! groups | grep docker > /dev/null ; then
    sudo usermod -a -G docker ${USER}
    echo
    echo Please enter the password for $USER to continue building
    exec su - ${USER} -c "env SKIPYML=1 SUPASS=${SUPASS} DBPASS=${DBPASS} CERTPASS=${CERTPASS} ${SHELL} -c 'cd '${PWD}' && ./$0'"
fi

echo '########################################'
echo Building SceneScape
echo '########################################'

make -C docs clean
make CERTPASS="${CERTPASS}" DBPASS="${DBPASS}"

if manager/tools/upgrade-database --check ; then
    UPGRADEDB=0
    echo "No upgrade needed"

else
    while true ; do
        echo
        echo
        read -p "Your database needs to be upgraded. Backup and upgrade now? " yn
        case $yn in
            [Yy]*)
                UPGRADEDB=1
                break
                ;;
            [Nn]*)
                break
                ;;
            *)
                echo "Please answer yes or no."
                ;;
        esac
    done

    if [ "${UPGRADEDB}" != "1" ] ; then
        echo
        echo "ABORTING"
        echo "Database must be upgraded in order to continue"
        exit 1
    fi

    UPGRADE_LOG=/tmp/upgrade.$$.log
    manager/tools/upgrade-database 2>&1 | tee ${UPGRADE_LOG}
    NEW_DB=$(egrep 'Upgraded database .* has been created' ${UPGRADE_LOG} | awk '{print $NF}')
    if [ ! -d "${NEW_DB}/db" -o ! -d "${NEW_DB}/migrations" ] ; then
        echo
        echo "ABORTING"
        echo "Automatic upgrade of database failed"
        exit 1
    fi

    rsync -a --delete ${NEW_DB}/db ${NEW_DB}/migrations .
fi

if [ "${SKIP_BRINGUP}" != "1" ] ; then
    make demo SUPASS=$SUPASS
fi

echo
echo "====================================================================="
echo "The autogenerated SceneScape superuser password (SUPASS) is:"
echo
echo "    $SUPASS"
echo
echo "Please copy this password to use in your browser when prompted."
echo "====================================================================="
