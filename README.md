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

1. **Enter Model URL**: Provide a direct URL to your 3D model file (`.3mf` or `.stl` format)
   - Supported sources: GitHub releases, file sharing services, direct HTTP/HTTPS links
   - Model files should be publicly accessible without authentication

2. **Select Printer**: Choose your target printer from the dropdown (if multiple configured)
   - The interface will show printer status and availability
   - Printer must be powered on and connected to your network

3. **Configure AMS Filaments**: Review and map AMS filaments to model requirements
   - The system queries your printer's current AMS status
   - Map each model color/material requirement to available AMS slots
   - Override material types if needed (PLA, PETG, ABS, etc.)

4. **Choose Build Plate**: Select the appropriate build plate for your material
   - Cool Plate: PLA, PETG
   - Engineering Plate: ABS, ASA, PC
   - High Temp Plate: PA, PEI
   - Textured PEI Plate: PETG, TPU

5. **Slice Model**: Click "Slice" to process the model with Bambu Studio CLI
   - Monitor slicing progress in the interface
   - Review estimated print time and material usage
   - Slicing respects embedded `.3mf` settings with selective overrides

6. **Start Print**: Click "Print" to transfer G-code and start the print job
   - G-code is transferred via FTP to your printer
   - Print job starts automatically once transfer completes
   - Monitor initial print status in the interface

## Troubleshooting

### Container and Installation Issues

**Container won't start:**
```bash
# Check container logs
docker compose logs lanbuhandy

# Check if port 8080 is already in use
sudo netstat -tulpn | grep :8080
# or on macOS:
lsof -i :8080

# If port is in use, modify docker-compose.yml to use different port:
# ports:
#   - '8081:8000'  # Change 8080 to 8081
```

**Permission issues with Docker:**
```bash
# Add user to docker group (Linux)
sudo usermod -aG docker $USER
# Log out and back in, or:
newgrp docker

# Or run with sudo
sudo docker compose up -d
```

**Build failures:**
```bash
# Clean build (removes cached layers)
docker compose build --no-cache

# Check disk space
df -h

# Update Docker and Docker Compose to latest versions
```

### Printer Connection Issues

**Printer not detected or "Connection failed":**

1. **Verify LAN-only mode is enabled:**
   - Go to printer Settings → Network → LAN-Only Mode
   - Enable LAN-Only Mode and note the Access Code

2. **Check network connectivity:**
   ```bash
   # Test if printer IP is reachable
   ping 192.168.1.100  # Replace with your printer IP
   
   # Test MQTT port (8883 for secure, 1883 for non-secure)
   telnet 192.168.1.100 8883
   
   # Test FTP port  
   telnet 192.168.1.100 990
   ```

3. **Verify configuration:**
   - Double-check printer IP address in your `.env` file
   - Verify Access Code is exactly as shown on printer screen (8 digits)
   - Ensure no extra spaces or characters in configuration

4. **Multiple printers configuration:**
   ```bash
   # Correct JSON format for multiple printers:
   BAMBU_PRINTERS=[{"name":"Printer 1","ip":"192.168.1.100","access_code":"12345678"},{"name":"Printer 2","ip":"192.168.1.101","access_code":"87654321"}]
   
   # Common mistakes:
   # - Missing quotes around strings
   # - Extra commas at the end
   # - Spaces in JSON keys
   ```

**MQTT connection timeouts:**
- Some routers block MQTT traffic - check firewall settings
- Try power cycling the printer
- Verify printer firmware is up to date

### Model Download and File Issues

**"Failed to download model" errors:**

1. **URL format issues:**
   ```bash
   # ✅ Correct: Direct file URLs
   https://github.com/user/repo/releases/download/v1.0/model.3mf
   https://example.com/files/model.stl
   
   # ❌ Incorrect: Repository or webpage URLs  
   https://github.com/user/repo/blob/main/model.3mf
   https://thingiverse.com/thing/123456
   ```

2. **Authentication required:**
   - Ensure URLs are publicly accessible
   - For GitHub, use "releases" URLs, not repository file URLs
   - Test URL in browser's private/incognito mode

