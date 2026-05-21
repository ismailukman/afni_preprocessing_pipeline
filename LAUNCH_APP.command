#!/bin/bash
# AFNI Preprocessing GUI Launcher
# Double-click this file from Finder to launch the application

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Launch the GUI
echo "=========================================="
echo "  AFNI Preprocessing Pipeline GUI"
echo "=========================================="
echo ""
echo "Launching application..."
echo ""

python3 main.py

# Keep terminal open if there's an error
if [ $? -ne 0 ]; then
    echo ""
    echo "Press any key to close..."
    read -n 1
fi
