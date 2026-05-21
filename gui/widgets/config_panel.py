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
    redetect_clicked = pyqtSignal()    # manual TR/TPs/runs re-detection request
    apply_tr_clicked = pyqtSignal(float)  # user-edited TR value to stamp on funcs

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

        # ── Processing Parameters (forwarded to afni_proc.py via script 004) ──
        proc_group = QGroupBox("Processing Parameters")
        proc_form = QFormLayout()

        self.motion_thresh_spin = QDoubleSpinBox()
        self.motion_thresh_spin.setRange(0.0, 5.0); self.motion_thresh_spin.setSingleStep(0.05)
        self.motion_thresh_spin.setDecimals(2); self.motion_thresh_spin.setSuffix(" mm")
        self.motion_thresh_spin.valueChanged.connect(self.on_config_changed)
        proc_form.addRow("Motion censor threshold:", self.motion_thresh_spin)

        self.outlier_thresh_spin = QDoubleSpinBox()
        self.outlier_thresh_spin.setRange(0.0, 1.0); self.outlier_thresh_spin.setSingleStep(0.01)
        self.outlier_thresh_spin.setDecimals(3)
        self.outlier_thresh_spin.valueChanged.connect(self.on_config_changed)
        proc_form.addRow("Outlier fraction:", self.outlier_thresh_spin)

        self.polort_spin = QSpinBox()
        self.polort_spin.setRange(-1, 9)
        self.polort_spin.setToolTip("-1 = auto choose based on run duration")
        self.polort_spin.valueChanged.connect(self.on_config_changed)
        proc_form.addRow("Polynomial order:", self.polort_spin)

        bp_row = QHBoxLayout()
        self.bp_low_spin = QDoubleSpinBox()
        self.bp_low_spin.setRange(0.0, 1.0); self.bp_low_spin.setSingleStep(0.005)
        self.bp_low_spin.setDecimals(3); self.bp_low_spin.setSuffix(" Hz")
        self.bp_low_spin.valueChanged.connect(self.on_config_changed)
        self.bp_high_spin = QDoubleSpinBox()
        self.bp_high_spin.setRange(0.0, 1.0); self.bp_high_spin.setSingleStep(0.005)
        self.bp_high_spin.setDecimals(3); self.bp_high_spin.setSuffix(" Hz")
        self.bp_high_spin.valueChanged.connect(self.on_config_changed)
        bp_row.addWidget(self.bp_low_spin)
        bp_row.addWidget(QLabel("→"))
        bp_row.addWidget(self.bp_high_spin)
        bp_wrap = QWidget(); bp_wrap.setLayout(bp_row)
        proc_form.addRow("Bandpass filter:", bp_wrap)

        self.blur_size_spin = QDoubleSpinBox()
        self.blur_size_spin.setRange(0.0, 15.0); self.blur_size_spin.setSingleStep(0.5)
        self.blur_size_spin.setDecimals(1); self.blur_size_spin.setSuffix(" mm FWHM")
        self.blur_size_spin.valueChanged.connect(self.on_config_changed)
        proc_form.addRow("Spatial blur:", self.blur_size_spin)

        self.tpattern_combo = QComboBox()
        for pat in ("seq+z", "seq-z", "alt+z", "alt-z", "alt+z2", "alt-z2",
                    "FROM_IMAGE", "@slice_timing.txt"):
            self.tpattern_combo.addItem(pat)
        self.tpattern_combo.setEditable(True)
        self.tpattern_combo.setToolTip("Slice timing pattern passed to afni_proc.py "
                                       "(-tshift_opts_ts -tpattern …)")
        self.tpattern_combo.currentTextChanged.connect(self.on_config_changed)
        proc_form.addRow("Slice timing pattern:", self.tpattern_combo)

        self.template_edit = QLineEdit()
        self.template_edit.setPlaceholderText("MNI152_2009_template_SSW.nii.gz")
        self.template_edit.textChanged.connect(self.on_config_changed)
        proc_form.addRow("Standard template:", self.template_edit)

        proc_group.setLayout(proc_form)
        layout.addWidget(proc_group)

        # Detected Parameters (Auto-detected during processing)
        detected_group = QGroupBox("Auto-Detected Parameters")
        detected_layout = QFormLayout()

        # TR (Repetition Time) — editable spinbox + "applied from <subject>" label
        tr_row = QHBoxLayout()
        self.tr_spin = QDoubleSpinBox()
        self.tr_spin.setRange(0.0, 60.0)
        self.tr_spin.setDecimals(3)
        self.tr_spin.setSingleStep(0.1)
        self.tr_spin.setSuffix(" s")
        self.tr_spin.setValue(0.0)
        self.tr_spin.setToolTip(
            "Repetition time. Auto-filled by detection, but you can override "
            "it here.  Use the Apply TR button to write your value back into "
            "every functional run via 3drefit."
        )
        self.apply_tr_btn = QPushButton("Apply TR")
        self.apply_tr_btn.setToolTip(
            "Stamp the TR shown here into every functional run "
            "(<subject>/PreprocessedData/func_run*+orig.nii[.gz]) using "
            "AFNI 3drefit -TR. Use this when the header TR is wrong or missing."
        )
        self.apply_tr_btn.setObjectName("applyTrBtn")
        self.apply_tr_btn.clicked.connect(
            lambda: self.apply_tr_clicked.emit(self.tr_spin.value())
        )
        tr_row.addWidget(self.tr_spin)
        tr_row.addWidget(self.apply_tr_btn)
        tr_wrap = QWidget(); tr_wrap.setLayout(tr_row)
        detected_layout.addRow("TR (Repetition Time):", tr_wrap)

        self.detected_tr_source_label = QLabel("Not yet detected")
        self.detected_tr_source_label.setStyleSheet("color: #888; font-style: italic; font-size: 9pt;")
        detected_layout.addRow("", self.detected_tr_source_label)

        # Keep the old read-only label name aliased to the new spin so older
        # callers (update_detected_parameters / reset_detected_parameters)
        # continue to function via small adapters below.
        self.detected_tr_label = self.detected_tr_source_label

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

        # Manual re-detect button (for when auto-detect failed or you just want to refresh)
        from PyQt6.QtWidgets import QPushButton
        self.redetect_btn = QPushButton("🔄 Re-detect now")
        self.redetect_btn.setToolTip(
            "Scan the selected subjects' PreprocessedData folders right now for "
            "TR / timepoints / runs.\nUseful if auto-detect didn't fire (e.g. before "
            "the pipeline has been started, or if files were added after start)."
        )
        self.redetect_btn.clicked.connect(self.redetect_clicked.emit)
        detected_layout.addRow("", self.redetect_btn)

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

        # Processing parameters (with sensible defaults)
        self.motion_thresh_spin.setValue(float(self.config.get("motion_threshold", 0.4)))
        self.outlier_thresh_spin.setValue(float(self.config.get("outlier_threshold", 0.1)))
        self.polort_spin.setValue(int(self.config.get("polort", 2)))
        self.bp_low_spin.setValue(float(self.config.get("bandpass_low", 0.01)))
        self.bp_high_spin.setValue(float(self.config.get("bandpass_high", 0.1)))
        self.blur_size_spin.setValue(float(self.config.get("blur_size", 6.0)))
        self.tpattern_combo.setCurrentText(self.config.get("tpattern", "seq+z"))
        self.template_edit.setText(self.config.get("template", "MNI152_2009_template_SSW.nii.gz"))

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

        # Processing parameters
        self.config.set("motion_threshold",  self.motion_thresh_spin.value())
        self.config.set("outlier_threshold", self.outlier_thresh_spin.value())
        self.config.set("polort",            self.polort_spin.value())
        self.config.set("bandpass_low",      self.bp_low_spin.value())
        self.config.set("bandpass_high",     self.bp_high_spin.value())
        self.config.set("blur_size",         self.blur_size_spin.value())
        self.config.set("tpattern",          self.tpattern_combo.currentText())
        self.config.set("template",          self.template_edit.text() or "MNI152_2009_template_SSW.nii.gz")

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

    def update_detected_parameters(self, tr=None, timepoints=None, num_runs=None,
                                   subject_id: str = None):
        """Update the displayed detected parameters.

        ``subject_id`` (if provided) is shown beneath the TR row so users can
        see which subject the values were measured on.
        """
        if tr is not None:
            self.tr_spin.setValue(float(tr))
            src = f" — detected from {subject_id}" if subject_id else ""
            self.detected_tr_source_label.setText(f"✓ {tr:.3f} s{src}")
            self.detected_tr_source_label.setStyleSheet(
                "color: #4CAF50; font-weight: bold; font-size: 9pt;"
            )

        if timepoints is not None:
            text = f"{timepoints} volumes"
            if subject_id:
                text += f" — detected from {subject_id}"
            self.detected_timepoints_label.setText(text)
            self.detected_timepoints_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

        if num_runs is not None:
            text = f"{num_runs} run(s)"
            if subject_id:
                text += f" — detected from {subject_id}"
            self.detected_runs_label.setText(text)
            self.detected_runs_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

    def reset_detected_parameters(self):
        """Reset detected parameters to 'not yet detected' state"""
        self.detected_tr_source_label.setText("Not yet detected")
        self.detected_tr_source_label.setStyleSheet("color: #888; font-style: italic; font-size: 9pt;")
        self.tr_spin.setValue(0.0)

        self.detected_timepoints_label.setText("Not yet detected")
        self.detected_timepoints_label.setStyleSheet("color: #666; font-style: italic;")

        self.detected_runs_label.setText("Not yet detected")
        self.detected_runs_label.setStyleSheet("color: #666; font-style: italic;")
