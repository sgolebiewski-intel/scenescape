export IMAGE=controller
mkdir -p sboms/$IMAGE
docker buildx build --sbom=true  --build-arg http_proxy=$http_proxy --build-arg https_proxy=$https_proxy --build-arg no_proxy=$no_proxy  -f $IMAGE/Dockerfile . -o type=tar,dest=sboms/$IMAGE/scenescape-$IMAGE.tar
cd sboms/$IMAGE
tar -xf scenescape-$IMAGE.tar sbom.spdx.json
../../generate-3rd-party-and-GPL-from-boms.py NOTICE.txt sbom.spdx.json
cd -

export IMAGE=manager
mkdir -p sboms/$IMAGE
docker buildx build --sbom=true  --build-arg http_proxy=$http_proxy --build-arg https_proxy=$https_proxy --build-arg no_proxy=$no_proxy  -f $IMAGE/Dockerfile . -o type=tar,dest=sboms/$IMAGE/scenescape-$IMAGE.tar
cd sboms/$IMAGE
tar -xf scenescape-$IMAGE.tar sbom.spdx.json
../../generate-3rd-party-and-GPL-from-boms.py NOTICE.txt sbom.spdx.json
cd -

export IMAGE=common-base
mkdir -p sboms/$IMAGE
docker buildx build --sbom=true  --build-arg http_proxy=$http_proxy --build-arg https_proxy=$https_proxy --build-arg no_proxy=$no_proxy  -f scene-common/Dockerfile . -o type=tar,dest=sboms/$IMAGE/scenescape-$IMAGE.tar
cd sboms/$IMAGE
tar -xf scenescape-$IMAGE.tar sbom.spdx.json
../../generate-3rd-party-and-GPL-from-boms.py NOTICE.txt sbom.spdx.json
cd -

export IMAGE=camcalibration
mkdir -p sboms/$IMAGE
docker buildx build --sbom=true  --build-arg http_proxy=$http_proxy --build-arg https_proxy=$https_proxy --build-arg no_proxy=$no_proxy  -f autocalibration/Dockerfile . -o type=tar,dest=sboms/$IMAGE/scenescape-$IMAGE.tar
cd sboms/$IMAGE
tar -xf scenescape-$IMAGE.tar sbom.spdx.json
../../generate-3rd-party-and-GPL-from-boms.py NOTICE.txt sbom.spdx.json
cd -

export IMAGE=model-installer
mkdir -p sboms/$IMAGE
docker buildx build --sbom=true  --build-arg http_proxy=$http_proxy --build-arg https_proxy=$https_proxy --build-arg no_proxy=$no_proxy  -f model_installer/Dockerfile . -o type=tar,dest=sboms/$IMAGE/scenescape-$IMAGE.tar
cd sboms/$IMAGE
tar -xf scenescape-$IMAGE.tar sbom.spdx.json
../../generate-3rd-party-and-GPL-from-boms.py NOTICE.txt sbom.spdx.json
cd -

export IMAGE=init-secrets
mkdir -p sboms/$IMAGE
docker buildx build --sbom=true  --build-arg http_proxy=$http_proxy --build-arg https_proxy=$https_proxy --build-arg no_proxy=$no_proxy  -f kubernetes/init-images/Dockerfile-secrets . -o type=tar,dest=sboms/$IMAGE/scenescape-$IMAGE.tar
cd sboms/$IMAGE
tar -xf scenescape-$IMAGE.tar sbom.spdx.json
../../generate-3rd-party-and-GPL-from-boms.py NOTICE.txt sbom.spdx.json
cd -

export IMAGE=init-models
mkdir -p sboms/$IMAGE
docker buildx build --sbom=true  --build-arg http_proxy=$http_proxy --build-arg https_proxy=$https_proxy --build-arg no_proxy=$no_proxy  -f kubernetes/init-images/Dockerfile-models . -o type=tar,dest=sboms/$IMAGE/scenescape-$IMAGE.tar
cd sboms/$IMAGE
tar -xf scenescape-$IMAGE.tar sbom.spdx.json
../../generate-3rd-party-and-GPL-from-boms.py NOTICE.txt sbom.spdx.json
cd -

export IMAGE=init-tests
mkdir -p sboms/$IMAGE
docker buildx build --sbom=true  --build-arg http_proxy=$http_proxy --build-arg https_proxy=$https_proxy --build-arg no_proxy=$no_proxy  -f kubernetes/init-images/Dockerfile-tests . -o type=tar,dest=sboms/$IMAGE/scenescape-$IMAGE.tar
cd sboms/$IMAGE
tar -xf scenescape-$IMAGE.tar sbom.spdx.json
../../generate-3rd-party-and-GPL-from-boms.py NOTICE.txt sbom.spdx.json
cd -
