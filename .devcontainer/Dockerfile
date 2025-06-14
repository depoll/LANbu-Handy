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
        git \
        curl \
        wget \
        vim \
        nano \
        sudo \
        # Build tools and dependencies
        build-essential \
        pkg-config \
        # Locale support
        locales \
        gnupg2 \
        openssh-client \
        # Docker CLI (minimal)
        docker.io \
    && python3 -m pip install --upgrade pip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

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

# Install Node.js 22.x from NodeSource repository
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

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

# Install global npm packages for development
RUN npm config set strict-ssl false && \
    npm install -g typescript@5.8.3 @types/node@22.15.29

# Switch to non-root user
USER $USERNAME

# Set up workspace
WORKDIR /workspace

# Set environment variables for development
ENV PYTHONPATH=/workspace/backend
ENV NODE_ENV=development

# Default command
CMD ["sleep", "infinity"]
