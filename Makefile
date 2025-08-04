# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# ================ Makefile for Intel® SceneScape ====================

# =========================== Variables ==============================
SHELL := /bin/bash

# Build folders
COMMON_FOLDER := scene_common
IMAGE_FOLDERS := autocalibration broker controller manager model_installer percebro

# Build flas
EXTRA_BUILD_FLAGS :=
REBUILDFLAGS :=

# Image variables
IMAGE_PREFIX := scenescape
SOURCES_IMAGE := $(IMAGE_PREFIX)-sources
VERSION := $(shell cat ./version.txt)

# User configurable variables
COMPOSE_PROJECT_NAME ?= scenescape
# - User can adjust build output folder (defaults to $PWD/build)
BUILD_DIR ?= $(PWD)/build
# - User can adjust folders being built (defaults to all)
FOLDERS ?= $(IMAGE_FOLDERS)
# - User can adjust number of parallel jobs (defaults to CPU count)
JOBS ?= $(shell nproc)
# - User can adjust the target branch
TARGET_BRANCH ?= $(if $(CHANGE_TARGET),$(CHANGE_TARGET),$(BRANCH_NAME))
# Ensure BUILD_DIR path is absolute, so that it works correctly in recursive make calls
ifeq ($(filter /%,$(BUILD_DIR)),)
override BUILD_DIR := $(PWD)/$(BUILD_DIR)
endif

# Secrets building variables
SECRETSDIR ?= $(PWD)/manager/secrets
CERTDOMAIN ?= scenescape.intel.com

# Demo variables
DLSTREAMER_SAMPLE_VIDEOS := $(addprefix sample_data/,apriltag-cam1.ts apriltag-cam2.ts apriltag-cam3.ts qcam1.ts qcam2.ts)
PERCEBRO_DOCKER_COMPOSE_FILE := ./sample_data/docker-compose-example.yml
DLSTREAMER_DOCKER_COMPOSE_FILE := ./sample_data/docker-compose-dl-streamer-example.yml

# Test variables
TESTS_FOLDER := tests
TEST_DATA_FOLDER := test_data
TEST_IMAGE_FOLDERS := autocalibration controller manager
TEST_IMAGES := $(addsuffix -test, camcalibration controller manager percebro)

# ========================= Default Target ===========================

default: build-all

.PHONY: build-all
build-all: init-secrets build-images install-models

# ============================== Help ================================

