#!/bin/bash
# Build AFNI Pipeline Manager .app and .dmg for macOS
set -e

echo "=== AFNI Pipeline Manager — macOS Build ==="

# Check for pyinstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Build
echo "Building .app bundle..."
pyinstaller afni_pipeline.spec --noconfirm

# Create DMG
echo "Creating DMG..."
mkdir -p dmg_contents
cp -R "dist/AFNI Pipeline Manager.app" dmg_contents/
ln -sf /Applications dmg_contents/Applications
hdiutil create -volname "AFNI Pipeline Manager" \
    -srcfolder dmg_contents \
    -ov -format UDZO \
    "dist/AFNI-Pipeline-Manager-v2.0.3-macOS.dmg"
rm -rf dmg_contents

echo ""
echo "=== Build complete ==="
echo "  .app → dist/AFNI Pipeline Manager.app"
echo "  .dmg → dist/AFNI-Pipeline-Manager-v2.0.1-macOS.dmg"
