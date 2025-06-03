# LANbu Handy

A self-hosted Progressive Web Application (PWA) that enables users to slice 3D model files and send them to Bambu Lab printers operating in LAN-only mode. LANbu Handy restores core Bambu Handy app functionality for users who prefer or require their printers to operate without cloud connectivity.

## Overview

LANbu Handy provides a streamlined workflow from model URL to print initiation, all within your local network:

1. **Input Model URL**: Provide a URL to your 3D model (`.3mf` or `.stl` files)
2. **Download & Prepare**: The system downloads and validates the model file
3. **Configure Settings**: Map AMS filaments, select build plate, and configure slicing parameters
4. **Local Slicing**: Uses embedded Bambu Studio CLI for reliable, up-to-date slicing
5. **Print Initiation**: Sends the sliced G-code directly to your Bambu Lab printer via LAN

## Key Features

- 🔗 **URL to Print**: Provide a URL to your 3D model and start printing
- ⚙️ **Local Slicing**: Uses embedded Bambu Studio CLI for reliable slicing
- 🏠 **LAN Only**: Operates entirely within your local network (post-download)
- 📱 **Mobile-First**: Responsive PWA interface optimized for mobile devices
- 🎨 **AMS Integration**: Query AMS status and map filaments to model requirements
- 🏗️ **Build Plate Selection**: Choose the correct build plate for optimal adhesion
- 🔧 **Settings Preservation**: Respects embedded `.3mf` settings with selective overrides
- 🚀 **Self-Hosted**: Deploy as a single Docker container in your home lab

## Technology Stack

### Backend

- **Language**: Python 3.9+
- **Framework**: FastAPI
- **Server**: Uvicorn
- **Slicing**: Embedded Bambu Studio CLI
- **Printer Communication**: MQTT and FTP for LAN-only mode

### Frontend (PWA)

- **Framework**: React 19 with TypeScript
- **Build Tool**: Vite
- **Styling**: CSS3 with mobile-first responsive design
- **PWA Features**: Service worker, app manifest, offline capabilities

### Infrastructure

- **Containerization**: Docker with Docker Compose
- **Architecture**: Single all-in-one container
- **Network**: Local area network only (except for model download)

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Bambu Lab printer in LAN-only mode
- Printer access code (found in printer settings)

### Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/depoll/LANbu-Handy.git
   cd LANbu-Handy
   ```

2. **Configure your printer(s)**:

   Create a `.env` file or set environment variables:

   **For a single printer (legacy format)**:

   ```bash
   BAMBU_PRINTER_IP=192.168.1.100
   BAMBU_PRINTER_ACCESS_CODE=12345678
   ```

   **For multiple printers (recommended)**:

   ```bash
   BAMBU_PRINTERS=[{"name":"Living Room X1C","ip":"192.168.1.100","access_code":"12345678"},{"name":"Garage A1 mini","ip":"192.168.1.101","access_code":"87654321"}]
   ```

3. **Start the application**:

   ```bash
   docker compose up -d
   ```

4. **Access the PWA**:
   Open your mobile browser and navigate to `http://[your-server-ip]:8080`

### Usage

1. Enter a URL to your 3D model file (`.3mf` or `.stl`)
2. Select your target printer (if multiple configured)
3. Review and map AMS filaments to model requirements
4. Choose your build plate type
5. Click "Slice" to process the model
6. Click "Print" to start the print job

## Project Structure

```
LANbu-Handy/
├── backend/              # FastAPI backend service
│   ├── app/             # Application code
│   ├── tests/           # Backend tests
│   └── requirements.txt # Python dependencies
├── pwa/                 # React PWA frontend
│   ├── src/            # Source code
│   ├── public/         # Static assets
│   └── package.json    # Node.js dependencies
├── scripts/            # Build and utility scripts
├── .devcontainer/      # Development container config
├── .docs/              # Project documentation
│   ├── prd.md          # Product Requirements Document
│   └── initial-development-plan.md
├── test_files/         # Sample 3D models for testing
├── Dockerfile          # All-in-one container definition
└── docker-compose.yml  # Docker Compose configuration
```

