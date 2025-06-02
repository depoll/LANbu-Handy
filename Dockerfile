# LANbu Handy - All-in-One Docker Image (Multi-stage Build)

# Stage 1: PWA Build Stage
FROM node:18-slim AS pwa-builder

WORKDIR /app/pwa

# Copy package files first for better layer caching
COPY pwa/package*.json ./

# Configure npm for restrictive environments and install dependencies
RUN npm config set strict-ssl false && \
    npm config set registry https://registry.npmjs.org/ && \
    npm install -g typescript@5.8.3 && \
    npm ci --no-audit --no-fund --prefer-offline --progress=false || npm install --no-audit --no-fund

# Copy PWA source and build
COPY pwa/ ./
RUN npm run build

# Stage 2: Python Runtime Stage
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-cache-dir -r backend/requirements.txt

# Install Bambu Studio CLI and dependencies
COPY scripts/bambu-studio-version.txt /scripts/
COPY scripts/install-bambu-studio-cli.sh /tmp/
RUN chmod +x /tmp/install-bambu-studio-cli.sh && \
    /tmp/install-bambu-studio-cli.sh && \
    rm /tmp/install-bambu-studio-cli.sh

# Copy backend application
COPY backend/ ./

# Copy built PWA from the build stage
COPY --from=pwa-builder /app/pwa/dist ./static_pwa

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]