.PHONY: help
help:
	@echo ""
	@echo "Intel® SceneScape version $(VERSION)"
	@echo ""
	@echo "Available targets:"
	@echo "  build-all         (default) Build secrets, all images, and install models"
	@echo "  build-images                Build all microservice images in parallel"
	@echo "  init-secrets                Generate secrets and certificates"
	@echo "  <image folder>              Build a specific microservice image (autocalibration, broker, etc.)"
	@echo ""
	@echo "  demo                        Start the SceneScape demo. Percebro-based visual analytics pipelines are used by default."
	@echo "                              (the demo target requires the SUPASS environment variable to be set"
	@echo "                              as the super user password for logging into Intel® SceneScape)"
	@echo ""
	@echo "  list-dependencies           List all apt/pip dependencies for all microservices"
	@echo "  build-sources-image         Build the image with 3rd party sources"
	@echo "  install-models              Install custom OpenVINO Zoo models to models volume"
	@echo "  check-db-upgrade            Check if the database needs to be upgraded"
	@echo "  upgrade-database            Backup and upgrade database to a newer PostgreSQL version"
	@echo "                              (automatically transfers data to Docker volumes)"
	@echo ""
	@echo "  rebuild                     Clean and build all images"
	@echo "  rebuild-all                 Clean and build everything including secrets and volumes"
	@echo ""
	@echo "  clean                       Clean images and build artifacts (logs etc.)"
	@echo "  clean-all                   Clean everything including volumes, secrets and models"
	@echo "  clean-volumes               Remove all project Docker volumes"
	@echo "  clean-secrets               Remove all generated secrets"
	@echo "  clean-models                Remove all installed models"
	@echo "  clean-tests                 Clean test images and test artifacts (logs etc.)"
	@echo ""
	@echo "  run_tests                   Run all tests"
	@echo "  run_basic_acceptance_tests  Run basic acceptance tests"
	@echo "  run_performance_tests       Run performance tests"
	@echo "  run_stability_tests         Run stability tests"
	@echo ""
	@echo "  lint-all                    Lint entire code base"
	@echo "  lint-python                 Lint python files"
	@echo "  lint-python-pylint          Lint python files using pylint"
	@echo "  lint-python-flake8          Lint python files using flake8"
	@echo "  lint-javascript             Lint javascript files"
	@echo "  lint-cpp                    Lint C++ files"
	@echo "  lint-html                   Lint HTML files"
	@echo "  lint-dockerfiles            Lint Dockerfiles"
	@echo "  lint-shell                  Lint shell files"
	@echo "  prettier-check              Run prettier check on all supported files"
	@echo ""
	@echo "  format-python               Format python files using autopep8"
	@echo "  prettier-write              Format code using prettier"
	@echo ""
	@echo "  add-licensing FILE=<file>   Add licensing headers to a file"
	@echo ""
	@echo "Usage:"
	@echo "  - Use 'SUPASS=<password> make build-all demo' to build Intel® SceneScape and run demo."
	@echo ""
	@echo "Tips:"
	@echo "  - Use 'DLS=1 make demo' to run demo with DLStreamer-based visual analytics pipelines."
	@echo "  - Use 'make BUILD_DIR=<path>' to change build output folder (default is './build')."
	@echo "  - Use 'make JOBS=N' to build Intel® SceneScape images using N parallel processes."
	@echo "  - Use 'make FOLDERS=\"<list of image folders>\"' to build specific image folders."
	@echo "  - Image folders can be: $(IMAGE_FOLDERS)"
	@echo ""

# ========================== CI specific =============================

ifneq (,$(filter DAILY TAG,$(BUILD_TYPE)))
  EXTRA_BUILD_FLAGS := rebuild
endif

ifneq (,$(filter rc beta-rc,$(TARGET_BRANCH)))
  EXTRA_BUILD_FLAGS := rebuild
endif

.PHONY: check-tag
check-tag:
ifeq ($(BUILD_TYPE),TAG)
	@echo "Checking if tag matches version.txt..."
	@if grep --quiet "$(BRANCH_NAME)" version.txt; then \
		echo "Perfect - Tag and Version is matching"; \
	else \
		echo "There is some mismatch between Tag and Version"; \
		exit 1; \
	fi
endif

# ========================= Build Images =============================

$(BUILD_DIR):
	mkdir -p $@

# Build common base image
.PHONY: build-common
build-common:
	@echo "==> Building common base image..."
	@$(MAKE) -C $(COMMON_FOLDER) http_proxy=$(http_proxy) $(EXTRA_BUILD_FLAGS)
	@echo "DONE ==> Building common base image"

# Build targets for each service folder
.PHONY: $(IMAGE_FOLDERS)
$(IMAGE_FOLDERS):
	@echo "====> Building folder $@..."
	@$(MAKE) -C $@ BUILD_DIR=$(BUILD_DIR) http_proxy=$(http_proxy) https_proxy=$(https_proxy) no_proxy=$(no_proxy) $(EXTRA_BUILD_FLAGS)
	@echo "DONE ====> Building folder $@"

# Dependency on the common base image
autocalibration controller manager percebro: build-common

# Parallel wrapper handles parallel builds of folders specified in FOLDERS variable
.PHONY: build-images
build-images: $(BUILD_DIR)
	@echo "==> Running parallel builds of folders: $(FOLDERS)"
# Use a trap to catch errors and print logs if any error occurs in parallel build
	@set -e; trap 'grep --color=auto -i -r --include="*.log" "^error" $(BUILD_DIR) || true' EXIT; \
	$(MAKE) -j$(JOBS) $(FOLDERS)
	@echo "DONE ==> Parallel builds of folders: $(FOLDERS)"

