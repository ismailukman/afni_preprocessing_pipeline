#!/bin/bash
# Quick start script for AFNI Preprocessing GUI

echo "=========================================="
echo "AFNI Preprocessing Pipeline - GUI"
echo "=========================================="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Check if PyQt6 is installed
if python3 -c "import PyQt6" 2>/dev/null; then
    echo "✓ PyQt6 is installed"
else
    echo "✗ PyQt6 is not installed"
    echo ""
    echo "Installing PyQt6..."
    pip3 install PyQt6
fi

# Check AFNI
if command -v 3dinfo &> /dev/null; then
    echo "✓ AFNI is available"
else
    echo "⚠ AFNI not found in PATH"
fi

# Check tcsh
if command -v tcsh &> /dev/null; then
    echo "✓ tcsh is available"
else
    echo "⚠ tcsh not found"
fi

echo ""
echo "Starting GUI..."
echo ""

# Run the application
python3 main.py
