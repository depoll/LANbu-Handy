# LANbu Handy Dev Container

This development container provides a complete environment for developing and testing LANbu Handy with all dependencies pre-installed.

## What's Included

### Architecture Requirements

- **Platform**: Forced to `linux/amd64` for Bambu Studio CLI compatibility
- **Apple Silicon Macs**: Uses Rosetta emulation automatically via Docker Desktop

### System Dependencies

- **Python 3.12** with FastAPI development environment
- **Node.js 18.x** with npm for PWA development
- **Bambu Studio CLI** (same as production environment)
- Development tools: git, vim, nano, curl, wget

### Python Development Tools

- **FastAPI & Uvicorn** (backend framework)
- **pytest & pytest-asyncio** (testing framework)
- **pytest-cov** (test coverage)
- **black** (code formatter)
- **flake8** (linter)
- **mypy** (type checker)
- **isort** (import sorter)
- **httpx & requests** (HTTP clients for testing)

### Frontend Development Tools

- **TypeScript 5.8.3** (globally installed)
- **@types/node** (TypeScript definitions)

## Usage

### Using with VS Code Dev Containers Extension

1. Install the "Dev Containers" extension in VS Code
2. Open the project in VS Code
3. When prompted, click "Reopen in Container" or use `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"
4. The container will build automatically and VS Code will connect to it

### Manual Docker Compose Usage

```bash
# Start the dev container
cd .devcontainer
docker compose up -d

# Connect to the container
docker compose exec dev bash

# Stop the container
docker compose down
```

## Development Workflow

### Backend Development

```bash
# Inside the container at /workspace
cd backend

# Run linting
flake8 .

# Format code
black .

# Type checking
mypy .

# Run tests (when created)
pytest

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
# Inside the container at /workspace
cd pwa

# Install dependencies (if not already installed)
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run linting
npm run lint
```

### Testing Bambu Studio CLI

```bash
# Test CLI availability
which bambu-studio-cli
bambu-studio-cli --help

# The CLI is available system-wide in the container
```

## Ports

- **8000**: Backend API (FastAPI)
- **3000**: Frontend development server (Vite)

These ports are automatically forwarded when using VS Code Dev Containers.

## Volume Mounts

- The entire project directory is mounted to `/workspace` in the container
- Node modules are handled with named volumes to avoid permission issues
- Changes made in the container are immediately reflected on the host

## Environment Variables

- `PYTHONPATH=/workspace/backend` - Enables Python imports from backend directory
- `NODE_ENV=development` - Sets Node.js environment for development

## Creating Tests

The dev container is ready for test development. When you create tests:

### Backend Tests

Create tests in the `backend/` directory following pytest conventions:

```python
# backend/test_example.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_example():
    response = client.get("/")
    assert response.status_code == 200
```

Run with: `pytest backend/`

### Frontend Tests

The container includes TypeScript support for frontend testing. You can add testing libraries as needed:

```bash
# Add testing dependencies
npm install --save-dev @testing-library/react @testing-library/jest-dom vitest
```

## Troubleshooting

### Quick Diagnosis

Run the troubleshooting script inside the dev container:

```bash
/workspace/.devcontainer/troubleshoot.sh
```

This script will check:

- Architecture compatibility
- Docker environment
- Python and Node.js availability
- Bambu Studio CLI installation
- Workspace structure and permissions
- Network connectivity

### Architecture Issues (Apple Silicon Macs)

If you encounter errors like "exit code 126" during Bambu Studio CLI installation:

1. **Verify Docker Desktop Settings**: Ensure "Use Rosetta for x86_64/amd64 emulation on Apple Silicon" is enabled in Docker Desktop settings
2. **Force Platform**: The devcontainer is configured to force `linux/amd64` platform, but you can verify with:
   ```bash
   docker compose config
   ```
3. **Manual Platform Override**: If needed, you can manually specify the platform:
   ```bash
   docker compose build --platform linux/amd64
   ```

### Permission Issues

If you encounter permission issues with npm or file access, ensure the container is running with appropriate user permissions.

### Rebuilding the Container

If you need to rebuild the container with changes:

```bash
cd .devcontainer
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Bambu Studio CLI Issues

If the CLI installation fails or shows warnings:

1. **Check Architecture**: Run `uname -m` inside the container - it should show `x86_64`
2. **Test CLI Availability**:
   ```bash
   which bambu-studio-cli
   bambu-studio-cli --help
   ```
3. **AppImage Extraction Warnings**: It's normal for AppImage extraction to fail in containers, but the CLI wrapper should still work
