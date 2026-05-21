#!/bin/bash
# Build AFNI Pipeline Manager for Linux
set -e

echo "=== AFNI Pipeline Manager — Linux Build ==="

# Check for pyinstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Build
echo "Building executable..."
pyinstaller afni_pipeline.spec --noconfirm

# Create tarball
echo "Creating tarball..."
cd dist
tar czf "AFNI-Pipeline-Manager-v2.0.3-Linux.tar.gz" "AFNI Pipeline Manager"
cd ..

echo ""
echo "=== Build complete ==="
echo "  Executable → dist/AFNI Pipeline Manager/"
echo "  Tarball    → dist/AFNI-Pipeline-Manager-v2.0.3-Linux.tar.gz"