# ===================== Cleaning and Rebuilding =======================

.PHONY: rebuild
rebuild: clean build-images

.PHONY: rebuild-all
rebuild-all: clean-all build-all

.PHONY: clean
clean:
	@echo "==> Cleaning up all build artifacts..."
	@for dir in $(FOLDERS); do \
		$(MAKE) -C $$dir clean 2>/dev/null; \
	done
	@echo "Cleaning common folder..."
	@$(MAKE) -C $(COMMON_FOLDER) clean 2>/dev/null
	@-rm -rf $(BUILD_DIR)
	@echo "DONE ==> Cleaning up all build artifacts"

.PHONY: clean-all
clean-all: clean clean-secrets clean-volumes clean-models clean-tests
	@echo "==> Cleaning all..."
	@-rm -f $(DLSTREAMER_SAMPLE_VIDEOS)
	@-rm -f docker-compose.yml .env
	@echo "DONE ==> Cleaning all"

.PHONY: clean-models
clean-models:
	@echo "==> Cleaning up all models..."
	@-docker volume rm -f $${COMPOSE_PROJECT_NAME:-scenescape}_vol-models
	@echo "DONE ==> Cleaning up all models"

.PHONY: clean-volumes
clean-volumes:
	@echo "==> Cleaning up all volumes..."
	@if [ -f ./docker-compose.yml ]; then \
	    docker compose down -v; \
	else \
	    VOLS=$$(docker volume ls -q --filter "name=$(COMPOSE_PROJECT_NAME)_"); \
	    if [ -n "$$VOLS" ]; then \
	        docker volume rm -f $$VOLS 2>/dev/null; \
	    fi; \
	fi
	@echo "DONE ==> Cleaning up all volumes"

.PHONY: clean-secrets
clean-secrets:
	@echo "==> Cleaning secrets..."
	@-rm -rf $(SECRETSDIR)
	@echo "DONE ==> Cleaning secrets"

.PHONY: clean-tests
clean-tests:
	@echo "==> Cleaning test artifacts..."
	@-rm -rf test_data/
	@echo "Cleaning test images..."
	@for image in $(TEST_IMAGES); do \
	    docker rmi $(IMAGE_PREFIX)-$$image:$(VERSION) $(IMAGE_PREFIX)-$$image:latest 2>/dev/null || true; \
	done
	@echo "DONE ==> Cleaning test artifacts"

# ===================== 3rd Party Dependencies =======================
.PHONY: list-dependencies
list-dependencies: $(BUILD_DIR)
	@echo "==> Listing dependencies for all microservices..."
	@set -e; \
	for dir in $(IMAGE_FOLDERS); do \
		$(MAKE) -C $$dir list-dependencies; \
	done
	@-find . -type f -name '*-apt-deps.txt' -exec cat {} + | sort | uniq > $(BUILD_DIR)/scenescape-all-apt-deps.txt
	@-find . -type f -name '*-pip-deps.txt' -exec cat {} + | sort | uniq > $(BUILD_DIR)/scenescape-all-pip-deps.txt
	@echo "The following dependency lists have been generated:"
	@find $(BUILD_DIR) -name '*-deps.txt' -print
	@echo "DONE ==> Listing dependencies for all microservices"

.PHONY: build-sources-image
build-sources-image: sources.Dockerfile
	@echo "==> Building the image with 3rd party sources..."
	env BUILDKIT_PROGRESS=plain \
	  docker build $(REBUILDFLAGS) -f $< \
	    --build-arg http_proxy=$(http_proxy) \
	    --build-arg https_proxy=$(https_proxy) \
	    --build-arg no_proxy=$(no_proxy) \
	    --rm -t $(SOURCES_IMAGE):$(VERSION) . \
	&& docker tag $(SOURCES_IMAGE):$(VERSION) $(SOURCES_IMAGE):latest
	@echo "DONE ==> Building the image with 3rd party sources"

