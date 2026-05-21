"""Configuration panel for pipeline settings"""
import sys
import platform
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                              QLabel, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
                              QPushButton, QLineEdit, QFileDialog, QFormLayout,
                              QScrollArea, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, Qt


class ConfigPanel(QWidget):
    """Widget for configuring pipeline settings"""

    config_changed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.init_ui()
        self.load_config()

    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area for better resizing behavior
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Content widget inside scroll area
        content_widget = QWidget()
        layout = QVBoxLayout()
        content_widget.setLayout(layout)

        # Execution Mode
        exec_group = QGroupBox("Execution Mode")
        exec_layout = QVBoxLayout()

        self.exec_mode_combo = QComboBox()
        self.exec_mode_combo.addItem("⚡ Auto-run: Execute all without waiting", "auto")
        self.exec_mode_combo.addItem("🛑 Step-by-step: Wait after each script", "step-by-step")
        self.exec_mode_combo.addItem("🔄 Semi-auto: Pause only on errors", "semi-auto")
        self.exec_mode_combo.currentIndexChanged.connect(self.on_config_changed)
        exec_layout.addWidget(QLabel("Execution mode:"))
        exec_layout.addWidget(self.exec_mode_combo)

        self.stop_on_error_check = QCheckBox("Stop pipeline on error")
        self.stop_on_error_check.stateChanged.connect(self.on_config_changed)
        exec_layout.addWidget(self.stop_on_error_check)

        self.archive_run_check = QCheckBox(
            "Default to Restart when prompted (archive existing PreprocessedData)"
        )
        self.archive_run_check.setToolTip(
            "When a subject's PreprocessedData folder already has data, you'll be\n"
            "asked whether to Continue (resume) or Restart (archive to _b/_c/…).\n"
            "This setting only controls the default if the prompt is auto-dismissed."
        )
        self.archive_run_check.stateChanged.connect(self.on_config_changed)
        exec_layout.addWidget(self.archive_run_check)

        exec_group.setLayout(exec_layout)
        layout.addWidget(exec_group)

        # FreeSurfer Settings
        fs_group = QGroupBox("FreeSurfer Settings")
        fs_layout = QFormLayout()

        fs_path_layout = QHBoxLayout()
        self.freesurfer_path_edit = QLineEdit()
        self.freesurfer_path_edit.setMinimumWidth(200)
        self.freesurfer_path_edit.textChanged.connect(self.on_config_changed)
        fs_path_layout.addWidget(self.freesurfer_path_edit, 1)

        fs_browse_btn = QPushButton("Browse...")
        fs_browse_btn.setMaximumWidth(100)
        fs_browse_btn.clicked.connect(self.browse_freesurfer)
        fs_path_layout.addWidget(fs_browse_btn)

        fs_layout.addRow("FREESURFER_HOME:", fs_path_layout)

        fs_group.setLayout(fs_layout)
        layout.addWidget(fs_group)

        # Script Options
        script_group = QGroupBox("Script Options")
        script_layout = QVBoxLayout()

        self.skip_interactive_check = QCheckBox("Skip interactive GUI (003b SUMA QA)")
        self.skip_interactive_check.setChecked(True)
        self.skip_interactive_check.stateChanged.connect(self.on_config_changed)
        script_layout.addWidget(self.skip_interactive_check)

        # Enable/disable scripts
        script_layout.addWidget(QLabel("Enable/Disable Scripts:"))

        self.script_checks = {}
        script_names = {
            "001a_dcm2niix": "1. DICOM to NIfTI Conversion",
            "001c_rename_files": "2. Rename Files",
            "002_batch_defaceMRI": "3. Deface/Reface MRI",
            "003_FreeSurfer_recon": "4. FreeSurfer Reconstruction",
            "003b_FreeSurferQA_SUMA": "5. SUMA Format Conversion",
            "004_createAP_struct_rf": "6. Create Processing Script",
            "004_execute_proc": "7. Execute Processing Script",
            "005_afni2nifti": "8. AFNI to NIfTI Conversion",
            "006_get_motion_files": "9. Extract Motion Files",
        }

        for script_key, script_label in script_names.items():
            check = QCheckBox(script_label)
            check.setChecked(True)
            check.stateChanged.connect(self.on_config_changed)
            self.script_checks[script_key] = check
            script_layout.addWidget(check)

        script_group.setLayout(script_layout)
        layout.addWidget(script_group)

        # Detected Parameters (Auto-detected during processing)
        detected_group = QGroupBox("Auto-Detected Parameters")
        detected_layout = QFormLayout()

        # TR (Repetition Time)
        self.detected_tr_label = QLabel("Not yet detected")
        self.detected_tr_label.setStyleSheet("color: #666; font-style: italic;")
        detected_layout.addRow("TR (Repetition Time):", self.detected_tr_label)

        # Timepoints per run
        self.detected_timepoints_label = QLabel("Not yet detected")
        self.detected_timepoints_label.setStyleSheet("color: #666; font-style: italic;")
        detected_layout.addRow("Timepoints per run:", self.detected_timepoints_label)

        # Number of runs
        self.detected_runs_label = QLabel("Not yet detected")
        self.detected_runs_label.setStyleSheet("color: #666; font-style: italic;")
        detected_layout.addRow("Number of functional runs:", self.detected_runs_label)

        # Info label
        info_label = QLabel("⚡ These values are automatically detected from your functional data during pipeline execution")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #2196F3; font-size: 9pt; padding: 5px;")
        detected_layout.addRow("", info_label)

        detected_group.setLayout(detected_layout)
        layout.addWidget(detected_group)

        # Save/Load buttons
        button_layout = QHBoxLayout()

        save_btn = QPushButton("💾 Save Configuration")
        save_btn.clicked.connect(self.save_config)
        save_btn.setToolTip("Save current settings to disk")
        button_layout.addWidget(save_btn)

        reset_btn = QPushButton("🔄 Reset to Defaults")
        reset_btn.clicked.connect(self.reset_config)
        reset_btn.setToolTip("Restore default settings")
        button_layout.addWidget(reset_btn)

        layout.addLayout(button_layout)

        layout.addStretch()

        # Set content widget in scroll area
        scroll_area.setWidget(content_widget)

        # Add scroll area to main layout
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)

        # Set size policy
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    def get_default_freesurfer_path(self):
        """Get default FreeSurfer path based on platform"""
        system = platform.system()

        if system == "Darwin":  # macOS
            return "/Applications/freesurfer/7.1.1"
        elif system == "Linux":
            # Common Linux locations
            possible_paths = [
                "/usr/local/freesurfer",
                str(Path.home() / "freesurfer"),
                "/opt/freesurfer"
            ]
            for path in possible_paths:
                if Path(path).exists():
                    return path
            return "/usr/local/freesurfer"
        elif system == "Windows":
            return "C:\\Program Files\\freesurfer"
        else:
            return str(Path.home() / "freesurfer")

    def browse_freesurfer(self):
        """Browse for FreeSurfer directory"""
        current_path = self.freesurfer_path_edit.text()

        # Determine starting directory
        if current_path and Path(current_path).exists():
            start_dir = current_path
        else:
            # Platform-specific default
            if platform.system() == "Darwin":
                start_dir = "/Applications"
            elif platform.system() == "Windows":
                start_dir = "C:\\Program Files"
            else:
                start_dir = "/usr/local"

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select FreeSurfer Home Directory",
            start_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if directory:
            self.freesurfer_path_edit.setText(directory)

    def on_config_changed(self):
        """Handle configuration change"""
        self.config_changed.emit()

    def load_config(self):
        """Load configuration into UI"""
        # Execution mode
        exec_mode = self.config.get("execution_mode", "auto")
        for i in range(self.exec_mode_combo.count()):
            if self.exec_mode_combo.itemData(i) == exec_mode:
                self.exec_mode_combo.setCurrentIndex(i)
                break

        # Stop on error
        self.stop_on_error_check.setChecked(self.config.get("stop_on_error", False))
        self.archive_run_check.setChecked(self.config.get("archive_previous_run", True))

        # FreeSurfer path
        default_path = self.get_default_freesurfer_path()
        self.freesurfer_path_edit.setText(self.config.get("freesurfer_home", default_path))

        # Skip interactive
        self.skip_interactive_check.setChecked(self.config.get("skip_interactive", True))

        # Script enables
        enabled_scripts = self.config.get("enabled_scripts", {})
        for script_key, check in self.script_checks.items():
            check.setChecked(enabled_scripts.get(script_key, True))

    def save_config(self):
        """Save current configuration"""
        # Execution mode
        self.config.set("execution_mode", self.exec_mode_combo.currentData())

        # Stop on error
        self.config.set("stop_on_error", self.stop_on_error_check.isChecked())

        # Archive previous PreprocessedData on rerun
        self.config.set("archive_previous_run", self.archive_run_check.isChecked())

        # FreeSurfer path
        self.config.set("freesurfer_home", self.freesurfer_path_edit.text())

        # Skip interactive
        self.config.set("skip_interactive", self.skip_interactive_check.isChecked())

        # Script enables
        enabled_scripts = {}
        for script_key, check in self.script_checks.items():
            enabled_scripts[script_key] = check.isChecked()
        self.config.set("enabled_scripts", enabled_scripts)

        # Save to file (silent — caller can show feedback if needed)
        self.config.save_config()

    def reset_config(self):
        """Reset to default configuration"""
        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Reset Configuration",
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.config.reset_to_defaults()
            self.load_config()
            QMessageBox.information(self, "Reset Complete",
                                   "Configuration has been reset to defaults.")

    def get_current_config(self):
        """Get current configuration from UI"""
        return {
            "execution_mode": self.exec_mode_combo.currentData(),
            "stop_on_error": self.stop_on_error_check.isChecked(),
            "freesurfer_home": self.freesurfer_path_edit.text(),
            "skip_interactive": self.skip_interactive_check.isChecked(),
        }

    def update_detected_parameters(self, tr=None, timepoints=None, num_runs=None):
        """Update the displayed detected parameters"""
        if tr is not None:
            self.detected_tr_label.setText(f"{tr:.2f} seconds")
            self.detected_tr_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

        if timepoints is not None:
            self.detected_timepoints_label.setText(f"{timepoints} volumes")
            self.detected_timepoints_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

        if num_runs is not None:
            self.detected_runs_label.setText(f"{num_runs} run(s)")
            self.detected_runs_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

    def reset_detected_parameters(self):
        """Reset detected parameters to 'not yet detected' state"""
        self.detected_tr_label.setText("Not yet detected")
        self.detected_tr_label.setStyleSheet("color: #666; font-style: italic;")

        self.detected_timepoints_label.setText("Not yet detected")
        self.detected_timepoints_label.setStyleSheet("color: #666; font-style: italic;")

        self.detected_runs_label.setText("Not yet detected")
        self.detected_runs_label.setStyleSheet("color: #666; font-style: italic;")
