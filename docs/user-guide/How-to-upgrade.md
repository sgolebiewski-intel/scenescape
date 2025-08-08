# How to Upgrade Intel® SceneScape

This guide provides step-by-step instructions to upgrade your Intel® SceneScape deployment to a new version. By completing this guide, you will:

- Migrate configuration and data directories.
- Deploy the latest version of Intel® SceneScape.
- Validate and troubleshoot common upgrade issues.

This task is essential for maintaining access to the latest features and fixes in Intel® SceneScape while preserving existing data and services.

## Prerequisites

Before You Begin, ensure the following:

- You have an existing Intel® SceneScape v1.3.0 installation with directories `db/`, `media/`, `migrations/`, `secrets/`, `model_installer/models/`, and a `docker-compose.yml` file.

# How to Upgrade Intel® SceneScape from v1.3.0

1. **Checkout latest SceneScape sources**:

   ```bash
   git checkout main
   ```

2. **Build the New Release**:

   ```bash
   make build-all
   ```

3. **Run the upgrade script**:

   ```bash
   bash manager/tools/upgrade-scenescape
   ```

4. **Bring up services to verify upgrade**:

   ```bash
   make demo
   ```

5. **Verify the volumes are created**:
   ```bash
   docker volume ls
   ```

   The results will look like:
   ```console
   local     scenescape_vol-datasets
   local     scenescape_vol-db
   local     scenescape_vol-dlstreamer-pipeline-server-pipeline-root
   local     scenescape_vol-media
   local     scenescape_vol-migrations
   local     scenescape_vol-models
   local     scenescape_vol-netvlad_models
   local     scenescape_vol-sample-data
   ```

6. **Log in to the Web UI** and verify that data and configurations are intact.

## Model Management During Upgrade

Starting from 1.4.0 version, Intel® SceneScape stores models in Docker volumes instead of the host filesystem. This provides several benefits:

- **Automatic Preservation**: Models are automatically preserved during upgrades as Docker volumes persist across container recreations.
- **No Manual Copy Required**: You no longer need to manually copy `model_installer/models/` during upgrades.
- **Reduced Disk Usage**: Models are not duplicated between host filesystem and containers.

## Troubleshooting

1. **pg_backup Container Already Running Error**:
   - Stop all active containers:
     ```bash
     docker stop $(docker ps -q)
     ```
   - Re-run the above steps for upgrade.
