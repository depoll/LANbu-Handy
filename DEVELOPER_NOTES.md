# LANbu Handy - Developer Documentation

This document provides developer-focused information for understanding, maintaining, and contributing to the LANbu Handy codebase.

## System Architecture Overview

LANbu Handy is designed as a self-contained Progressive Web Application (PWA) that orchestrates 3D model slicing and printing workflows for Bambu Lab printers in LAN-only mode.

### High-Level Architecture

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│   React PWA     │    │    FastAPI Backend   │    │  Bambu Studio   │
│   (Frontend)    │◄──►│    (Orchestrator)    │◄──►│      CLI        │
│                 │    │                      │    │   (Embedded)    │
└─────────────────┘    └──────────────────────┘    └─────────────────┘
                                  │
                                  ▼
                        ┌──────────────────────┐
                        │   Bambu Printer      │
                        │   (LAN Mode)         │
                        │   MQTT + FTP         │
                        └──────────────────────┘
```

### Core Components

#### Backend Services (`backend/app/`)

- **`main.py`**: FastAPI application entry point, API routes, and PWA static file serving
- **`model_service.py`**: Handles model download, validation, and temporary file management
- **`slicer_service.py`**: Manages Bambu Studio CLI interaction and slicing operations
- **`printer_service.py`**: Implements MQTT and FTP communication with Bambu printers
- **`filament_matching_service.py`**: Logic for matching model requirements with AMS filaments
- **`job_orchestration.py`**: Coordinates the full workflow from URL to print start
- **`config.py`**: Configuration management and validation
- **`utils.py`**: Shared utilities and error handling functions

#### PWA Frontend (`pwa/src/`)

- **`App.tsx`**: Main application component and routing
- **`components/`**: Reusable React components for the UI
- **`hooks/`**: Custom React hooks for API integration and state management
- **`types/`**: TypeScript type definitions
- **`validation.ts`**: Input validation utilities

### Communication Patterns

1. **PWA ↔ Backend**: RESTful API over HTTP/HTTPS
2. **Backend ↔ CLI**: Subprocess execution with stdin/stdout communication  
3. **Backend ↔ Printer**: MQTT for commands/status, FTP for file transfer
4. **Backend ↔ External**: HTTP for model file downloads

## Development Environment Setup

### Option 1: DevContainer (Recommended)

The project includes a complete development container setup that provides all dependencies and tools pre-configured.

**VS Code Users:**
1. Open the project in VS Code
2. Install the "Remote - Containers" extension
3. Click "Reopen in Container" when prompted
4. The container will build and configure automatically

**GitHub Codespaces:**
1. Open the repository in GitHub Codespaces
2. The environment will be ready after initialization

**Benefits:**
- Pre-commit hooks automatically configured
- All dependencies installed
- Consistent development environment
- No local setup required

### Option 2: Local Development Setup

**Prerequisites:**
- Python 3.9+ 
- Node.js 18+
- Docker and Docker Compose

**Quick Setup:**
```bash
# Clone the repository
git clone https://github.com/depoll/LANbu-Handy.git
cd LANbu-Handy

# Automated setup (recommended)
./scripts/setup-dev-environment.sh
```

**Manual Setup:**
```bash
# Backend dependencies
cd backend && pip install -r requirements.txt

# Frontend dependencies  
cd pwa && npm install

# Pre-commit hooks (optional but recommended)
pip install pre-commit
pre-commit install
```

### Environment Configuration

Create a `.env` file for local development:

```bash
# Single printer (legacy format)
BAMBU_PRINTER_IP=192.168.1.100
BAMBU_PRINTER_ACCESS_CODE=12345678

# Multiple printers (recommended)
BAMBU_PRINTERS=[{"name":"Living Room X1C","ip":"192.168.1.100","access_code":"12345678"}]
```

## Backend Code Architecture

### FastAPI Application Structure

The backend follows a service-oriented architecture with clear separation of concerns:

```python
# main.py - Application entry point
app = FastAPI(title="LANbu Handy Backend")

# Route organization
@app.post("/api/submit-model-url")  # Model submission
@app.post("/api/slice")             # Basic slicing  
@app.post("/api/configured-slice")  # Advanced slicing
@app.post("/api/start-print")       # Print initiation
@app.get("/api/printer/ams-status") # Printer queries
```

### Service Layer Pattern

Each service module encapsulates specific domain logic:

```python
# Example: slicer_service.py
class BambuStudioCLI:
    def __init__(self, cli_path: str = "/opt/bambu-studio/bambu-studio-cli"):
        self.cli_path = cli_path
    
    async def slice_model(self, model_path: str, options: SlicingOptions) -> str:
        # Subprocess management, error handling, output parsing
        pass

    def _build_cli_command(self, model_path: str, options: SlicingOptions) -> List[str]:
        # Command construction with proper escaping
        pass
```

### Key Backend Patterns

1. **Async/Await**: All I/O operations use async patterns for non-blocking execution
2. **Pydantic Models**: Request/response validation and serialization
3. **Error Handling**: Centralized error handling with user-friendly messages
4. **Dependency Injection**: Services are injected into route handlers
5. **Configuration Management**: Environment-based configuration with validation

### Testing Approach

- **Unit Tests**: Individual service method testing with mocks
- **Integration Tests**: End-to-end workflow testing 
- **Edge Case Tests**: Error conditions and input validation
- **Real CLI Tests**: Actual Bambu Studio CLI interaction (when available)

```bash
# Run backend tests
cd backend && python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=html
```

## PWA Code Architecture

### React 19 + TypeScript Structure

The PWA uses modern React patterns with TypeScript for type safety:

```typescript
// Component structure
interface Props {
  onModelSubmit: (url: string) => void;
  loading: boolean;
}

