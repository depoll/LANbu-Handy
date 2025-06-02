# LANbu Handy - Development Container
# This container includes all dependencies needed for development and testing

FROM python:3.12-slim

# Create a non-root user for development
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Install system dependencies for Bambu Studio CLI and development tools
RUN apt-get update && apt-get install -y \
    # Basic development tools
    git \
    curl \
    wget \
    vim \
    nano \
    sudo \
    # Build tools and dependencies
    build-essential \
    pkg-config \
    # Bambu Studio CLI dependencies
    binutils \
    fuse \
    libfuse2 \
    libxcb1 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-render0 \
    libxcb-shape0 \
    libxcb-sync1 \
    libxcb-util1 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    libxkbcommon0 \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js from Debian packages (version 18+ available in bookworm)
RUN apt-get update && apt-get install -y nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Create the user
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Install Python development dependencies
COPY ../backend/requirements.txt /tmp/backend-requirements.txt
RUN pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-cache-dir -r /tmp/backend-requirements.txt

# Install additional Python development and testing tools
RUN pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    black \
    flake8 \
    mypy \
    isort \
    httpx \
    requests

# Install Bambu Studio CLI
COPY ../scripts/bambu-studio-version.txt /scripts/
COPY ../scripts/install-bambu-studio-cli.sh /tmp/
RUN chmod +x /tmp/install-bambu-studio-cli.sh && \
    /tmp/install-bambu-studio-cli.sh && \
    rm /tmp/install-bambu-studio-cli.sh

# Install global npm packages for development
RUN npm config set strict-ssl false && \
    npm install -g typescript@5.8.3 @types/node

# Set up workspace
WORKDIR /workspace

# Switch to non-root user
USER $USERNAME

# Set environment variables for development
ENV PYTHONPATH=/workspace/backend
ENV NODE_ENV=development

# Default command
CMD ["sleep", "infinity"]