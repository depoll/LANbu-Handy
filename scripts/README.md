# Bambu Studio CLI Installation

This directory contains the installation script for adding Bambu Studio CLI to the LANbu Handy Docker image.

## Current Status

The installation infrastructure is complete and working. The Docker build process successfully:

1. ✅ Installs all necessary system dependencies for running AppImages and GUI applications
2. ✅ Downloads and executes the Bambu Studio CLI installation script
3. ✅ Creates executable CLI commands at `/usr/local/bin/bambu-studio-cli` and `/usr/local/bin/bambu-studio`
4. ✅ Makes the CLI available system-wide in the container

## Current Implementation

Currently, a placeholder CLI is installed that:
- Responds to `--help`, `--version`, and `--slice` commands  
- Provides clear feedback about its placeholder status
- Allows the Docker build and application to work while the real CLI URLs are researched

## To Complete the Installation

To replace the placeholder with the actual Bambu Studio CLI:

1. **Research the correct download URLs** for Bambu Studio releases
   - Check the official Bambu Lab GitHub releases
   - Identify the Linux AppImage or .deb package URLs
   - Note the exact naming conventions used

2. **Update the installation script** (`install-bambu-studio-cli.sh`)
   - Replace the placeholder URL patterns with working URLs
   - Test that the download and installation works

3. **Rebuild the Docker image** to pick up the changes

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

You can test the current installation:

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

# Example CLI usage (once real CLI is installed)
result = subprocess.run([
    'bambu-studio-cli', 
    '--slice', 
    'input.stl', 
    '--output', 
    'output.gcode'
], capture_output=True, text=True)
```