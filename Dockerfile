# LANbu Handy - All-in-One Docker Image (Optimized Multi-stage Build)
# Note: Platform forced via docker-compose.yml for Bambu Studio CLI compatibility

# Stage 1: PWA Build Stage
FROM node:18-slim AS pwa-builder

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

# Stage 2: Python Runtime Stage
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN groupadd -r lanbu && \
    useradd -r -g lanbu -u 1001 -d /app -s /bin/bash lanbu && \
    mkdir -p /app && \
    chown -R lanbu:lanbu /app

# Install Bambu Studio CLI and dependencies (with essential CLI deps)
COPY scripts/bambu-studio-version.txt /scripts/
COPY scripts/install-bambu-studio-cli.sh /tmp/
RUN chmod +x /tmp/install-bambu-studio-cli.sh && \
    MINIMAL_DEPS=true /tmp/install-bambu-studio-cli.sh && \
    rm -f /tmp/install-bambu-studio-cli.sh

# Copy and install Python dependencies (production only)
COPY backend/requirements-prod.txt ./backend/
RUN pip install --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    --no-cache-dir \
    -r backend/requirements-prod.txt && \
    pip cache purge

# Copy backend application and set proper ownership
COPY backend/ ./
RUN chown -R lanbu:lanbu /app

# Copy built PWA from the build stage and set proper ownership
COPY --from=pwa-builder --chown=lanbu:lanbu /app/pwa/dist ./static_pwa

# Switch to non-root user
USER lanbu

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