# ======================= Model Installer ============================

.PHONY: install-models
install-models:
	@$(MAKE) -C model_installer install-models

# =========================== Run Tests ==============================

.PHONY: setup_tests
setup_tests: build-images
	@echo "Setting up test environment..."
	for dir in $(TEST_IMAGE_FOLDERS); do \
		$(MAKE) -C $$dir test-build; \
	done
	mkdir -p $(TEST_DATA_FOLDER)/netvlad_models
	@echo "DONE ==> Setting up test environment"

.PHONY: run_tests
run_tests: setup_tests
	@if [ "$${DLS}" = "1" ]; then \
	    $(MAKE) $(DLSTREAMER_SAMPLE_VIDEOS); \
	fi
	@echo "Running tests..."
	@DLS_ARG=""; [ "$${DLS}" = "1" ] && DLS_ARG="DLS=1"; \
	$(MAKE) --trace -C tests -j 1 $${DLS_ARG} SECRETSDIR=$(PWD)/manager/secrets || (echo "Tests failed" && exit 1)
	@echo "DONE ==> Running tests"

.PHONY: run_performance_tests
run_performance_tests:
	@if [ "$${DLS}" = "1" ]; then \
	    $(MAKE) $(DLSTREAMER_SAMPLE_VIDEOS); \
	fi
	@echo "Running performance tests..."
	@DLS_ARG=""; [ "$${DLS}" = "1" ] && DLS_ARG="DLS=1"; \
	$(MAKE) -C tests performance_tests -j 1 SUPASS=$(SUPASS) $${DLS_ARG} || (echo "Performance tests failed" && exit 1)
	@echo "DONE ==> Running performance tests"

.PHONY: run_stability_tests
run_stability_tests:
	@if [ "$${DLS}" = "1" ]; then \
	    $(MAKE) $(DLSTREAMER_SAMPLE_VIDEOS); \
	fi
	@echo "Running stability tests..."
	@DLS_ARG=""; [ "$${DLS}" = "1" ] && DLS_ARG="DLS=1"
ifeq ($(BUILD_TYPE),DAILY)
	@$(MAKE) -C tests system-stability SUPASS=$(SUPASS) $${DLS_ARG} HOURS=4
else
	@$(MAKE) -C tests system-stability SUPASS=$(SUPASS) $${DLS_ARG}
endif
	@echo "DONE ==> Running stability tests"

.PHONY: run_basic_acceptance_tests
run_basic_acceptance_tests: setup_tests
	@if [ "$${DLS}" = "1" ]; then \
	    $(MAKE) $(DLSTREAMER_SAMPLE_VIDEOS); \
	fi
	@echo "Running basic acceptance tests..."
	@DLS_ARG=""; [ "$${DLS}" = "1" ] && DLS_ARG="DLS=1"; \
	$(MAKE) --trace -C tests basic-acceptance-tests -j 1 SUPASS=$(SUPASS) $${DLS_ARG} || (echo "Basic acceptance tests failed" && exit 1)
	@echo "DONE ==> Running basic acceptance tests"

# ============================= Lint ==================================

.PHONY: lint-all
lint-all: lint-python lint-javascript lint-cpp lint-shell lint-dockerfiles prettier-check
	@echo "==> Linting entire code base..."
	$(MAKE) lint-python
	@echo "DONE ==> Linting entire code base":

.PHONY: lint-python
lint-python: lint-python-pylint lint-python-flake8

