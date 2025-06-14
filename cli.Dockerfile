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

# ARM64-specific optimizations to prevent OOM during compilation
# RUN if [ "$(uname -m)" = "aarch64" ]; then \
#         echo "Applying ARM64 build optimizations..." && \
#         # Limit parallel jobs to reduce memory usage \
#         echo "export MAKEFLAGS='-j1'" >> /etc/environment && \
#         echo "ARM64 optimizations applied"; \
#     fi

# Clone Bambu Studio source
ARG BAMBU_VERSION=v02.01.00.59
RUN git clone --depth 1 --branch ${BAMBU_VERSION} https://github.com/bambulab/BambuStudio.git

WORKDIR /build/BambuStudio

# Build Bambu Studio using the official build script
# BuildLinux.sh sequence: -u (dependencies), -d (build deps), -s (studio)
RUN chmod +x BuildLinux.sh && \
    ./BuildLinux.sh -u

# Build dependencies with ARM64 optimizations
RUN if [ "$(uname -m)" = "aarch64" ]; then \
        # echo "Building dependencies with ARM64 optimizations..." && \
        # export MAKEFLAGS="-j1" && \
        # export CXXFLAGS="-O1" && \
        # export CFLAGS="-O1" && \
        ./BuildLinux.sh -d; \
    else \
        ./BuildLinux.sh -d; \
    fi

RUN ./BuildLinux.sh -s

# Install AppImage creation dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    imagemagick \
    squashfs-tools \
    file \
    fuse \
    desktop-file-utils \
    && rm -rf /var/lib/apt/lists/*

# Detect architecture and download appropriate linuxdeploy
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

# Create AppImage manually with correct architecture
RUN mkdir -p /tmp/appdir/usr/bin && \
    mkdir -p /tmp/appdir/usr/share/applications && \
    mkdir -p /tmp/appdir/usr/share/icons/hicolor/256x256/apps

# Find the built BambuStudio binary and copy it to AppImage structure
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

# Create a desktop file for the AppImage
RUN echo '[Desktop Entry]' > /tmp/appdir/usr/share/applications/BambuStudio.desktop && \
    echo 'Type=Application' >> /tmp/appdir/usr/share/applications/BambuStudio.desktop && \
    echo 'Name=BambuStudio' >> /tmp/appdir/usr/share/applications/BambuStudio.desktop && \
    echo 'Exec=BambuStudio' >> /tmp/appdir/usr/share/applications/BambuStudio.desktop && \
    echo 'Icon=BambuStudio' >> /tmp/appdir/usr/share/applications/BambuStudio.desktop && \
    echo 'Categories=Graphics;3DGraphics;' >> /tmp/appdir/usr/share/applications/BambuStudio.desktop

# Create a simple icon (if one doesn't exist)
RUN if [ ! -f /tmp/appdir/usr/share/icons/hicolor/256x256/apps/BambuStudio.png ]; then \
        echo "Creating placeholder icon" && \
        convert -size 256x256 xc:blue /tmp/appdir/usr/share/icons/hicolor/256x256/apps/BambuStudio.png 2>/dev/null || \
        touch /tmp/appdir/usr/share/icons/hicolor/256x256/apps/BambuStudio.png; \
    fi

# Create the AppImage with linuxdeploy
RUN cd /tmp && \
    ARCH=$(uname -m) && \
    ./linuxdeploy/AppRun --appdir appdir --output appimage --desktop-file appdir/usr/share/applications/BambuStudio.desktop

# Find and copy the built binary and AppImage
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


# Runtime stage
FROM ubuntu:22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive

# Install minimal runtime dependencies
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

# Copy the built binary
COPY --from=builder /usr/local/bin/BambuStudio.AppImage /usr/local/bin/BambuStudio.AppImage

# Make AppImage executable and extract it for containerized use
RUN chmod +x /usr/local/bin/BambuStudio.AppImage && \
    cd /tmp && \
    /usr/local/bin/BambuStudio.AppImage --appimage-extract && \
    mv squashfs-root /opt/BambuStudio && \
    ln -s /opt/BambuStudio/AppRun /usr/local/bin/bambu-studio-cli

# Test the installation
RUN bambu-studio-cli --help

CMD ["bambu-studio-cli", "--help"]

# Build Instructions:
# docker build -f docker/Dockerfile -t bambu-studio-cli:latest .
#
# Expected build time: 15-30 minutes depending on system
#
# The build process:
# 1. Uses Ubuntu 22.04 (officially supported)
# 2. Installs exact dependencies from Linux Compile Guide
# 3. Uses official BuildLinux.sh script with proper flags
# 4. Creates minimal runtime container with just the CLI
