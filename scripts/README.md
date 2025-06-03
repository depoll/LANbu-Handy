# Scripts Directory for LANbu Handy

This directory contains various scripts and tools for the LANbu Handy project.

## Development Environment Setup

### Quick Setup (One Command)

For new developers or to reset your environment:

```bash
# Run the complete setup script
./scripts/setup-dev-environment.sh
```

This script automatically:
- Installs the pre-commit framework
- Sets up pre-commit hooks for the repository
- Optionally installs backend and PWA dependencies
- Provides helpful next steps and tips

### DevContainer (Automatic)

If you're using the devcontainer (VS Code or GitHub Codespaces), pre-commit hooks are **automatically configured** when the container starts. No manual setup required!

## Pre-commit Hook Setup

### Modern Pre-commit Framework (Recommended)

LANbu Handy now uses the [pre-commit framework](https://pre-commit.com/) for automated code formatting and linting. This provides consistent formatting across Python, JavaScript/TypeScript, CSS, and other file types.

#### Installation

```bash
# Install pre-commit
pip install pre-commit

# Install the hooks (from repository root)
pre-commit install
```

#### What it does

The modern pre-commit setup automatically:
- **Formats Python code** with Black and isort
- **Formats JavaScript/TypeScript/CSS/HTML/JSON/Markdown** with Prettier  
- **Runs linting** with flake8 (Python) and ESLint (JS/TS)
- **Performs general file checks** (trailing whitespace, file endings, etc.)
- **Optional**: Lints Dockerfiles with hadolint

#### Usage

Once installed, hooks run automatically before each commit:

```bash
# Normal commit - hooks run automatically
git commit -m "Your changes"

# Skip hooks if needed (not recommended)
git commit --no-verify -m "Emergency fix"

# Run hooks manually on all files
pre-commit run --all-files
```

### Legacy Pre-commit Hook (Deprecated)

The original bash-based pre-commit hook (`scripts/pre-commit-hook.sh`) is still available for reference but is deprecated in favor of the pre-commit framework.

#### What it does

The legacy pre-commit hook automatically runs `flake8` linting on Python code before each commit. If any linting errors are found, the commit is blocked until the issues are fixed.

#### Installation

The hook can be manually installed in `.git/hooks/pre-commit`:

```bash
# Copy the hook script to the git hooks directory
cp scripts/pre-commit-hook.sh .git/hooks/pre-commit

# Make it executable
chmod +x .git/hooks/pre-commit
```

#### Features

- ✅ **Automatic linting**: Runs flake8 on Python files before each commit
- ✅ **Smart detection**: Only runs when Python files are staged for commit
- ✅ **Comprehensive checks**: Validates flake8 availability and provides helpful error messages
- ✅ **Bypass option**: Can be temporarily bypassed with `git commit --no-verify`
- ✅ **Colorized output**: Clear, colorized feedback for better user experience

### Usage

The hook runs automatically before each commit. No manual action required.

#### Successful commit (clean code)
```
🔍 Running pre-commit linting checks...
📁 Checking Python files in: backend/
📝 Staged Python files:
  - backend/app/main.py
🔍 Running: python -m flake8 backend/
✅ All linting checks passed!
🚀 Proceeding with commit...
```

#### Blocked commit (linting errors)
```
🔍 Running pre-commit linting checks...
📁 Checking Python files in: backend/
📝 Staged Python files:
  - backend/app/main.py
🔍 Running: python -m flake8 backend/
❌ Linting errors found:

backend/app/main.py:10:80: E501 line too long (85 > 79 characters)
backend/app/main.py:15:1: W293 blank line contains whitespace

💡 Please fix the above linting errors before committing.
💡 You can run 'python -m flake8 backend/' to see all issues.
💡 To bypass this hook temporarily, use: git commit --no-verify
```

#### Bypassing the hook (when needed)
```bash
# Skip the pre-commit hook for this commit only
git commit --no-verify -m "Emergency fix - will clean up linting later"
```

---

# Bambu Studio CLI Installation

This directory contains the installation script for adding Bambu Studio CLI to the LANbu Handy Docker image.

## Current Status

The installation infrastructure is complete and working. The Docker build process successfully:

1. ✅ Installs all necessary system dependencies for running AppImages and GUI applications
2. ✅ Downloads and executes the Bambu Studio CLI installation script
3. ✅ Downloads the actual Bambu Studio AppImage from GitHub releases
4. ✅ Extracts and installs the CLI binary at `/usr/local/bin/bambu-studio-cli` and `/usr/local/bin/bambu-studio`
5. ✅ Makes the CLI available system-wide in the container

## Current Implementation

The installation script now:
- **Installs minimal system dependencies by default** for faster CI builds (9 packages vs 90+ in full mode)
- Downloads the actual Bambu Studio AppImage from GitHub releases (https://github.com/bambulab/BambuStudio/releases)
- **Defaults to the latest version** automatically by fetching from GitHub API
- Uses a version configuration file (`bambu-studio-version.txt`) for version tracking
- Supports configurable version selection via `BAMBU_VERSION` environment variable
- Extracts the CLI binary from the AppImage and installs it properly
- Provides error handling and fallback mechanisms
- Creates both `bambu-studio-cli` and `bambu-studio` commands
- **Provides `--skip-deps` flag** to skip system dependencies if already installed
- **Provides `--minimal` flag** (default) for minimal dependencies
- **Provides `--full-deps` flag** for complete GUI support when debugging

## Version Management

The project uses a version tracking approach for maintainability:

### Version Configuration File

The version is controlled by `scripts/bambu-studio-version.txt`:
- Contains either "latest" for automatic latest version detection
- Or a specific version tag like "v1.8.4"
- When updated, triggers new builds and releases

### Version Resolution Priority

1. **Environment variable**: `BAMBU_VERSION` (if set)
2. **Version file**: Content of `scripts/bambu-studio-version.txt`
3. **Default fallback**: "latest"

### Latest Version Detection

When version is set to "latest":
- Script attempts to fetch the latest release from GitHub API
- Falls back to a known stable version if API is unavailable
- Handles network restrictions gracefully

## Script Usage

### Basic Installation (All-in-One)

```bash
# Install both dependencies and CLI
./scripts/install-bambu-studio-cli.sh

# Show help
./scripts/install-bambu-studio-cli.sh --help
```

### Advanced Usage

```bash
# Skip system dependencies if already installed
./scripts/install-bambu-studio-cli.sh --skip-deps

# Use specific version
BAMBU_VERSION=v1.8.4 ./scripts/install-bambu-studio-cli.sh
```

The script is designed to work in multiple environments:
- **Docker containers** (CI, production, development)
- **CI environments** (GitHub Actions)
- **Local development setups**
- **Development containers** (VS Code dev containers)

## Dependencies Installed

The script now supports two dependency modes:

### Minimal Mode (Default)
For faster CI builds and CLI-only operation (~9 packages):
```bash
wget curl ca-certificates fuse libfuse2 binutils locales libssl3 file
```

### Full Mode (--full-deps flag)
The script installs a comprehensive list of dependencies based on the official Bambu Studio Dockerfile (~90 packages):

### Build and Development Tools
```bash
autoconf build-essential cmake curl xvfb extra-cmake-modules file git
```

### Graphics and GUI Libraries  
```bash
libcairo2-dev libglew-dev libglu1-mesa-dev libgtk-3-dev libosmesa6-dev
libwayland-dev libxkbcommon-dev libwebkit2gtk-4.1-dev
```

### Media and Streaming
```bash
gstreamer1.0-plugins-bad gstreamer1.0-libav libgstreamer1.0-dev
libgstreamer-plugins-base1.0-dev libgstreamer-plugins-good1.0-dev
```

### Security and Networking
```bash
libcurl4-openssl-dev libssl3 libssl-dev libsecret-1-dev libsoup2.4-dev
ca-certificates gnupg
```

### X11 and Display Support
```bash
libxcb1 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0
libxcb-render-util0 libxcb-render0 libxcb-shape0 libxcb-sync1
libxcb-util1 libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1
libxkbcommon-x11-0 libxkbcommon0
```

### AppImage Support
```bash
binutils fuse libfuse2
```

### Runtime Libraries
```bash
libegl1 libegl-mesa0 libgl1-mesa-dri libopengl0 libgstreamer1.0-0
libgstreamer-plugins-base1.0-0 libsoup-2.4-1 libgtk-3-0t64
libglib2.0-0t64 libdbus-1-3 libfontconfig1 libfreetype6
```

The minimal mode ensures the Bambu Studio CLI works for slicing operations in headless environments. The full mode provides complete GUI library support for debugging.

## Installation Details

### Version Configuration

You can specify a different Bambu Studio version in several ways:

#### 1. Update Version File (Recommended)
Edit `scripts/bambu-studio-version.txt`:
```bash
# For latest version
echo "latest" > scripts/bambu-studio-version.txt

# For specific version  
echo "v1.8.4" > scripts/bambu-studio-version.txt
```

#### 2. Environment Variable
```bash
# In Dockerfile or build environment
ENV BAMBU_VERSION=v1.8.4

# Or during docker build
docker build --build-arg BAMBU_VERSION=v1.8.2 -t lanbu-handy .
```

#### 3. Build-time Override
```bash
# Override both file and default
docker build --build-arg BAMBU_VERSION=latest -t lanbu-handy .
```

### Download Process

The script:
1. Downloads the AppImage from: `https://github.com/bambulab/BambuStudio/releases/download/{VERSION}/BambuStudio_ubu64.AppImage`
2. Makes it executable and extracts the contents
3. Locates the CLI binary within the extracted files
4. Installs it to `/usr/local/bin/` with proper permissions

## Testing

You can test the installation:

```bash
# Build the image
docker build -t lanbu-handy .

# Test CLI availability
docker run --rm lanbu-handy bambu-studio-cli --help
docker run --rm lanbu-handy bambu-studio --version

# Check installation location
docker run --rm lanbu-handy which bambu-studio-cli
docker run --rm lanbu-handy ls -la /usr/local/bin/bambu*
```

## Integration with Backend

The backend Python application can call the CLI using subprocess:

```python
import subprocess

# Example CLI usage
result = subprocess.run([
    'bambu-studio-cli', 
    '--slice', 
    'input.stl', 
    '--output', 
    'output.gcode'
], capture_output=True, text=True)
```

## Troubleshooting

If a specific version fails to download:
1. Check available versions at: https://github.com/bambulab/BambuStudio/releases
2. Update `scripts/bambu-studio-version.txt` or the `BAMBU_VERSION` environment variable to a valid release tag
3. Rebuild the Docker image

### When "latest" Version Detection Fails

If automatic latest version detection fails (due to network restrictions):
- The script falls back to a known stable version (v1.8.4)
- Manual version specification still works via the version file or environment variable
- Check the build logs for specific error messages

## Dev Container Testing

### Validation Script

The `test-dev-container.sh` script provides comprehensive validation of the dev container environment:

```bash
# From the repository root
./scripts/test-dev-container.sh
```

This script tests:
- **Python environment**: Verifies Python 3 and backend dependencies (FastAPI, pytest)
- **Node.js environment**: Checks Node.js and npm availability  
- **Bambu Studio CLI**: Tests CLI installation and basic functionality
- **Backend tests**: Runs unit tests and integration tests
- **Workspace configuration**: Validates file permissions and test files

### Integration Testing

The dev container environment supports full end-to-end testing:

```bash
# Run integration tests with real 3MF files
cd backend
python -m pytest tests/test_slicer_service.py::TestEndToEndSlicing -v
```

This runs 7 integration tests that:
1. **Process real 3MF files** from the `test_files/` directory
2. **Generate G-code output** using the actual Bambu Studio CLI
3. **Validate the complete slicing pipeline** end-to-end

### CI Environment

The same CLI installation and testing approach is used in GitHub Actions CI:
- Integration tests run in CI (not skipped)
- CLI works in headless environments with Xvfb
- All test files are properly validated
- Enhanced CI wrapper provides fallback functionality when needed
- **CLI caching**: The workflow caches the CLI binaries based on the version in `bambu-studio-version.txt` to improve build times