3. **File format issues:**
   ```bash
   # Supported formats:
   .3mf  # Preferred - includes print settings
   .stl  # Supported - requires manual configuration
   
   # Unsupported formats:
   .obj, .ply, .amf, .zip archives
   ```

**Large file downloads:**
- Files over 100MB may timeout - check your network connection
- Consider hosting files on faster CDN if possible

### Slicing Issues

**Bambu Studio CLI errors:**

1. **"Command not found" or CLI missing:**
   ```bash
   # Rebuild container to reinstall CLI
   docker compose down
   docker compose build --no-cache
   docker compose up -d
   ```

2. **Slicing fails with memory errors:**
   - Increase Docker memory allocation to at least 4GB
   - For complex models, allocate 8GB+ RAM to Docker

3. **Invalid model errors:**
   ```bash
   # Common model issues:
   # - Non-manifold geometry
   # - Corrupt STL files  
   # - Models with zero volume
   
   # Try repairing model in:
   # - Meshmixer (free)
   # - Netfabb (Windows built-in)
   # - Online repair services
   ```

**Slicing configuration problems:**
- `.3mf` files contain embedded settings - these are preserved during slicing
- Manual overrides (filament, plate type) take precedence over embedded settings
- Check material compatibility with selected build plate

### PWA and Interface Issues

**Can't access web interface:**

1. **Check container status:**
   ```bash
   docker compose ps
   # Should show lanbuhandy as "Up"
   
   docker compose logs lanbuhandy
   # Look for "Uvicorn running on http://0.0.0.0:8000"
   ```

2. **Network access:**
   ```bash
   # Try different URLs:
   http://localhost:8080        # If running on same machine
   http://192.168.1.50:8080    # Replace with your server IP
   http://<hostname>:8080       # Using hostname
   ```

3. **Firewall issues:**
   ```bash
   # Linux: Allow port 8080
   sudo ufw allow 8080
   
   # Check if firewall is blocking:
   sudo iptables -L | grep 8080
   ```

**Mobile browser compatibility:**
- Use modern browsers: Chrome 80+, Safari 13+, Firefox 75+
- Enable JavaScript and cookies
- Try refreshing with Ctrl+F5 (or Cmd+Shift+R on Mac)

**PWA installation issues:**
- Look for "Add to Home Screen" in browser menu
- Ensure HTTPS is not required (should work on local network with HTTP)
- Clear browser cache if PWA features aren't working

### Performance Issues

**Slow slicing:**
- Increase Docker CPU allocation
- Close other resource-intensive applications
- Consider using simpler print profiles for testing

**Interface lag:**
- Clear browser cache and cookies
- Disable browser extensions
- Check network latency to server

**High memory usage:**
- Restart container periodically: `docker compose restart lanbuhandy`
- Monitor with: `docker stats lanbuhandy`

### Getting Help

**Enable debug logging:**
```bash
# Add to your .env file or docker-compose.yml:
LOG_LEVEL=debug

# Restart container
docker compose restart lanbuhandy

# View detailed logs
docker compose logs -f lanbuhandy
```

**Collect diagnostic information:**
```bash
# System info
docker --version
docker compose version
uname -a

# Container status
docker compose ps
docker compose logs --tail=50 lanbuhandy

# Network connectivity
ping <printer_ip>
traceroute <printer_ip>
```

**Common solutions checklist:**
- [ ] Printer is powered on and connected to network
- [ ] LAN-only mode is enabled with correct access code
- [ ] Docker container is running (`docker compose ps`)
- [ ] No firewall blocking ports 8080, 8883, 990
- [ ] Model URL is direct link to `.3mf` or `.stl` file
- [ ] Sufficient disk space and memory available
- [ ] Using supported browser with JavaScript enabled

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
- **[Developer Notes](DEVELOPER_NOTES.md)**: Architecture overview, development setup, and code organization
- **[PWA Development Guide](pwa/README.md)**: Frontend development setup and structure
- **[DevContainer Guide](.devcontainer/README.md)**: Development environment setup
- **[Scripts Documentation](scripts/README.md)**: Build scripts and utilities

## Development

For comprehensive development information including architecture, setup instructions, and code organization, see the **[Developer Notes](DEVELOPER_NOTES.md)**.

**Quick Links:**
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
