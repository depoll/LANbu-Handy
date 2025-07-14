# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the LANbu Handy codebase.

## Quick Reference

### Most Used Commands

```bash
# Development
./scripts/start-dev.sh                          # Start dev servers (backend + frontend)
./scripts/stop-dev.sh                           # Stop dev servers
./scripts/test.sh                               # Run all tests

# Code Quality
./scripts/format-code.sh                        # Auto-format all code
./scripts/lint.sh                               # Check code quality
pre-commit run --all-files                      # Run all pre-commit checks

# Setup
./scripts/setup-dev-environment.sh              # Complete dev environment setup
```

## Essential Commands

### Development Commands

```bash
# Backend (Python/FastAPI)
cd backend && python -m pytest                    # Run backend tests
cd backend && python -m pytest -v                # Verbose backend tests
cd backend && python -m pytest tests/test_integration_* -v  # Integration tests only
cd backend && python -m pytest -m "not slow"     # Skip slow tests
cd backend && python -m uvicorn app.main:app --reload  # Run backend dev server

# Frontend (React/TypeScript PWA)
cd pwa && npm run dev                            # Run PWA dev server (Vite)
cd pwa && npm test                               # Run Vitest unit tests
cd pwa && npm run test:ui                        # Run tests with UI
cd pwa && npm run test:coverage                  # Generate coverage report
cd pwa && npm run build                          # Build PWA for production

# Code Quality (run from project root)
./scripts/format-code.sh                         # Format all code (Black + Prettier)
./scripts/lint.sh                                # Lint all code (flake8 + ESLint)
./scripts/autofix-lint.sh                        # Auto-fix linting issues

# Docker Development
docker compose -f docker-compose.dev.yml up --build  # Build and run dev container
docker compose up                                     # Run with pre-built image
docker compose down                                   # Stop containers
```

### Setup Commands

```bash
./scripts/setup-dev-environment.sh               # One-command dev setup
pre-commit install                               # Install git hooks
./scripts/dev-container-startup.sh               # DevContainer initialization

## Architecture Overview

LANbu Handy is a self-hosted PWA for 3D printing workflow management with Bambu Lab printers in LAN-only mode.

### Core Architecture

- **All-in-one Docker container** serving both backend API and PWA frontend
- **Backend**: Python 3.9+ with FastAPI, serves static PWA files and REST API
- **Frontend**: React 19 + TypeScript PWA with mobile-first responsive design
- **Slicer**: Embedded Bambu Studio CLI for local G-code generation
- **Printer Communication**: MQTT + FTP for LAN-only mode operation
- **Status Monitoring**: Parallel MQTT connections with connection pooling for efficient multi-printer monitoring

### Key Workflow

1. User provides URL to 3D model (.3mf/.stl)
2. System downloads and validates model
3. User configures AMS filaments and build plate
4. Local slicing via Bambu Studio CLI
5. G-code transfer to printer via FTP and print initiation via MQTT

### Performance Optimizations

- **MQTT Connection Pool**: Reuses connections for parallel printer status checks
- **Background Status Monitor**: Updates all printer statuses every 5 seconds
- **In-Memory Caching**: Caches printer metadata and status to reduce API calls
- **Async Operations**: All printer communications use async/await patterns

### Directory Structure

```

backend/app/ # FastAPI application and business logic
pwa/src/ # React PWA frontend
scripts/ # Build, setup, and utility scripts
test_files/ # Sample 3MF models for testing

````

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

- `app/main.py` - FastAPI application entry point, serves API and static PWA files
- `app/slicer_service.py` - Bambu Studio CLI integration for G-code generation
- `app/printer_service.py` - MQTT/FTP printer communication with error handling
- `app/model_service.py` - 3D model download, validation, and parsing
- `app/job_orchestration.py` - End-to-end workflow coordination
- `app/printer_status_monitor.py` - Background service for parallel status updates
- `app/mqtt_connection_pool.py` - Connection pooling for efficient MQTT operations
- `app/printer_config.py` - Printer configuration management with persistence
- `app/auth_manager.py` - Manages printer access codes and authentication

### Bambu Studio Resources

- Resources are located at `/opt/bambu-studio-resources` in containers
- In development, a symlink at `./bambu-studio-resources` provides access
- Contains printer configurations, filament profiles, build plate settings, and images
- These resources are automatically copied from the Bambu Studio repository during CLI build
- Version controlled via `scripts/bambu-studio-version.txt`

