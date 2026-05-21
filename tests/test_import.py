#!/usr/bin/env python3
"""Test script to verify all modules can be imported correctly"""

import sys
from pathlib import Path

print("=" * 60)
print("AFNI Preprocessing GUI - Module Import Test")
print("=" * 60)
print()

# Test imports
try:
    print("Testing core modules...")
    from core.config_manager import ConfigManager
    from core.logger import PipelineLogger
    from core.pipeline_manager import PipelineManager, Subject, ScriptInfo
    from core.script_runner import ScriptRunner, DirectScriptRunner
    print("✓ Core modules imported successfully")
    print()

    print("Testing PyQt6 modules...")
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    print("✓ PyQt6 modules imported successfully")
    print()

    print("Testing GUI modules...")
    # Note: We can't instantiate GUI components without QApplication
    # but we can import them
    from gui.main_window import MainWindow
    from gui.widgets.subject_selector import SubjectSelector
    from gui.widgets.script_list import ScriptList
    from gui.widgets.log_viewer import LogViewer
    from gui.widgets.progress_panel import ProgressPanel
    from gui.widgets.config_panel import ConfigPanel
    print("✓ GUI modules imported successfully")
    print()

    print("Testing configuration...")
    config = ConfigManager()
    print(f"✓ Default FreeSurfer path: {config.get('freesurfer_home')}")
    print(f"✓ Default execution mode: {config.get('execution_mode')}")
    print()

    print("Testing logger...")
    logger = PipelineLogger()
    print(f"✓ Logger initialized")
    print()

    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print()
    print("The application is ready to run.")
    print("Note: GUI cannot be displayed in this terminal environment.")
    print()
    print("To run the GUI:")
    print("1. Open your macOS Terminal app")
    print("2. Run: cd", Path.cwd())
    print("3. Run: python3 main.py")
    print()
    print("Or simply double-click 'AFNI_GUI.command' in Finder!")
    print()

except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
