# LANbu Handy - All-in-One Docker Image (Multi-stage Build)
# Base: Published Bambu Studio CLI image with Python runtime added

# Stage 1: PWA Build Stage
FROM node:22-slim AS pwa-builder

WORKDIR /app/pwa

# Copy package files first for better layer caching
COPY pwa/package*.json ./

# Configure npm for restrictive environments and install dependencies
RUN npm config set strict-ssl false && \
    npm config set registry https://registry.npmjs.org/ && \
    npm install -g typescript@5.8.3 && \
    (npm ci --no-audit --no-fund --prefer-offline --progress=false || npm install --no-audit --no-fund) && \
    npm cache clean --force

# Copy PWA source and build
COPY pwa/ ./
RUN npm run build

# Stage 2: Main Runtime Stage
FROM ghcr.io/depoll/lanbu-handy/bambu-studio-cli:latest

# Set working directory
WORKDIR /app

# Install pip and upgrade it (Python 3.10 already available in base image)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-pip \
        python3-dev \
    && python3 -m pip install --upgrade pip \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r lanbu && \
    useradd -r -g lanbu -u 1001 -d /app -s /bin/bash lanbu && \
    mkdir -p /app && \
    chown -R lanbu:lanbu /app

# Copy and install Python dependencies (production only)
COPY backend/requirements-prod.txt ./backend/
RUN python3 -m pip install --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    --no-cache-dir \
    -r backend/requirements-prod.txt && \
    python3 -m pip cache purge

# Copy backend application and set proper ownership
COPY backend/ ./
RUN chown -R lanbu:lanbu /app

# Copy built PWA from the build stage and set proper ownership
COPY --from=pwa-builder --chown=lanbu:lanbu /app/pwa/dist ./static_pwa

# Create symlink to Bambu Studio resources from the base image
# TODO: Remove the conditional check once CLI images are rebuilt with resources
RUN if [ -d /opt/bambu-studio-resources ]; then \
        echo "Found Bambu Studio resources, creating symlink..." && \
        ln -s /opt/bambu-studio-resources ./bambu-studio-resources && \
        chown -h lanbu:lanbu ./bambu-studio-resources; \
    else \
        echo "Bambu Studio resources not found in base image (CLI image needs rebuild)" && \
        mkdir -p ./bambu-studio-resources && \
        chown lanbu:lanbu ./bambu-studio-resources && \
        echo "Created empty resources directory as placeholder"; \
    fi

# Switch to non-root user
USER lanbu

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
