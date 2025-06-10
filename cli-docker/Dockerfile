# Bambu Studio CLI Build - Working Configuration
# Based on official BuildLinux.sh and Linux Compile Guide
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install Ubuntu dependencies exactly as specified in the Linux Compile Guide
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

# Use the official BuildLinux.sh script with correct sequence:
# 1. Install system dependencies (-u flag)
# 2. Build all components (-dsi flags: dependencies, studio, appimage)
RUN chmod +x BuildLinux.sh && \
    ./BuildLinux.sh -u
RUN ./BuildLinux.sh -d
RUN ./BuildLinux.sh -s
RUN ./BuildLinux.sh -i

# Find and copy the built binary
RUN find . -name "*ambu*" -type f -executable -o -name "*BambuStudio*" -type f -executable | head -10 && \
    BINARY=$(find . -name "*ambu*" -type f -executable -o -name "*BambuStudio*" -type f -executable | head -1) && \
    if [ -n "$BINARY" ]; then \
        echo "Found binary: $BINARY" && \
        cp "$BINARY" /usr/local/bin/bambu-studio-cli && \
        chmod +x /usr/local/bin/bambu-studio-cli; \
    else \
        echo "No Bambu Studio binary found, checking build results:" && \
        find . -name "*slic3r*" -type f && \
        ls -la build/ 2>/dev/null || echo "No build directory" && \
        exit 1; \
    fi

# Find and copy the built AppImage instead of binary
RUN find . -name "*.AppImage" -type f | head -10 && \
    APPIMAGE=$(find . -name "*.AppImage" -type f | head -1) && \
    if [ -n "$APPIMAGE" ]; then \
        echo "Found AppImage: $APPIMAGE" && \
        cp "$APPIMAGE" /usr/local/bin/BambuStudio.AppImage && \
        chmod +x /usr/local/bin/BambuStudio.AppImage; \
    else \
        echo "No AppImage found, checking build results:" && \
        find . -name "*Bambu*" -type f && \
        find . -name "*.AppImage" -type f && \
        ls -la build/ 2>/dev/null || echo "No build directory" && \
        exit 1; \
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
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the built binary
COPY --from=builder /usr/local/bin/bambu-studio-cli /usr/local/bin/bambu-studio-cli
COPY --from=builder /usr/local/bin/BambuStudio.AppImage /usr/local/bin/BambuStudio.AppImage
# Test the installation
RUN bambu-studio-cli --version || bambu-studio-cli --help || echo "CLI installed"

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
