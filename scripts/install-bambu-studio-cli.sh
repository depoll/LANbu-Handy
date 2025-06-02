#!/bin/bash
set -e

# Bambu Studio CLI Installation Script
# This script installs system dependencies and downloads/installs Bambu Studio CLI
# for use in Docker containers, CI environments, and development setups

echo "Starting Bambu Studio CLI installation..."

# Function to install system dependencies
install_system_dependencies() {
    echo "Installing system dependencies for Bambu Studio CLI..."
    
    # Check if we're running as root or can use sudo
    if [ "$EUID" -eq 0 ]; then
        APT_CMD="apt-get"
    elif command -v sudo >/dev/null 2>&1; then
        APT_CMD="sudo apt-get"
    else
        echo "Error: This script requires root privileges or sudo access to install system dependencies"
        echo "Please run as root or ensure sudo is available"
        exit 1
    fi
    
    # Update package list
    $APT_CMD update
    
    # Core build dependencies (always required)
    CORE_DEPS=(
        autoconf
        build-essential
        cmake
        curl
        file
        git
        wget
        ca-certificates
        gnupg
    )
    
    # GUI and graphics dependencies
    GUI_DEPS=(
        xvfb
        libcairo2-dev
        libglew-dev
        libglu1-mesa-dev
        libgtk-3-dev
        libosmesa6-dev
        libwayland-dev
        libxkbcommon-dev
        libwebkit2gtk-4.1-dev
        libegl1
        libegl-mesa0
        libgl1-mesa-dri
        libopengl0
        libgtk-3-0
        libglib2.0-0
        libdbus-1-3
        libfontconfig1
        libfreetype6
        libdrm2
        libxss1
        libasound2
        libxrandr2
        libxcomposite1
        libxdamage1
        libxi6
        libxfixes3
        libxcursor1
        libxinerama1
        libwebkit2gtk-4.1-0
    )
    
    # GStreamer dependencies
    GSTREAMER_DEPS=(
        gstreamer1.0-plugins-bad
        gstreamer1.0-libav
        libgstreamer1.0-dev
        libgstreamer-plugins-base1.0-dev
        libgstreamer1.0-0
        libgstreamer-plugins-base1.0-0
    )
    
    # X11 and window system dependencies
    X11_DEPS=(
        libxcb1
        libxcb-icccm4
        libxcb-image0
        libxcb-keysyms1
        libxcb-randr0
        libxcb-render-util0
        libxcb-render0
        libxcb-shape0
        libxcb-sync1
        libxcb-util1
        libxcb-xfixes0
        libxcb-xinerama0
        libxcb-xkb1
        libxkbcommon-x11-0
        libxkbcommon0
    )
    
    # Network and security dependencies
    NETWORK_DEPS=(
        libcurl4-openssl-dev
        libdbus-1-dev
        libsecret-1-dev
        libsoup2.4-dev
        libsoup2.4-1
        libssl3
        libssl-dev
        libudev-dev
        libgssapi-krb5-2
    )
    
    # Additional system dependencies
    SYSTEM_DEPS=(
        locales
        locales-all
        m4
        pkgconf
        sudo
        binutils
        fuse
        libfuse2
    )
    
    # Optional dependencies that might not be available on all systems
    OPTIONAL_DEPS=(
        eglexternalplatform-dev
        extra-cmake-modules
        wayland-protocols
        libgstreamerd-3-dev
    )
    
    # Function to install a list of packages, continuing on failure
    install_package_list() {
        local desc="$1"
        shift
        local packages=("$@")
        
        echo "Installing $desc..."
        for package in "${packages[@]}"; do
            if $APT_CMD install -y "$package" 2>/dev/null; then
                echo "  ✓ $package"
            else
                echo "  ✗ $package (not available or failed to install)"
            fi
        done
    }
    
    # Install packages in groups
    install_package_list "core dependencies" "${CORE_DEPS[@]}"
    install_package_list "GUI and graphics dependencies" "${GUI_DEPS[@]}"
    install_package_list "GStreamer dependencies" "${GSTREAMER_DEPS[@]}"
    install_package_list "X11 dependencies" "${X11_DEPS[@]}"
    install_package_list "network and security dependencies" "${NETWORK_DEPS[@]}"
    install_package_list "system dependencies" "${SYSTEM_DEPS[@]}"
    install_package_list "optional dependencies" "${OPTIONAL_DEPS[@]}"
    
    echo "System dependencies installation completed"
}

# Parse command line arguments
INSTALL_DEPS=true
DEPS_ONLY=false
for arg in "$@"; do
    case $arg in
        --skip-deps)
            INSTALL_DEPS=false
            shift
            ;;
        --deps-only)
            DEPS_ONLY=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--skip-deps] [--deps-only] [--help]"
            echo ""
            echo "Options:"
            echo "  --skip-deps  Skip installation of system dependencies"
            echo "  --deps-only  Install only system dependencies (skip CLI download)"
            echo "  --help       Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  BAMBU_VERSION  Version to install (default: latest)"
            exit 0
            ;;
    esac
done

# Install system dependencies unless skipped
if [ "$INSTALL_DEPS" = true ]; then
    install_system_dependencies
else
    echo "Skipping system dependencies installation (--skip-deps flag used)"
fi

# If deps-only mode, exit after installing dependencies
if [ "$DEPS_ONLY" = true ]; then
    if [ "$INSTALL_DEPS" = true ]; then
        echo "Dependencies-only installation completed (--deps-only flag used)"
    else
        echo "Dependencies-only mode requested but dependencies were skipped (--skip-deps flag used)"
    fi
    echo "Skipping CLI binary download and installation"
    exit 0
fi

echo "Installing Bambu Studio CLI binary..."

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