# LANbu Handy - All-in-One Docker Image

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Node.js for PWA build
RUN apt-get update && apt-get install -y \
    curl \
    wget \
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

# Install Node.js from official Debian repos (might be older but more reliable)
RUN apt-get update && apt-get install -y nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-cache-dir -r backend/requirements.txt

# Install Bambu Studio CLI
COPY scripts/bambu-studio-version.txt /scripts/
COPY scripts/install-bambu-studio-cli.sh /tmp/
RUN chmod +x /tmp/install-bambu-studio-cli.sh && \
    /tmp/install-bambu-studio-cli.sh && \
    rm /tmp/install-bambu-studio-cli.sh

# Build PWA within Docker - with optimized settings
COPY pwa/package*.json ./pwa/
WORKDIR /app/pwa

# Try to install dependencies with timeout and optimizations
RUN timeout 120 npm ci --no-audit --no-fund --prefer-offline --progress=false || \
    (echo "NPM install timed out or failed. PWA build requires manual build step." && \
     mkdir -p /app/static_pwa && \
     echo "<html><body><h1>PWA Build Required</h1><p>Please build the PWA manually with 'cd pwa && npm run build' before running Docker build.</p></body></html>" > /app/static_pwa/index.html && \
     exit 0)

# Copy PWA source and build it (only if npm ci succeeded)
COPY pwa/ ./
RUN if [ -d "node_modules" ]; then \
        npm run build && \
        mkdir -p /app/static_pwa && \
        cp -r dist/* /app/static_pwa/; \
    else \
        echo "Skipping PWA build due to dependency installation failure"; \
    fi

# Return to main working directory and copy backend
WORKDIR /app
COPY backend/ ./

# Ensure static_pwa directory exists with fallback content if needed
RUN mkdir -p ./static_pwa && \
    if [ ! -f "./static_pwa/index.html" ]; then \
        echo "<html><body><h1>PWA Build Required</h1><p>Please build the PWA manually with 'cd pwa && npm run build' and rebuild the Docker image.</p></body></html>" > ./static_pwa/index.html; \
    fi

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]