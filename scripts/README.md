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
- Downloads the actual Bambu Studio AppImage from GitHub releases (https://github.com/bambulab/BambuStudio/releases)
- Supports configurable version selection via `BAMBU_VERSION` environment variable (defaults to v1.8.4)
- Extracts the CLI binary from the AppImage and installs it properly
- Provides error handling and fallback mechanisms
- Creates both `bambu-studio-cli` and `bambu-studio` commands

## Installation Details

### Version Configuration

You can specify a different Bambu Studio version by setting the `BAMBU_VERSION` environment variable:

```bash
# In Dockerfile or build environment
ENV BAMBU_VERSION=v1.8.4

# Or during docker build
docker build --build-arg BAMBU_VERSION=v1.8.2 -t lanbu-handy .
```

### Download Process

The script:
1. Downloads the AppImage from: `https://github.com/bambulab/BambuStudio/releases/download/{VERSION}/BambuStudio_ubu64.AppImage`
2. Makes it executable and extracts the contents
3. Locates the CLI binary within the extracted files
4. Installs it to `/usr/local/bin/` with proper permissions

## Dependencies Installed

The Dockerfile installs these packages to support Bambu Studio CLI execution:

```bash
curl wget binutils fuse libfuse2 libxcb1 libxcb-icccm4 libxcb-image0 
libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-render0 
libxcb-shape0 libxcb-sync1 libxcb-util1 libxcb-xfixes0 libxcb-xinerama0 
libxcb-xkb1 libxkbcommon-x11-0 libxkbcommon0
```

These support:
- AppImage execution (`fuse`, `libfuse2`)
- GUI library dependencies (`libxcb*`, `libxkbcommon*`)
- Download utilities (`curl`, `wget`)
- Archive extraction (`binutils`)

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
2. Update the `BAMBU_VERSION` environment variable to a valid release tag
3. Rebuild the Docker image