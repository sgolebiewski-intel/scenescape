# -------------------
# Stage 1: Builder
# -------------------
FROM ubuntu:22.04 as builder

USER root
SHELL ["/bin/bash", "-e", "-o", "pipefail", "-c"]

ARG CERTDOMAIN=scenescape.intel.com

ENV DEBIAN_FRONTEND=noninteractive

COPY requirements-buildtime.txt /tmp

RUN apt-get update && apt-get install -y --no-install-recommends \
        bzip2 \
        curl \
        g++ \
        libboost-python-dev \
        libegl1 \
        libeigen3-dev \
        libgl1 \
        libglib2.0 \
        libgtest-dev \
        make \
        pybind11-dev \
        python-is-python3 \
        python3-dev \
        python3-pip \
        python3-scipy \
    && pip3 install --upgrade --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r /tmp/requirements-buildtime.txt

# Copy and build SceneScape and scene_common
ADD SceneScape.tar /tmp/
ADD scene_common.tar /tmp/
RUN : \
    ; cd tmp/scene_common \
    ; pip install --no-cache-dir . \
    ; make -C fast_geometry -j $(nproc) all install \
    ;

# -------------------
# Stage 2: Runtime
# -------------------
FROM ubuntu:22.04

USER root
SHELL ["/bin/bash", "-e", "-o", "pipefail", "-c"]

ARG USER_ID
ARG CERTDOMAIN=scenescape.intel.com

ENV DEBIAN_FRONTEND=noninteractive
ENV WSUSER=scenescape
ENV SCENESCAPE_HOME=/home/$WSUSER/SceneScape

COPY requirements-runtime.txt /tmp

# Runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        apache2 \
        bindfs \
        curl \
        libegl1 \
        libgl1 \
        libglib2.0 \
        libapache2-mod-wsgi-py3 \
        libapache2-mod-qos \
        mosquitto-clients \
        netcat \
        postgresql \
        python-is-python3 \
        python3-pip \
        python3-scipy \
        sudo \
    && pip3 install --upgrade --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r /tmp/requirements-runtime.txt

RUN : \
    ; PSQLVER=$(ls /etc/postgresql) \
    ; echo "host all  all    0.0.0.0/0  md5" >> "/etc/postgresql/${PSQLVER}/main/pg_hba.conf" \
    ; echo "listen_addresses='*'" >> "/etc/postgresql/${PSQLVER}/main/postgresql.conf" \
    ;

RUN : \
    ; a2dismod -f \
          auth_basic \
          authn_core \
          authn_file \
          authz_host \
          authz_user \
          autoindex \
          status \
    ; a2enmod \
        allowmethods \
        headers \
        proxy \
        proxy_wstunnel \
        ssl \
    ; a2ensite default-ssl \
    ;

# mod_qos configuration
RUN cat > /etc/apache2/mods-available/qos.conf <<EOF
<IfModule qos_module>
   QS_ClientEntries 100000
   QS_SrvMaxConnPerIP 50
   MaxClients 256
   QS_SrvMaxConnClose 180
   QS_SrvMinDataRate 150 1200
</IfModule>
EOF

# Apache configuration
COPY 000-default.conf default-ssl.conf /etc/apache2/sites-available/
COPY apache2.conf /etc/apache2/
RUN : \
    ; sed -i "s/scenescape.intel.com/$CERTDOMAIN/g" /etc/apache2/sites-available/default-ssl.conf \
    ; chmod og-w /etc/apache2/sites-available/*.conf /etc/apache2/apache2.conf

# Add application user
RUN useradd -r -m -s /bin/bash $WSUSER && \
    usermod -a -G video,users $WSUSER && \
    chmod a+rX /home/$WSUSER

# Copy Python environment from builder
COPY --from=builder /usr/local/lib/python3.*/dist-packages /usr/local/lib/python3.*/dist-packages
COPY --from=builder /tmp/sscape $SCENESCAPE_HOME/sscape
COPY --from=builder /tmp/manage.py $SCENESCAPE_HOME/
COPY --from=builder /usr/local/lib/python3.10/dist-packages/fast_geometry /usr/local/lib/python3.10/dist-packages/fast_geometry
COPY --from=builder /usr/local/lib/python3.10/dist-packages/scene_common /usr/local/lib/python3.10/dist-packages/scene_common

# Install SceneScape
RUN : \
    ; eval WSHOME=~$WSUSER \
    ; chown -R "$WSUSER" "$WSHOME/SceneScape" \
    ; touch "$WSHOME/SceneScape/sscape/settings_local.py" \
    ; chown "$WSUSER.$WSUSER" "$WSHOME/SceneScape/sscape/settings_local.py" \
    ; pip3 install --no-cache-dir "$SCENESCAPE_HOME/sscape/" \
    ;

# Web assets
COPY --chown=${USER_ID} editor/js $SCENESCAPE_HOME/sscape/static/js/editor
COPY --chown=${USER_ID} editor/images $SCENESCAPE_HOME/sscape/static/images
COPY --chown=${USER_ID} editor/css $SCENESCAPE_HOME/sscape/static/css
COPY --chown=${USER_ID} jslibs/assets $SCENESCAPE_HOME/sscape/static/assets
COPY --chown=${USER_ID} jslibs/examples $SCENESCAPE_HOME/sscape/static/examples
COPY --chown=${USER_ID} jslibs/bootstrap $SCENESCAPE_HOME/sscape/static/bootstrap

RUN chmod -R u=rwX,go=rX $SCENESCAPE_HOME/sscape/static/js/editor/ \
    $SCENESCAPE_HOME/sscape/static/examples/ && \
    OPENCV_SHA=$(openssl dgst -sha256 -binary $SCENESCAPE_HOME/sscape/static/assets/opencv.js | openssl base64) && \
    sed -i "s|sha256-opencv|sha256-$OPENCV_SHA|g" /etc/apache2/sites-available/000-default.conf

# Copy init scripts
COPY scenescape-init database-init webserver-init /usr/local/bin/

ENTRYPOINT ["/usr/local/bin/scenescape-init"]