.PHONY: lint-python-pylint
lint-python-pylint:
	@echo "==> Linting Python files - pylint..."
	@pylint ./*/src tests/* tools/* || (echo "Python linting failed" && exit 1)
	@echo "DONE ==> Linting Python files - pylint"

.PHONY: lint-python-flake8
lint-python-flake8:
	@echo "==> Linting Python files - flake8..."
	@flake8 || (echo "Python linting failed" && exit 1)
	@echo "DONE ==> Linting Python files - flake8"

.PHONY: lint-javascript
lint-javascript:
	@echo "==> Linting JavaScript files..."
	@find . -name '*.js'  | xargs npx eslint -c .github/resources/eslint.config.js --no-warn-ignored || (echo "Javascript linting failed" && exit 1)
	@echo "DONE ==> Linting JavaScript files"

.PHONY: lint-cpp
lint-cpp:
	@echo "==> Linting C++ files..."
	@find . -name '*.c' -o -name '*.cpp' -o -name '*.h'  | xargs cpplint || (echo "C++ linting failed" && exit 1)
	@echo "DONE ==> Linting C++ files"

.PHONY: lint-shell
SH_FILES := $(shell find . -type f \( -name '*.sh' \) -print )
lint-shell:
	@echo "==> Linting Shell files..."
	@shellcheck -x -S style $(SH_FILES) || (echo "Shell linting failed" && exit 1)
	@echo "DONE ==> Linting Shell files"

.PHONY: lint-dockerfiles
lint-dockerfiles:
	@echo "==> Linting Dockerfiles..."
	@find . -name '*Dockerfile*' | xargs hadolint || (echo "Dockerfile linting failed" && exit 1)
	@echo "DONE ==> Linting Dockerfiles"

.PHONY: prettier-check
prettier-check:
	@echo "==> Checking style with prettier..."
	@npx prettier --check . --ignore-path .gitignore --ignore-path .github/resources/.prettierignore --config .github/resources/.prettierrc.json  || (echo "Prettier check failed - run 'make prettier-write' to fix" && exit 1)
	@echo "DONE ==> Checking style with prettier"

# ===================== Format Code ================================

.PHONY: format-python
format-python:
	@echo "==> Formatting Python files..."
	@find . -name "*.py" -not -path "./venv/*" | xargs autopep8 --in-place --aggressive --aggressive || (echo "Python formatting failed" && exit 1)
	@echo "DONE ==> Formatting Python files"

.PHONY: prettier-write
prettier-write:
	@echo "==> Formatting code with prettier..."
	@npx prettier --write . --ignore-path .gitignore --ignore-path .github/resources/.prettierignore --config .github/resources/.prettierrc.json || (echo "Prettier formatting failed" && exit 1)
	@echo "DONE ==> Formatting code with prettier"

# ===================== Licensing Management ========================

.PHONY: add-licensing
add-licensing:
	@reuse annotate --template template $(ADDITIONAL_LICENSING_ARGS) --merge-copyrights --copyright-prefix="spdx-c" --copyright="Intel Corporation" --license="Apache-2.0" $(FILE) || (echo "Adding license failed" && exit 1)

# =========================== Coverity ==============================
.PHONY: build-coverity
build-coverity:
	@make -C scene_common/src/fast_geometry/ || (echo "scene_common/fast_geometry build failed" && exit 1)
	@export OpenCV_DIR=$${OpenCV_DIR:-$$(pkg-config --variable=pc_path opencv4 | cut -d':' -f1)} && cd controller/src/robot_vision && python3 setup.py bdist_wheel || (echo "robot vision build failed" && exit 1)
# ===================== Docker Compose Demo ==========================

.PHONY: convert-dls-videos
convert-dls-videos:
	@if [ "$${DLS}" = "1" ]; then \
	    $(MAKE) $(DLSTREAMER_SAMPLE_VIDEOS); \
	fi

.PHONY: init-sample-data
init-sample-data: convert-dls-videos
	@echo "Initializing sample data volume..."
	@docker volume create $(COMPOSE_PROJECT_NAME)_vol-sample-data 2>/dev/null || true
	@echo "Setting up volume permissions..."
	@docker run --rm -v $(COMPOSE_PROJECT_NAME)_vol-sample-data:/dest alpine:latest chown $(shell id -u):$(shell id -g) /dest
	@echo "Copying files from $(PWD)/sample_data to volume..."
	@if [ -d "$(PWD)/sample_data" ]; then \
	    docker run --rm \
	        -v $(PWD)/sample_data:/source:ro \
	        -v $(COMPOSE_PROJECT_NAME)_vol-sample-data:/dest \
	        --user $(shell id -u):$(shell id -g) \
	        alpine:latest \
	        sh -c "echo 'Copying files...'; cp -rv /source/* /dest/ && echo 'Copy completed successfully' || echo 'Copy failed'; echo '';"; \
	else \
	    echo "WARNING: Source directory $(PWD)/sample_data does not exist!"; \
	    exit 1; \
	fi
	@echo "Sample data volume initialized."

.PHONY: demo
demo: docker-compose.yml .env init-sample-data
	@if [ -z "$$SUPASS" ]; then \
	    echo "Please set the SUPASS environment variable before starting the demo for the first time."; \
	    echo "The SUPASS environment variable is the super user password for logging into Intel® SceneScape."; \
	    exit 1; \
	fi
	docker compose up -d
	@echo ""
	@echo "To stop SceneScape, type:"
	@echo "    docker compose down"

.PHONY: docker-compose.yml
docker-compose.yml:
	@if [ "$${DLS}" = "1" ]; then \
	    cp $(DLSTREAMER_DOCKER_COMPOSE_FILE) $@; \
	else \
	    cp $(PERCEBRO_DOCKER_COMPOSE_FILE) $@; \
	fi

$(DLSTREAMER_SAMPLE_VIDEOS): ./dlstreamer-pipeline-server/convert_video_to_ts.sh
	@echo "==> Converting sample videos for DLStreamer..."
	@./dlstreamer-pipeline-server/convert_video_to_ts.sh
	@echo "DONE ==> Converting sample videos for DLStreamer..."

.PHONY: .env
.env:
	@echo "SECRETSDIR=$(SECRETSDIR)" > $@
	@echo "VERSION=$(VERSION)" >> $@
	@echo "GID=$$(id -g)" >> $@
	@echo "UID=$$(id -u)" >> $@

# ======================= Secrets Management =========================

.PHONY: init-secrets
init-secrets: $(SECRETSDIR) certificates auth-secrets

$(SECRETSDIR):
	mkdir -p $@
	chmod go-rwx $(SECRETSDIR)

.PHONY: $(SECRETSDIR) certificates
certificates:
	@make -C ./tools/certificates CERTPASS=$$(openssl rand -base64 12) SECRETSDIR=$(SECRETSDIR) CERTDOMAIN=$(CERTDOMAIN)

.PHONY: auth-secrets
auth-secrets:
	$(MAKE) -C ./tools/authsecrets SECRETSDIR=$(SECRETSDIR)

# Database upgrade target
.PHONY: check-db-upgrade upgrade-database

check-db-upgrade:
	@if manager/tools/upgrade-database --check >/dev/null 2>&1; then \
		echo "Database upgrade is required."; \
		exit 0; \
	else \
		echo "No database upgrade needed."; \
		exit 1; \
	fi

upgrade-database:
	@echo "Starting database upgrade process..."
	@if ! manager/tools/upgrade-database --check >/dev/null 2>&1; then \
		echo "No database upgrade needed."; \
		exit 0; \
	fi
	@UPGRADE_LOG=/tmp/upgrade.$(shell date +%s).log; \
	echo "Upgrading database (log at $$UPGRADE_LOG)..."; \
	manager/tools/upgrade-database 2>&1 | tee $$UPGRADE_LOG; \
	NEW_DB=$$(grep -E 'Upgraded database .* has been created in Docker volumes' $$UPGRADE_LOG | sed -e 's/.*created in Docker volumes.*//'); \
	if [ $$? -ne 0 ]; then \
		echo ""; \
		echo "ABORTING"; \
		echo "Automatic upgrade of database failed"; \
		exit 1; \
	fi; \
	echo ""; \
	echo "Database upgrade completed successfully."; \
	echo "Database is now stored in Docker volumes:"; \
	echo "  - Database: scenescape_vol-db"; \
	echo "  - Migrations: scenescape_vol-migrations"