const ModelSubmissionForm: React.FC<Props> = ({ onModelSubmit, loading }) => {
  // Component logic with hooks
};
```

### Custom Hooks Pattern

API interactions are encapsulated in custom hooks:

```typescript
// hooks/useModelSubmission.ts
export const useModelSubmission = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const submitModel = async (url: string) => {
    // API call logic with error handling
  };
  
  return { submitModel, loading, error };
};
```

### State Management

- **Local State**: React useState for component-level state
- **API State**: Custom hooks with fetch-based API calls
- **Global State**: Context API for shared application state
- **Persistence**: LocalStorage for user preferences

### PWA Features

- **Service Worker**: Configured via Vite PWA plugin
- **Manifest**: App installation and offline capabilities
- **Responsive Design**: Mobile-first with CSS Grid/Flexbox
- **TypeScript**: Full type safety across the application

## Code Style and Quality

### Python (Backend)

**Formatting Tools:**
- **Black**: Code formatter with 88-character line length
- **isort**: Import sorting compatible with Black  
- **flake8**: Linting with Black-compatible rules

**Configuration:**
```ini
# .flake8
[flake8]
max-line-length = 88
extend-ignore = E203, W503
```

**Running Linters:**
```bash
cd backend
python -m black app/ tests/
python -m isort --profile black app/ tests/
python -m flake8 app/ tests/
```

### TypeScript/React (PWA)

**Formatting Tools:**
- **Prettier**: Code formatter for TS/JS/CSS/HTML/JSON
- **ESLint**: TypeScript and React linting

**Running Linters:**
```bash
cd pwa
npm run format      # Format code
npm run format:check # Check formatting
npm run lint        # Run ESLint
```

### Pre-commit Hooks

Automatic code formatting on commit (configured in DevContainer):

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 25.1.0
    hooks:
      - id: black
        language_version: python3
        
  - repo: https://github.com/pycqa/isort  
    rev: 5.14.0
    hooks:
      - id: isort
        args: ["--profile", "black"]
```

## Docker Build and Deployment

### Multi-Stage Build Process

The Dockerfile uses a multi-stage build for optimal image size and security:

```dockerfile
# Stage 1: PWA Build
FROM node:18-slim AS pwa-builder
WORKDIR /app/pwa
COPY pwa/package*.json ./
RUN npm ci --no-audit --no-fund
COPY pwa/ ./
RUN npm run build

# Stage 2: Python Runtime  
FROM python:3.12-slim
WORKDIR /app

# Install Bambu Studio CLI
COPY scripts/install-bambu-studio-cli.sh /tmp/
RUN chmod +x /tmp/install-bambu-studio-cli.sh && \
    /tmp/install-bambu-studio-cli.sh

# Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Application code
COPY backend/ ./
COPY --from=pwa-builder /app/pwa/dist ./static_pwa

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Building and Testing Locally

```bash
# Build the complete application
docker compose build

# Run locally for testing
docker compose up -d

# View logs
docker compose logs -f

# Access application
open http://localhost:8080
```

### Updating Bambu Studio CLI

The embedded Bambu Studio CLI version is managed through:

1. **Version File**: `scripts/bambu-studio-version.txt` specifies the target version
2. **Install Script**: `scripts/install-bambu-studio-cli.sh` handles download and setup
3. **Docker Build**: CLI is installed during the Docker build process

**To update the CLI version:**
```bash
# Edit the version file
echo "01.10.01.05" > scripts/bambu-studio-version.txt

# Rebuild the Docker image
docker compose build --no-cache

# Test the new version
docker compose up -d
```

### Production Deployment Considerations

- **Platform Compatibility**: The Docker image is built for `linux/amd64` to ensure Bambu Studio CLI compatibility
- **Volume Mounts**: Consider mounting `/tmp` for temporary files in production
- **Environment Variables**: Use Docker secrets or environment files for sensitive configuration
- **Resource Limits**: Set appropriate memory limits for the container
- **Health Checks**: Implement health check endpoints for monitoring

### Docker Compose Configuration

```yaml
# docker-compose.yml
services:
  lanbu-handy:
    build: .
    platform: linux/amd64  # Required for Bambu Studio CLI
    ports:
      - "8080:8000"
    environment:
      - BAMBU_PRINTER_IP=${BAMBU_PRINTER_IP}
      - BAMBU_PRINTER_ACCESS_CODE=${BAMBU_PRINTER_ACCESS_CODE}
    tmpfs:
      - /tmp:noexec,nosuid,size=1g  # Temporary file storage
```

## Contributing Guidelines

### Code Organization Principles

1. **Single Responsibility**: Each module/component has a clear, focused purpose
2. **Dependency Injection**: Services are injected rather than imported directly
3. **Error Boundaries**: Proper error handling at appropriate levels
4. **Type Safety**: Full TypeScript coverage in PWA, Pydantic models in backend
5. **Testing**: New features must include appropriate tests

### Development Workflow

1. **Branch Naming**: Use descriptive names (e.g., `feature/ams-integration`, `fix/slicing-error`)
2. **Commits**: Write clear, descriptive commit messages
3. **Pull Requests**: Include tests and documentation updates
4. **Code Review**: All changes require review before merging

### Testing Requirements

- **Backend**: Unit tests for all service methods
- **Integration**: End-to-end workflow tests
- **PWA**: Component tests for complex UI logic
- **Manual Testing**: Real hardware testing when possible

This documentation should be updated as the codebase evolves to maintain accuracy and usefulness for future developers.