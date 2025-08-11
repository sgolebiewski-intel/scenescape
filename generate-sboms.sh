export SERVICE=controller
mkdir -p build/$SERVICE
docker buildx build --sbom=true  --build-arg http_proxy=$http_proxy --build-arg https_proxy=$https_proxy --build-arg no_proxy=$no_proxy  -f $SERVICE/Dockerfile . -o type=tar,dest=build/$SERVICE/scenescape-$SERVICE.tar
cd build/$SERVICE
tar -xf scenescape-$SERVICE.tar sbom.spdx.json
../../generate-3rd-party-from-boms.py NOTICE.txt sbom.spdx.json
