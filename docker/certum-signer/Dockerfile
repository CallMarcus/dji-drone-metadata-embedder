# syntax=docker/dockerfile:1
#
# Certum SimplySign signing image for the release workflows.
#
# SimplySign (Certum's cloud HSM) has no headless signing API: the private key
# is only reachable through the SimplySign Desktop GUI, which exposes it as a
# PKCS#11 token. This image bakes in everything the sign jobs need to run that
# GUI headlessly - SimplySign Desktop (~313 MB installer from Certum's slow EU
# host), the X/Qt/PKCS#11 runtime stack, jsign (Authenticode signing) and
# osslsigncode (signature verification) - so a sign run pulls one image
# instead of re-downloading and apt-installing everything every release.
#
# Adapted from reactiveui/actions-common (docker/certum-signer, MIT) and
# hpvb/certum-container. Their .NET SDK base is dropped: we sign .exe files
# with jsign, not NuGet packages.
#
# Build & push via .github/workflows/signer-image.yml (manual dispatch).
# Consumed by .github/actions/certum-sign via the SS_DIST/JSIGN_JAR contract.

FROM ubuntu:24.04

# SimplySign Desktop Linux (Ubuntu) installer. No Renovate datasource exists
# for Certum's file host, so bump this manually when Certum ships a new
# version - and re-run sign-test.yml after any bump: a SimplySign UI change
# can break the xdotool login scripting in the certum-sign action.
# Checksum-verified pins, matching the repo convention for bundled tooling
# (FFmpeg in release-installer.yml, ExifTool in utils/provision.py):
# bumps change the pin AND the checksum, nothing else.
ARG SIMPLYSIGN_BIN_URL=https://files.certum.eu/software/SimplySignDesktop/Linux-Ubuntu/2.9.14-9.4.3.0/SimplySignDesktop-2.9.14-9.4.3.0-x86_64-prod-ubuntu.bin
ARG SIMPLYSIGN_SHA256=e462dc83679f9987d4e8419c9b4db30e11884bffd875e85e142ac77aad7233e8
ARG JSIGN_VERSION=7.5
ARG JSIGN_SHA256=602a51c3545a6dc4fb99bd2ea7152b26d1345916d0c93ddfbd5936cb735af91c

ENV DEBIAN_FRONTEND=noninteractive

# Headless X (Xvfb + fluxbox), UI automation (xdotool/wmctrl), PKCS#11
# tooling, Java for jsign, osslsigncode for verification, git for
# actions/checkout, and the Qt5/WebKit + misc system libs SimplySign needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
      xvfb x11-utils xdotool wmctrl fluxbox \
      opensc opensc-pkcs11 default-jre-headless osslsigncode \
      unzip openssl ca-certificates curl python3 git procps \
      libx11-6 libxext6 libxcomposite1 libxi6 libice6 libsm6 libxrender1 \
      libxcb1 libxau6 libpcsclite1 libglx-mesa0 libgl1 libxslt1.1 \
      libxkbcommon0 libxcb-xinerama0 libfontconfig1 libdbus-1-3 \
      libpulse-mainloop-glib0 libpulse0 libasound2t64 \
      libqt5webkit5 libqt5multimedia5 libqt5multimediawidgets5 libqt5quick5 \
      libqt5printsupport5 libqt5positioning5 libqt5sensors5 libqt5opengl5 \
      libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 \
      libwoff1 libharfbuzz0b libhyphen0 libwebp7 libwebpdemux2 \
      libnss3 libxtst6 libxss1 libxrandr2 libxdamage1 libxfixes3 libxcursor1 \
      libegl1 libgbm1 libxkbcommon-x11-0 \
    && rm -rf /var/lib/apt/lists/*

# Install SimplySign Desktop. The bundled SimplySignDesktop_start wrapper
# hardcodes /opt/SimplySignDesktop/SimplySignDesktop, so the dist MUST live
# there (mirrors hpvb/certum-container). Extract to a temp dir, then move the
# dist into place and drop the installer + temp to keep the layer smaller.
RUN curl -fsSL -o /tmp/ss.bin "$SIMPLYSIGN_BIN_URL" \
    && echo "$SIMPLYSIGN_SHA256  /tmp/ss.bin" | sha256sum -c \
    && mkdir -p /tmp/ss-extract \
    && (yes yes | sh /tmp/ss.bin --target /tmp/ss-extract || true) \
    && mv "$(find /tmp/ss-extract -maxdepth 1 -type d -name 'SSD-*-dist' | head -1)" /opt/SimplySignDesktop \
    && rm -rf /tmp/ss.bin /tmp/ss-extract \
    && test -x /opt/SimplySignDesktop/SimplySignDesktop

# jsign (Authenticode signing over PKCS#11).
RUN curl -fsSL -o /opt/jsign.jar "https://repo1.maven.org/maven2/net/jsign/jsign/${JSIGN_VERSION}/jsign-${JSIGN_VERSION}.jar" \
    && echo "$JSIGN_SHA256  /opt/jsign.jar" | sha256sum -c

# Contract consumed by the certum-sign action.
#
# USER=root: SimplySignDesktop reads $USER at startup and segfaults (NULL
# deref in its bundled OpenSSL) when it is unset. Container jobs don't set
# $USER, so bake a default in - without it the login window never appears.
ENV USER=root \
    SS_DIST=/opt/SimplySignDesktop \
    JSIGN_JAR=/opt/jsign.jar \
    LD_LIBRARY_PATH=/opt/SimplySignDesktop

LABEL org.opencontainers.image.title="Certum SimplySign signer" \
      org.opencontainers.image.description="SimplySign Desktop + jsign + osslsigncode for headless Authenticode signing on Linux" \
      org.opencontainers.image.source="https://github.com/CallMarcus/dji-drone-metadata-embedder"
