#!/bin/bash
set -e

# Bambu Studio CLI Installation Script
# This script downloads and installs Bambu Studio CLI for use in Docker containers

echo "Installing Bambu Studio CLI..."

# Configuration
# Read version from configuration file, fall back to environment variable, then to "latest"
VERSION_FILE="/scripts/bambu-studio-version.txt"
if [ -f "$VERSION_FILE" ]; then
    BAMBU_VERSION="${BAMBU_VERSION:-$(cat "$VERSION_FILE" | tr -d '[:space:]')}"
else
    BAMBU_VERSION="${BAMBU_VERSION:-latest}"
fi
INSTALL_DIR="/usr/local/bin"
TEMP_DIR="/tmp/bambu-studio-install"

echo "Bambu Studio version: $BAMBU_VERSION"
echo "Install directory: $INSTALL_DIR"
echo "Temporary directory: $TEMP_DIR"

# If version is "latest", try to get the latest release version
if [ "$BAMBU_VERSION" = "latest" ]; then
    echo "Attempting to fetch latest release version..."
    
    # Try to get latest release info from GitHub API
    LATEST_VERSION=""
    if command -v curl >/dev/null 2>&1; then
        LATEST_VERSION=$(curl -s --max-time 10 "https://api.github.com/repos/bambulab/BambuStudio/releases/latest" 2>/dev/null | grep '"tag_name"' | cut -d'"' -f4 || echo "")
    fi
    
    if [ -n "$LATEST_VERSION" ]; then
        echo "Found latest version: $LATEST_VERSION"
        BAMBU_VERSION="$LATEST_VERSION"
    else
        echo "Error: Could not fetch latest version from GitHub API"
        echo "This may be due to network restrictions or API rate limits"
        echo "Build failed: Unable to determine latest Bambu Studio version."
        exit 1
    fi
    
    echo "Using version: $BAMBU_VERSION"
fi

# Create temporary directory
mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"

# Try multiple possible naming patterns for Bambu Studio releases
LOWERCASE_VERSION=$(echo "$BAMBU_VERSION" | tr '[:upper:]' '[:lower:]')
POSSIBLE_NAMES=(
    "Bambu_Studio_linux_fedora-${LOWERCASE_VERSION}.AppImage"
    "Bambu_Studio_linux_fedora-${BAMBU_VERSION}.AppImage"
    "BambuStudio_ubu64.AppImage"
    "Bambu_Studio_ubuntu-22.04_${BAMBU_VERSION}.AppImage"
    "Bambu_Studio_ubuntu-22.04_${LOWERCASE_VERSION}.AppImage"
    "BambuStudio_Linux_${BAMBU_VERSION}.AppImage"
    "bambu-studio_${BAMBU_VERSION}_linux_x64.AppImage"
)

APPIMAGE_URL=""
DOWNLOAD_SUCCESSFUL=false

# Try each possible filename until we find one that works
for FILENAME in "${POSSIBLE_NAMES[@]}"; do
    APPIMAGE_URL="https://github.com/bambulab/BambuStudio/releases/download/${BAMBU_VERSION}/${FILENAME}"
    echo "Trying download URL: $APPIMAGE_URL"
    
    if curl -L --insecure --fail --max-time 30 -o "BambuStudio.AppImage" "$APPIMAGE_URL"; then
        echo "Successfully downloaded: $FILENAME"
        DOWNLOAD_SUCCESSFUL=true
        break
    else
        echo "Failed to download: $FILENAME"
    fi
done

if [ "$DOWNLOAD_SUCCESSFUL" = false ]; then
    echo "Error: Could not download Bambu Studio AppImage from any of the tried URLs"
    echo "Attempted URLs:"
    for FILENAME in "${POSSIBLE_NAMES[@]}"; do
        echo "  - https://github.com/bambulab/BambuStudio/releases/download/${BAMBU_VERSION}/${FILENAME}"
    done
    echo ""
    echo "Please check the available releases at:"
    echo "  https://github.com/bambulab/BambuStudio/releases/"
    echo "and update the BAMBU_VERSION environment variable if needed."
    echo ""
    echo "Build failed: Unable to download real Bambu Studio CLI."
    exit 1
fi

echo "Download completed. Making AppImage executable..."
chmod +x "BambuStudio.AppImage"

# Extract the AppImage to access the CLI
echo "Extracting AppImage..."
./BambuStudio.AppImage --appimage-extract > /dev/null 2>&1

# For better reliability in CI environments, always use the full AppImage approach
echo "Installing AppImage and creating CLI wrapper..."

# Copy the AppImage to the install directory
cp "BambuStudio.AppImage" "$INSTALL_DIR/BambuStudio.AppImage"
chmod +x "$INSTALL_DIR/BambuStudio.AppImage"

# Create a wrapper script that uses the full AppImage
cat > "$INSTALL_DIR/bambu-studio-cli" << 'EOF'
#!/bin/bash
# Bambu Studio CLI wrapper
# This wrapper runs the Bambu Studio AppImage in CLI mode

APPIMAGE_PATH="/usr/local/bin/BambuStudio.AppImage"

if [ ! -f "$APPIMAGE_PATH" ]; then
    echo "Error: Bambu Studio AppImage not found at $APPIMAGE_PATH"
    exit 1
fi

# Run the AppImage with the provided arguments
# Note: Some operations may require a display, but basic CLI functions should work
exec "$APPIMAGE_PATH" "$@"
EOF
chmod +x "$INSTALL_DIR/bambu-studio-cli"

# Create symlink for bambu-studio command
ln -sf "$INSTALL_DIR/bambu-studio-cli" "$INSTALL_DIR/bambu-studio"

# Clean up temporary files
cd /
rm -rf "$TEMP_DIR"

echo "Bambu Studio CLI installation completed!"
echo "Available commands:"
echo "  - bambu-studio"
echo "  - bambu-studio-cli"
echo ""
echo "Installation details:"
echo "  Version: $BAMBU_VERSION"
echo "  CLI location: $INSTALL_DIR/bambu-studio-cli"
echo "  Symlink: $INSTALL_DIR/bambu-studio"

# Test the installation
if command -v bambu-studio-cli >/dev/null 2>&1; then
    echo ""
    echo "Testing installation..."
    echo "CLI help output:"
    timeout 10 bambu-studio-cli --help 2>/dev/null || {
        echo "Note: CLI might require additional setup for full functionality"
        echo "Installation completed but CLI help test failed - this is expected in headless environments"
    }
else
    echo "Warning: bambu-studio-cli not found in PATH"
fi