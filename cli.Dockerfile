# Bambu Studio CLI with AppImage Build
# Multi-stage build: creates both CLI binary and self-contained AppImage
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install build dependencies required by Bambu Studio's Linux Compile Guide
RUN apt-get update && \
    apt-get install -y \
    cmake \
    clang \
    git \
    g++ \
    build-essential \
    libgl1-mesa-dev \
    libgtk-3-dev \
    libegl1-mesa-dev \
    libgles2-mesa-dev \
    libdbus-1-dev \
    libglib2.0-dev \
    curl \
    wget \
    pkg-config \
    ca-certificates \
    sudo \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Set up build environment with proper settings
WORKDIR /build
ENV SKIP_RAM_CHECK=1

# Clone Bambu Studio source
ARG BAMBU_VERSION=v02.01.00.59
RUN git clone --depth 1 --branch ${BAMBU_VERSION} https://github.com/bambulab/BambuStudio.git

WORKDIR /build/BambuStudio

# Build Bambu Studio using the official build script
# BuildLinux.sh sequence: -u (dependencies), -d (build deps), -s (studio)
RUN chmod +x BuildLinux.sh && \
    ./BuildLinux.sh -u
RUN ./BuildLinux.sh -d
RUN ./BuildLinux.sh -s

# Install tools needed for AppImage creation
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    imagemagick \
    squashfs-tools \
    file \
    fuse \
    desktop-file-utils \
    && rm -rf /var/lib/apt/lists/*

# Download linuxdeploy for the target architecture (x86_64 or aarch64)
RUN ARCH=$(uname -m) && \
    echo "Detected architecture: $ARCH" && \
    if [ "$ARCH" = "x86_64" ]; then \
        LINUXDEPLOY_ARCH="x86_64"; \
    elif [ "$ARCH" = "aarch64" ]; then \
        LINUXDEPLOY_ARCH="aarch64"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    echo "Using linuxdeploy for: $LINUXDEPLOY_ARCH" && \
    wget -O /tmp/linuxdeploy-${LINUXDEPLOY_ARCH}.AppImage https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-${LINUXDEPLOY_ARCH}.AppImage && \
    chmod +x /tmp/linuxdeploy-${LINUXDEPLOY_ARCH}.AppImage && \
    cd /tmp && ./linuxdeploy-${LINUXDEPLOY_ARCH}.AppImage --appimage-extract && \
    mv squashfs-root linuxdeploy && \
    chmod +x linuxdeploy/AppRun

# Set up AppImage directory structure following FreeDesktop standards
RUN mkdir -p /tmp/appdir/usr/bin && \
    mkdir -p /tmp/appdir/usr/share/applications && \
    mkdir -p /tmp/appdir/usr/share/icons/hicolor/256x256/apps

# Locate the compiled Bambu Studio binary and prepare it for AppImage packaging
RUN BINARY=$(find build -name "bambu-studio" -o -name "BambuStudio" -type f -executable | head -1) && \
    if [ -n "$BINARY" ]; then \
        echo "Found BambuStudio binary: $BINARY" && \
        cp "$BINARY" /tmp/appdir/usr/bin/BambuStudio && \
        chmod +x /tmp/appdir/usr/bin/BambuStudio; \
    else \
        echo "No BambuStudio binary found in build directory" && \
        find . -name "*ambu*" -type f -executable && \
        exit 1; \
    fi

# Generate desktop entry file required for AppImage
RUN echo '[Desktop Entry]' > /tmp/appdir/usr/share/applications/BambuStudio.desktop && \
    echo 'Type=Application' >> /tmp/appdir/usr/share/applications/BambuStudio.desktop && \
    echo 'Name=BambuStudio' >> /tmp/appdir/usr/share/applications/BambuStudio.desktop && \
    echo 'Exec=BambuStudio' >> /tmp/appdir/usr/share/applications/BambuStudio.desktop && \
    echo 'Icon=BambuStudio' >> /tmp/appdir/usr/share/applications/BambuStudio.desktop && \
    echo 'Categories=Graphics;3DGraphics;' >> /tmp/appdir/usr/share/applications/BambuStudio.desktop

# Create placeholder icon if none exists in the source
RUN if [ ! -f /tmp/appdir/usr/share/icons/hicolor/256x256/apps/BambuStudio.png ]; then \
        echo "Creating placeholder icon" && \
        convert -size 256x256 xc:blue /tmp/appdir/usr/share/icons/hicolor/256x256/apps/BambuStudio.png 2>/dev/null || \
        touch /tmp/appdir/usr/share/icons/hicolor/256x256/apps/BambuStudio.png; \
    fi

# Package everything into a self-contained AppImage using linuxdeploy
RUN cd /tmp && \
    ARCH=$(uname -m) && \
    ./linuxdeploy/AppRun --appdir appdir --output appimage --desktop-file appdir/usr/share/applications/BambuStudio.desktop

# Copy both the CLI binary and AppImage to final locations for runtime stage
RUN find /tmp -name "*.AppImage" -type f && \
    APPIMAGE=$(find /tmp -name "*.AppImage" -type f | head -1) && \
    BINARY=$(find build -name "bambu-studio" -o -name "BambuStudio" -type f -executable | head -1) && \
    if [ -n "$BINARY" ]; then \
        echo "Found binary: $BINARY" && \
        cp "$BINARY" /usr/local/bin/bambu-studio-cli && \
        chmod +x /usr/local/bin/bambu-studio-cli; \
    else \
        echo "No Bambu Studio binary found, checking build results:" && \
        find . -name "*slic3r*" -type f && \
        ls -la build/ 2>/dev/null || echo "No build directory" && \
        exit 1; \
    fi && \
    if [ -n "$APPIMAGE" ]; then \
        echo "Found AppImage: $APPIMAGE" && \
        cp "$APPIMAGE" /usr/local/bin/BambuStudio.AppImage && \
        chmod +x /usr/local/bin/BambuStudio.AppImage; \
    else \
        echo "Warning: No AppImage created"; \
    fi


# Runtime stage - minimal Ubuntu with only necessary dependencies
FROM ubuntu:22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive

# Install minimal runtime libraries required by Bambu Studio CLI
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libcurl4 \
    libssl3 \
    libgl1-mesa-glx \
    libgtk-3-0 \
    libegl1 \
    software-properties-common \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the self-contained AppImage from builder stage
COPY --from=builder /usr/local/bin/BambuStudio.AppImage /usr/local/bin/BambuStudio.AppImage

# Extract AppImage for headless/containerized use (avoids FUSE requirement)
# This creates a usable CLI even in environments without FUSE support
RUN chmod +x /usr/local/bin/BambuStudio.AppImage && \
    cd /tmp && \
    /usr/local/bin/BambuStudio.AppImage --appimage-extract && \
    mv squashfs-root /opt/BambuStudio && \
    ln -s /opt/BambuStudio/AppRun /usr/local/bin/bambu-studio-cli

# Verify the CLI installation works in headless mode
RUN bambu-studio-cli --help

CMD ["bambu-studio-cli", "--help"]

# Build Instructions:
# docker build -f cli.Dockerfile -t bambu-studio-cli:latest .
#
# Usage:
# - CLI Binary: docker run bambu-studio-cli bambu-studio-cli --help
# - AppImage: docker run bambu-studio-cli /usr/local/bin/BambuStudio.AppImage --help
#
# Expected build time: 15-30 minutes depending on system specs
#
# Architecture support: x86_64 and aarch64 (ARM64)
# The AppImage bundles all dependencies for maximum portability
