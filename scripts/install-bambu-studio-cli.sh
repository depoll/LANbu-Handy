#!/bin/bash
set -e

# Bambu Studio CLI Installation Script
# This script downloads and installs Bambu Studio CLI for use in Docker containers

echo "Installing Bambu Studio CLI..."

# Configuration
BAMBU_VERSION="${BAMBU_VERSION:-v1.8.4}"
INSTALL_DIR="/usr/local/bin"
TEMP_DIR="/tmp/bambu-studio-install"

echo "Bambu Studio version: $BAMBU_VERSION"
echo "Install directory: $INSTALL_DIR"
echo "Temporary directory: $TEMP_DIR"

# Create temporary directory
mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"

# Try multiple possible naming patterns for Bambu Studio releases
POSSIBLE_NAMES=(
    "BambuStudio_ubu64.AppImage"
    "Bambu_Studio_ubuntu-22.04_${BAMBU_VERSION}.AppImage"
    "BambuStudio_Linux_${BAMBU_VERSION}.AppImage"
    "bambu-studio_${BAMBU_VERSION}_linux_x64.AppImage"
)

APPIMAGE_URL=""
DOWNLOAD_SUCCESSFUL=false

# Try each possible filename until we find one that works
for FILENAME in "${POSSIBLE_NAMES[@]}"; do
    APPIMAGE_URL="https://github.com/bambulab/BambuStudio/releases/download/${BAMBU_VERSION}/${FILENAME}"
    echo "Trying download URL: $APPIMAGE_URL"
    
    if curl -L --silent --fail -o "BambuStudio.AppImage" "$APPIMAGE_URL"; then
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
    echo "Installing a placeholder CLI for now..."
    
    # Install placeholder that provides helpful information
    cat > "$INSTALL_DIR/bambu-studio-cli" << 'EOF'
#!/bin/bash
echo "Bambu Studio CLI Installation Failed"
echo "The CLI could not be downloaded from GitHub releases."
echo ""
echo "To fix this:"
echo "1. Check available versions at: https://github.com/bambulab/BambuStudio/releases/"
echo "2. Update the BAMBU_VERSION environment variable in your Docker build"
echo "3. Rebuild the Docker image"
echo ""
echo "For help, use: bambu-studio-cli --help"

if [ "$1" = "--help" ]; then
    echo ""
    echo "Available options:"
    echo "  --help      Show this help message"
    echo "  --version   Show version information"
    echo "Note: Full functionality requires successful CLI installation."
    exit 0
elif [ "$1" = "--version" ]; then
    echo "Bambu Studio CLI placeholder (download failed)"
    exit 1
else
    exit 1
fi
EOF
    chmod +x "$INSTALL_DIR/bambu-studio-cli"
    ln -sf "$INSTALL_DIR/bambu-studio-cli" "$INSTALL_DIR/bambu-studio"
    
    echo "Placeholder CLI installed. The build will continue but CLI functionality will be limited."
    exit 0
fi

echo "Download completed. Making AppImage executable..."
chmod +x "BambuStudio.AppImage"

# Extract the AppImage to access the CLI
echo "Extracting AppImage..."
./BambuStudio.AppImage --appimage-extract > /dev/null 2>&1

# Look for the CLI binary in the extracted content
if [ -f "squashfs-root/usr/bin/bambu-studio" ]; then
    echo "Found CLI binary at: squashfs-root/usr/bin/bambu-studio"
    cp "squashfs-root/usr/bin/bambu-studio" "$INSTALL_DIR/bambu-studio-cli"
    chmod +x "$INSTALL_DIR/bambu-studio-cli"
elif [ -f "squashfs-root/AppRun" ]; then
    echo "Using AppRun as CLI binary"
    cp "squashfs-root/AppRun" "$INSTALL_DIR/bambu-studio-cli"
    chmod +x "$INSTALL_DIR/bambu-studio-cli"
else
    echo "CLI binary not found in expected locations. Creating wrapper..."
    # Create a wrapper script that uses the full AppImage
    cp "BambuStudio.AppImage" "$INSTALL_DIR/BambuStudio.AppImage"
    chmod +x "$INSTALL_DIR/BambuStudio.AppImage"
    
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
fi

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
    bambu-studio-cli --help 2>/dev/null || echo "Note: CLI might require additional setup for full functionality"
else
    echo "Warning: bambu-studio-cli not found in PATH"
fi