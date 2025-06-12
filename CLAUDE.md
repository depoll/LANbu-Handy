# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Development Commands

```bash
# Backend (Python/FastAPI)
cd backend && python -m pytest                    # Run backend tests
cd backend && python -m pytest -v                # Verbose backend tests
cd backend && python -m uvicorn app.main:app --reload  # Run backend dev server

# Frontend (React/TypeScript PWA)
cd pwa && npm run dev                              # Run PWA dev server
cd pwa && npm test                                 # Run PWA tests
cd pwa && npm run build                           # Build PWA for production

# Code Quality (run from project root)
./scripts/format-code.sh                          # Format all code (Python + JS/TS)
./scripts/lint.sh                                 # Lint all code
./scripts/test.sh                                 # Run all tests (backend + frontend)

# Docker Development
docker compose -f docker-compose.dev.yml up --build  # Build and run dev container
docker compose up                                     # Run with pre-built image
```

### Setup Commands

```bash
./scripts/setup-dev-environment.sh               # One-command dev setup
pre-commit install                                # Install formatting hooks
```

## Architecture Overview

LANbu Handy is a self-hosted PWA for 3D printing workflow management with Bambu Lab printers in LAN-only mode.

### Core Architecture

- **All-in-one Docker container** serving both backend API and PWA frontend
- **Backend**: Python 3.9+ with FastAPI, serves static PWA files and REST API
- **Frontend**: React 19 + TypeScript PWA with mobile-first responsive design
- **Slicer**: Embedded Bambu Studio CLI for local G-code generation
- **Printer Communication**: MQTT + FTP for LAN-only mode operation

### Key Workflow

1. User provides URL to 3D model (.3mf/.stl)
2. System downloads and validates model
3. User configures AMS filaments and build plate
4. Local slicing via Bambu Studio CLI
5. G-code transfer to printer via FTP and print initiation via MQTT

### Directory Structure

```
backend/app/           # FastAPI application and business logic
pwa/src/              # React PWA frontend
scripts/              # Build, setup, and utility scripts
test_files/           # Sample 3MF models for testing
```

## Code Quality Standards

### Python (Backend)

- **Black** formatter with 88-character line length
- **isort** for import sorting (Black-compatible profile)
- **flake8** for linting with Black-compatible rules
- **pytest** for testing with async support

### TypeScript/React (PWA)

- **Prettier** for code formatting
- **ESLint** for linting TypeScript and React
- **Vitest** for unit testing with jsdom
- **Playwright** for E2E testing

### Automated Formatting

- Pre-commit hooks automatically format code before commits
- All formatting tools configured for consistency between Python and JS/TS
- CI enforces formatting standards

## Testing Strategy

### Backend Testing

```bash
cd backend && python -m pytest tests/            # All backend tests
cd backend && python -m pytest tests/test_integration_* -v  # Integration tests
```

### Frontend Testing

```bash
cd pwa && npm test                               # Unit tests with Vitest
cd pwa && npm run test:coverage                  # Coverage report
npx playwright test                              # E2E tests
```

### Integration Testing

- Backend has comprehensive integration tests using real 3MF files
- Tests cover model parsing, slicing pipeline, and printer communication
- Uses embedded Bambu Studio CLI for end-to-end validation

## Development Environment

### DevContainer (Recommended)

- Pre-configured VS Code devcontainer with all dependencies
- Automatic pre-commit hook setup on container start
- Includes Bambu Studio CLI installation for testing

### Manual Setup

```bash
./scripts/setup-dev-environment.sh    # Installs dependencies and hooks
```

## Printer Configuration

### Environment Variables (Docker)

```bash
BAMBU_PRINTERS='[{"name":"X1C","ip":"192.168.1.100","access_code":"12345678"}]'
```

### Persistent Storage (Recommended)

- Enable volume mount: `- ./config:/app/data` in docker-compose.yml
- Add printers via UI with "Save permanently" option
- Configurations stored in `./config/printers.json`

## Key Files and Services

### Backend Core Services

- `app/main.py` - FastAPI application entry point
- `app/slicer_service.py` - Bambu Studio CLI integration
- `app/printer_service.py` - MQTT/FTP printer communication
- `app/model_service.py` - 3D model download and validation
- `app/job_orchestration.py` - End-to-end workflow coordination

### Frontend Core Components

- `src/components/ModelPreview.tsx` - 3D model visualization with Three.js
- `src/components/PrinterSelector.tsx` - Printer management and selection
- `src/components/FilamentMappingConfig.tsx` - AMS filament configuration
- `src/components/SliceAndPrint.tsx` - Main workflow component

### Configuration

- `pyproject.toml` - Python formatting and linting configuration
- `pwa/vite.config.ts` - Vite build configuration
- `.pre-commit-config.yaml` - Automated formatting hooks

## Development Notes

### Bambu Studio CLI Integration

- CLI installed at `/usr/local/bin/bambu-studio-cli` in container
- Version controlled via `scripts/bambu-studio-version.txt`
- Integration tests validate CLI functionality with real models

### Mobile-First PWA Design

- Responsive design optimized for mobile devices
- Service worker for offline capabilities
- App manifest for "add to home screen" functionality

### Error Handling

- Comprehensive error handling for I/O operations, CLI interactions, and printer communication
- User-friendly error messages displayed in PWA interface
- Detailed logging for debugging

### Security Considerations

- Input validation for all API endpoints
- Secure temporary file handling for model downloads
- Path traversal protection for file operations

### Development Workflow

- Running tests and pre-commits should happen inside the dev container

### Commit Notes

- If precommits are passing in the dev container, commit with noverify from outside of the container
```