### Frontend Core Components

- `src/components/ModelPreview.tsx` - 3D model visualization with Three.js
- `src/components/PrinterSelector.tsx` - Printer management with background status
- `src/components/FilamentMappingConfig.tsx` - AMS filament configuration UI
- `src/components/SliceAndPrint.tsx` - Main workflow orchestration component
- `src/contexts/ThemeContext.tsx` - Theme management (light/dark/system)
- `src/hooks/useBackgroundPrinterStatus.ts` - Hook for efficient status polling
- `src/hooks/useCurrentPrinter.ts` - Current printer state management
- `src/hooks/useProactiveAMSStatus.ts` - Proactive AMS status updates

### Configuration

- `pyproject.toml` - Python project config (Black, isort, pytest settings)
- `pwa/vite.config.ts` - Vite build configuration with PWA plugin
- `pwa/vitest.config.ts` - Vitest configuration for unit testing
- `.pre-commit-config.yaml` - Automated formatting hooks
- `backend/data/printers.json` - Persistent printer configuration storage

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

## Important Development Guidelines

### Critical Rules

1. **Always use provided scripts** - Never start servers manually unless absolutely necessary
   - Use `scripts/start-dev.sh` and `scripts/stop-dev.sh` for development servers
   - These scripts handle proper log management and process cleanup

2. **Code quality checks are mandatory** - Never commit with `--no-verify`
   - Fix all pre-commit failures before committing
   - Run tests (backend AND frontend) before marking work as complete
   - Ensure builds succeed without errors

3. **Theme support is required** - All UI changes must support light/dark themes
   - Test components in both theme modes
   - Use CSS variables from the theme system

4. **Line length limits** - Python code must have lines < 88 characters

5. **Parallel execution** - Run independent tasks in parallel when safe

### API and Integration References

- **Bambu Studio CLI**: Use `bambu-studio-cli --help` for canonical documentation
  - Additional examples: https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage
  - Always prefer built-in CLI features over custom implementations

- **MQTT API**: https://github.com/Doridian/OpenBambuAPI/blob/main/mqtt.md
  - Contains printer communication protocol details
  - Status reporting format and command structure

- **Printer Model Mappings**: https://wiki.bambulab.com/en/general/find-sn
  - Maps serial numbers to printer models

### Development Workflow

1. **Git workflow** - Keep commits linear and stay in sync
   - Check remote branch status before committing
   - Build up changesets until ready for clean commit

2. **Issue tracking** - Keep GitHub issues updated
   - Add progress notes when working on PRs
   - Include enough context to resume work later

3. **Testing approach** - Use appropriate tools
   - Prefer Playwright MCP for browser testing (use Chromium)
   - Backend: pytest with async support
   - Frontend: Vitest for unit tests

### System-Specific Notes

- Development servers run on port 3000
- Logs should be redirected to readable location (e.g., /tmp)
- Printer configuration stored at `backend/data/printers.json`
- PWA manifest and service worker handle offline functionality

## Troubleshooting

### Common Issues

1. **MQTT Connection Timeouts**
   - Check printer IP and access code
   - Verify printer is in LAN-only mode
   - Connection pool may need restart: restart backend service

2. **Slicing Failures**
   - Verify Bambu Studio CLI is installed: `which bambu-studio-cli`
   - Check resources directory exists: `ls -la /opt/bambu-studio-resources`
   - Review slice logs for detailed errors

3. **Theme Issues**
   - Clear browser cache and localStorage
   - Check theme class on document root element
   - Verify CSS variables are properly loaded

4. **Pre-commit Hook Failures**
   - Run `./scripts/format-code.sh` to auto-fix formatting
   - Check Python line length (< 88 chars)
   - Ensure all imports are properly sorted

5. **Development Server Issues**
   - Always use `scripts/stop-dev.sh` before `scripts/start-dev.sh`
   - Check for orphaned processes: `ps aux | grep -E "uvicorn|vite"`
   - Review logs in `/tmp` for detailed errors

### Debugging Tips

- Enable FastAPI debug mode: `export DEBUG=true`
- Check MQTT logs: `tail -f backend/logs/mqtt.log`
- Monitor printer status: Check `/api/printers/all-statuses` endpoint
- PWA debugging: Use Chrome DevTools Application tab

## Development Debugging Notes

- If you're making a change and getting feedback that nothing has changed, add (and observe) logging to let you know that it's actually running.
````
