# LANbu Handy - Development Container
# This container includes all dependencies needed for development and testing
# Based on the Bambu Studio CLI image like the main Dockerfile

FROM ghcr.io/depoll/lanbu-handy/bambu-studio-cli:latest

# Create a non-root user for development
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Install pip and development dependencies (Python 3.10 already available in base image)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-pip \
        python3-dev \
        # Basic development tools
        bash \
        bash-completion \
        git \
        curl \
        wget \
        vim \
        nano \
        sudo \
        # Network and system tools
        net-tools \
        lsof \
        procps \
        psmisc \
        iproute2 \
        dnsutils \
        telnet \
        htop \
        strace \
        tcpdump \
        jq \
        # Build tools and dependencies
        build-essential \
        pkg-config \
        # Locale support
        locales \
        gnupg2 \
        openssh-client \
        # Docker CLI (minimal)
        docker.io \
        # Dependencies for playwright browsers
        libnspr4 \
        libnss3 \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libatspi2.0-0 \
        libcairo2 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libglib2.0-0 \
        libgtk-3-0 \
        libpango-1.0-0 \
        libx11-6 \
        libx11-xcb1 \
        libxcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
        libxshmfence1 \
        libxtst6 \
        fonts-liberation \
        libegl1 \
        libgl1 \
        libgles2 \
        libvulkan1 \
        xvfb \
        # Additional fonts required by Playwright
        fonts-freefont-ttf \
        fonts-ipafont-gothic \
        fonts-noto-color-emoji \
        fonts-tlwg-loma-otf \
        fonts-unifont \
        fonts-wqy-zenhei \
        xfonts-cyrillic \
        xfonts-encodings \
        xfonts-scalable \
        xfonts-utils \
        libfontconfig1 \
        libfreetype6 \
        libwayland-client0 \
        # Powerline fonts for terminal
        fonts-powerline \
    && python3 -m pip install --upgrade pip \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3 1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Ensure bash is the default shell for devcontainer features compatibility
RUN ln -sf /bin/bash /bin/sh

# Install Docker Compose V2 plugin (latest stable version)
RUN DOCKER_COMPOSE_VERSION="v2.32.1" \
    && mkdir -p /usr/local/lib/docker/cli-plugins \
    && curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose \
    && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose \
    && docker compose version

# Configure locale
RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen en_US.UTF-8 && \
    update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# Create the user
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && usermod -aG docker $USERNAME

# Install Python development dependencies
COPY backend/requirements.txt /tmp/backend-requirements.txt
COPY backend/requirements-prod.txt /tmp/requirements-prod.txt
COPY backend/requirements-dev.txt /tmp/requirements-dev.txt
RUN python3 -m pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-cache-dir -r /tmp/backend-requirements.txt

# Install additional Python development and testing tools
RUN python3 -m pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-cache-dir \
    pytest==8.3.4 \
    pytest-asyncio==0.24.0 \
    pytest-cov==6.0.0 \
    black==25.1.0 \
    flake8==7.2.0 \
    mypy==1.14.0 \
    isort==6.0.1 \
    httpx==0.28.1 \
    requests==2.32.3

# Bambu Studio CLI is already available in the base image, no need to install it again

# Switch to non-root user
USER $USERNAME

# Set up workspace
WORKDIR /workspace

# Set environment variables for development
ENV PYTHONPATH=/workspace/backend
ENV NODE_ENV=development

# Default command
CMD ["sleep", "infinity"]
