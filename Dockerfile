# LANbu Handy - All-in-One Docker Image
# Note: Build the PWA locally first with `cd pwa && npm run build`

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies that might be needed
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
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-cache-dir -r requirements.txt

# Install Bambu Studio CLI
COPY scripts/bambu-studio-version.txt /scripts/
COPY scripts/install-bambu-studio-cli.sh /tmp/
RUN chmod +x /tmp/install-bambu-studio-cli.sh && \
    /tmp/install-bambu-studio-cli.sh && \
    rm /tmp/install-bambu-studio-cli.sh

# Copy backend application code
COPY backend/ ./

# Copy built PWA static files
# Note: Run `cd pwa && npm run build` before building this Docker image
COPY pwa/dist/ ./static_pwa/

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]