## Documentation

- **[Product Requirements Document](.docs/prd.md)**: Detailed project requirements and specifications
- **[PWA Development Guide](pwa/README.md)**: Frontend development setup and structure
- **[DevContainer Guide](.devcontainer/README.md)**: Development environment setup
- **[Scripts Documentation](scripts/README.md)**: Build scripts and utilities

## Development

For development setup and contribution guidelines, see:

- **DevContainer**: Use the provided `.devcontainer` for a consistent development environment
- **Backend Development**: See backend tests and FastAPI application structure
- **Frontend Development**: See the [PWA README](pwa/README.md) for React development workflow

### Code Formatting and Linting

LANbu Handy uses automated code formatting to maintain consistent code style across the project:

#### Python (Backend)

- **Black**: Code formatter with 88-character line length
- **isort**: Import sorting compatible with Black
- **flake8**: Linting with Black-compatible rules

#### JavaScript/TypeScript (PWA)

- **Prettier**: Code formatter for JS/TS/CSS/HTML/JSON/Markdown
- **ESLint**: Linting for TypeScript and React

#### Setup for Development

**DevContainer Users (Automatic Setup)**:
If you're using the devcontainer (VS Code or GitHub Codespaces), pre-commit hooks are **automatically configured** when the container starts. No manual setup required!

**Local Development Setup**:

1. **Quick setup** (one command):

   ```bash
   # Automated setup script
   ./scripts/setup-dev-environment.sh
   ```

2. **Manual setup**:

   ```bash
   # Install dependencies
   cd backend && pip install -r requirements.txt
   cd pwa && npm install

   # Install pre-commit hooks
   pip install pre-commit
   pre-commit install
   ```

3. **Manual formatting** (if not using pre-commit):

   ```bash
   # Format Python code
   python -m black backend/
   python -m isort --profile black backend/

   # Format PWA code
   cd pwa && npm run format
   ```

4. **Check formatting**:

   ```bash
   # Python
   python -m black --check backend/
   python -m isort --profile black --check-only backend/
   python -m flake8 backend/

   # PWA
   cd pwa && npm run format:check
   cd pwa && npm run lint
   ```

The pre-commit hooks will automatically format your code before each commit, reducing linting errors and maintaining consistent style. All formatting checks are also run in CI.

### Running Tests

```bash
# Backend tests
cd backend && python -m pytest

# Frontend linting
cd pwa && npm run lint

# Full Docker build test
docker compose build
```

## Target Audience

LANbu Handy is designed for Bambu Lab printer owners who:

- Prefer or require running their printers in LAN-only mode for privacy or security
- Are comfortable with self-hosting applications in their home lab
- Want a convenient mobile-first interface for initiating prints
- Desire independence from cloud services for core printing workflows

## Roadmap

This project follows a phased development approach:

- **Phase 0**: ✅ Project foundation and basic structure
- **Phase 1**: 🚧 Core slicing and printing backbone
- **Phase 2**: 📋 Enhanced slicing configuration and AMS integration
- **Phase 3**: 📋 Printer discovery and UX polish
- **Phase 4**: 📋 Testing, documentation, and release preparation

See the [Initial Development Plan](.docs/initial-development-plan.md) for detailed milestones.

## Contributing

Contributions are welcome! Please:

1. Review the [Product Requirements Document](.docs/prd.md)
2. Check existing GitHub Issues for tasks
3. Follow the established code style and testing practices
4. Submit pull requests for review

## License

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) file for details.

## Disclaimer

LANbu Handy is an independent project and is not affiliated with, endorsed by, or sponsored by Bambu Lab. Bambu Lab, Bambu Studio, and related trademarks are the property of their respective owners.
