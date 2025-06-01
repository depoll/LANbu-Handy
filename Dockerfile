# LANbu Handy - All-in-One Docker Image
# Note: Build the PWA locally first with `cd pwa && npm run build`

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies that might be needed
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/ ./

# Copy built PWA static files
# Note: Run `cd pwa && npm run build` before building this Docker image
COPY pwa/dist/ ./static_pwa/

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]