"""Main window for the AFNI Preprocessing GUI"""
from pathlib import Path
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QSplitter, QTabWidget, QMenuBar, QMenu, QMessageBox,
                              QDialog, QDialogButtonBox, QLabel, QScrollArea)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QIcon, QPixmap

from gui.widgets.subject_selector import SubjectSelector
from gui.widgets.script_list import ScriptList
from gui.widgets.log_viewer import LogViewer
from gui.widgets.progress_panel import ProgressPanel
from gui.widgets.config_panel import ConfigPanel

from core.config_manager import ConfigManager
from core.logger import PipelineLogger, install_stdout_stderr_capture
from core.pipeline_manager import PipelineManager, Subject


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Initialize managers
        self.config = ConfigManager()
        self.logger = PipelineLogger()
        # Mirror anything printed to sys.stdout / sys.stderr (uncaught
        # tracebacks, ad-hoc print() calls, library messages) into the GUI's
        # Pipeline tab via the same signal the rest of the logger uses.
        install_stdout_stderr_capture(self.logger.signals)
        self.pipeline_manager = None

        # Settings for window geometry
        self.settings = QSettings("AFNIPreprocessing", "AFNIGUIApp")

        self.init_ui()
        self.setup_connections()
        self.restore_window_state()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("AFNI Preprocessing Pipeline")
        self.setMinimumSize(1200, 800)

        # Set window icon
        icon_path = Path(__file__).parent.parent / "resources" / "icons" / "afni_guiapp.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Create splitter for left/right panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left Panel ---
        left_panel_scroll_area = QScrollArea()
        left_panel_scroll_area.setWidgetResizable(True)
        left_panel_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_panel_content = QWidget()
        left_layout = QVBoxLayout(left_panel_content)

        # Logo (above tabs) — prefer the hero artwork; fall back to the app icon
        repo_root = Path(__file__).parent.parent
        hero_path = repo_root / "docs" / "images" / "afni_guiapp_hero.png"
        icon_path = repo_root / "resources" / "icons" / "afni_guiapp.png"
        logo_path = hero_path if hero_path.exists() else icon_path
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaledToWidth(260, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setStyleSheet("background-color: transparent; padding: 4px; margin: 2px;")
            left_layout.addWidget(logo_label)

        # Bold app-title label under the logo (also mirrored on the splash screen)
        title_label = QLabel("AFNI Pipeline Manager")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(
            "font-size: 14pt; font-weight: bold; color: #64b5f6; "
            "padding: 2px; margin-bottom: 6px;"
        )
        left_layout.addWidget(title_label)

        # Subjects / Configuration as side-by-side tabs
        self.subject_selector = SubjectSelector()
        self.config_panel = ConfigPanel(self.config)

        self.left_tabs = QTabWidget()
        self.left_tabs.addTab(self.subject_selector, "Subjects")
        self.left_tabs.addTab(self.config_panel, "Configuration")
        left_layout.addWidget(self.left_tabs, 1)

        left_panel_scroll_area.setWidget(left_panel_content)
        splitter.addWidget(left_panel_scroll_area)


        # --- Right Panel ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.progress_panel = ProgressPanel()
        right_layout.addWidget(self.progress_panel)

        self.script_list = None
        self.log_viewer = LogViewer()
        right_layout.addWidget(self.log_viewer, 1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)
        self.statusBar().showMessage("Ready")
        self.initialize_pipeline_manager()
        self.create_menu_bar()

    def create_menu_bar(self):
        """Create menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open Parent Directory...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.subject_selector.browse_directory)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_config_action = QAction("&Save Configuration", self)
        save_config_action.setShortcut("Ctrl+S")
        save_config_action.triggered.connect(self.config_panel.save_config)
        file_menu.addAction(save_config_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Pipeline menu
        pipeline_menu = menubar.addMenu("&Pipeline")

        start_action = QAction("&Start Pipeline", self)
        start_action.setShortcut("F5")
        start_action.triggered.connect(self.start_pipeline)
        pipeline_menu.addAction(start_action)

        pause_action = QAction("&Pause Pipeline", self)
        pause_action.setShortcut("F6")
        pause_action.triggered.connect(self.progress_panel.pause_clicked.emit)
        pipeline_menu.addAction(pause_action)

        stop_action = QAction("&Stop Pipeline", self)
        stop_action.setShortcut("F7")
        stop_action.triggered.connect(self.progress_panel.stop_clicked.emit)
        pipeline_menu.addAction(stop_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About AFNI Pipeline Manager…", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        author_action = QAction("&Author…", self)
        author_action.triggered.connect(self.show_author)
        help_menu.addAction(author_action)

        ack_action = QAction("&Acknowledgements…", self)
        ack_action.triggered.connect(self.show_acknowledgements)
        help_menu.addAction(ack_action)

        help_menu.addSeparator()

        github_action = QAction("Open &GitHub Repository", self)
        github_action.triggered.connect(self.open_github_repo)
        help_menu.addAction(github_action)

        user_manual_action = QAction("&User Manual…", self)
        user_manual_action.triggered.connect(self.show_user_manual)
        help_menu.addAction(user_manual_action)

    def initialize_pipeline_manager(self):
        """Initialize the pipeline manager"""
        self.pipeline_manager = PipelineManager(self.config, self.logger)

        # Create script list with pipeline scripts
        self.script_list = ScriptList(self.pipeline_manager.scripts)

        # Insert script list into right panel (after progress panel)
        right_layout = self.centralWidget().findChild(QVBoxLayout)
        if right_layout:
            # Find the progress panel widget and insert after it
            for i in range(right_layout.count()):
                widget = right_layout.itemAt(i).widget()
                if isinstance(widget, ProgressPanel):
                    right_layout.insertWidget(i + 1, self.script_list)
                    break

        # Populate step indicator with currently enabled scripts
        self._refresh_step_indicator()

    def _resolve_archive_choices(self, subjects) -> bool:
        """For each subject with non-empty PreprocessedData, ask Continue vs Restart.

        Sets ``subject.archive_existing`` to True (Restart) or False (Continue).
        A single "Apply to all remaining" option is offered once more than one
        subject needs prompting.  Returns False if the user cancels — in that
        case the caller should abort.
        """
        candidates = []
        for s in subjects:
            try:
                pre = s.path / "PreprocessedData"
                if pre.is_dir() and any(pre.iterdir()):
                    candidates.append(s)
            except OSError:
                continue
        if not candidates:
            return True

        apply_to_all = False
        bulk_choice = None  # True=Restart, False=Continue

        for subject in candidates:
            if apply_to_all:
                subject.archive_existing = bulk_choice
                continue

            dlg = QMessageBox(self)
            dlg.setWindowTitle("Existing PreprocessedData")
            dlg.setIcon(QMessageBox.Icon.Question)
            dlg.setText(f"<b>{subject.subject_id}</b> already has a "
                        f"<code>PreprocessedData</code> folder with data.")
            dlg.setInformativeText(
                "▶ <b>Continue</b> — resume using the existing files "
                "(scripts may skip steps that already have outputs).<br><br>"
                "🔄 <b>Restart</b> — archive the existing folder to "
                "<code>PreprocessedData_b</code> (or next free letter) and "
                "start a fresh run."
            )
            cont_btn = dlg.addButton("▶ Continue", QMessageBox.ButtonRole.AcceptRole)
            restart_btn = dlg.addButton("🔄 Restart", QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = dlg.addButton(QMessageBox.StandardButton.Cancel)

            apply_box = None
            if len(candidates) > 1:
                from PyQt6.QtWidgets import QCheckBox
                apply_box = QCheckBox("Apply this choice to all remaining subjects")
                dlg.setCheckBox(apply_box)

            dlg.setDefaultButton(cont_btn)
            dlg.exec()

            clicked = dlg.clickedButton()
            if clicked is cancel_btn:
                return False
            choice_restart = (clicked is restart_btn)
            subject.archive_existing = choice_restart

            if apply_box is not None and apply_box.isChecked():
                apply_to_all = True
                bulk_choice = choice_restart

        return True

    def _refresh_step_indicator(self):
        """Push the currently-enabled pipeline scripts into the step indicator.

        Each step is rendered as a numbered circle (1..N) so the label is just
        the position; the script's full name is used as the match key.
        """
        if not self.pipeline_manager:
            return
        enabled = self.pipeline_manager.get_enabled_scripts()
        steps = [{"label": str(i + 1), "key": s.name} for i, s in enumerate(enabled)]
        self.progress_panel.set_steps(steps)

    def setup_connections(self):
        """Setup signal/slot connections"""
        # Subject selector
        self.subject_selector.subjects_changed.connect(self.on_subjects_changed)
        self.subject_selector.apply_additions_clicked.connect(self.on_apply_additions)

        # Progress panel
        self.progress_panel.start_clicked.connect(self.start_pipeline)
        self.progress_panel.pause_clicked.connect(self.pause_pipeline)
        self.progress_panel.resume_clicked.connect(self.resume_pipeline)
        self.progress_panel.stop_clicked.connect(self.stop_pipeline)

        # Configuration
        self.config_panel.config_changed.connect(self.on_config_changed)
        self.config_panel.redetect_clicked.connect(self.on_redetect_clicked)
        self.config_panel.apply_tr_clicked.connect(self.on_apply_tr)

        # Logger signals
        self.logger.signals.log_message.connect(self.on_log_message)

    def on_subjects_changed(self, subjects):
        """Handle subject selection change"""
        self.statusBar().showMessage(f"{len(subjects)} subject(s) selected")

    def on_apply_tr(self, tr_value: float):
        """Stamp the user-edited TR into every functional run via 3drefit -TR."""
        import subprocess
        if tr_value <= 0:
            QMessageBox.warning(self, "Invalid TR",
                                "Enter a positive TR value before applying.")
            return
        subjects = self.subject_selector.get_selected_subjects()
        if not subjects:
            QMessageBox.information(self, "Apply TR",
                                    "Select at least one subject first.")
            return
        # Use shared patterns from the pipeline manager so this matches the
        # naming used by detection.
        patterns = ["func_run*+orig.nii.gz", "func_run*+orig.nii",
                    "func_run*.nii.gz", "func_run*.nii",
                    "*_task-*_bold.nii.gz", "*_task-*_bold.nii"]
        seen, updated, failed = 0, 0, []
        for s in subjects:
            pre = s.path / "PreprocessedData"
            if not pre.is_dir():
                continue
            funcs = []
            for pat in patterns:
                funcs.extend(sorted(pre.glob(pat)))
            # Dedupe while preserving order
            funcs = list(dict.fromkeys(funcs))
            for f in funcs:
                seen += 1
                try:
                    subprocess.run(["3drefit", "-TR", f"{tr_value}", str(f)],
                                   check=True, capture_output=True, text=True)
                    updated += 1
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    failed.append((str(f), str(e)))
        msg = f"3drefit -TR {tr_value} applied to {updated}/{seen} functional file(s)."
        if failed:
            msg += f"\nFailed: {len(failed)}.  First error:\n{failed[0][1][:200]}"
        QMessageBox.information(self, "Apply TR", msg)
        self.statusBar().showMessage(msg.splitlines()[0])

    def on_redetect_clicked(self):
        """Re-run scan-parameter detection for the currently-selected subjects."""
        if not self.pipeline_manager:
            self.statusBar().showMessage("Pipeline not initialized yet.")
            return
        subjects = self.subject_selector.get_selected_subjects()
        if not subjects:
            QMessageBox.information(
                self, "Re-detect",
                "Select at least one subject first — detection reads the\n"
                "PreprocessedData folder of each selected subject."
            )
            return
        # Use the running pipeline's current subject when one is active, else
        # the first selected subject — detection is per-subject.
        target = self.pipeline_manager.current_subject or subjects[0]
        self.statusBar().showMessage(f"Re-detecting parameters from {target.subject_id}…")
        self.config_panel.reset_detected_parameters()
        self.pipeline_manager._detect_scan_parameters(target)

    def on_config_changed(self):
        """Handle configuration change"""
        self.config_panel.save_config()
        if self.pipeline_manager:
            # Reload config in pipeline manager
            self.pipeline_manager.config = self.config
        # Reflect new enabled-script set in the step indicator immediately
        self._refresh_step_indicator()

    def on_log_message(self, message: str, level: str):
        """Route global pipeline-logger messages into the Log viewer Pipeline tab."""
        self.log_viewer.append_pipeline_log(message, level)

    def start_pipeline(self):
        """Start the pipeline"""
        # Get selected subjects
        subjects = self.subject_selector.get_selected_subjects()

        if not subjects:
            QMessageBox.warning(
                self,
                "No Subjects Selected",
                "Please select at least one subject to process."
            )
            return

        # Validate FreeSurfer installation (home dir + recon-all binary + license)
        fs_home = self.config.get("freesurfer_home")
        fs_root = Path(fs_home)
        if not fs_root.exists():
            QMessageBox.warning(
                self,
                "Invalid FreeSurfer Path",
                f"FreeSurfer home directory not found:\n{fs_home}\n\n"
                "Please check the configuration."
            )
            return
        recon_all = fs_root / "bin" / "recon-all"
        if not recon_all.exists():
            QMessageBox.warning(
                self,
                "FreeSurfer Incomplete",
                f"recon-all not found at:\n{recon_all}\n\n"
                "FreeSurfer appears to be missing or incompletely installed."
            )
            return
        if not (fs_root / "license.txt").exists() and not (fs_root / ".license").exists():
            QMessageBox.warning(
                self,
                "FreeSurfer License Missing",
                f"No license.txt found in:\n{fs_home}\n\n"
                "Get a free license at https://surfer.nmr.mgh.harvard.edu/registration.html "
                "and place it in the FreeSurfer home directory before running step 003."
            )
            # Not a hard stop — user may have set FS_LICENSE elsewhere

        # Ask Continue / Restart for any subject with existing PreprocessedData
        if not self._resolve_archive_choices(subjects):
            return  # user cancelled

        # Clear previous logs
        self.log_viewer.clear_all_logs()

        # Add tabs for each subject
        for subject in subjects:
            self.log_viewer.add_subject_tab(subject.subject_id)

        # Reset script list
        self.script_list.reset_all_status()

        # Reset progress
        self.progress_panel.reset()

        # Reset detected parameters
        self.config_panel.reset_detected_parameters()

        # Refresh step indicator with numbered circles (1..N) for enabled scripts
        self._refresh_step_indicator()

        # Set up pipeline manager
        self.pipeline_manager.set_subjects(subjects)

        # Connect pipeline signals
        self.connect_pipeline_signals()

        # Mark the initial subjects as "applied" and surface the Apply button
        self.subject_selector.mark_applied(subjects)
        self.subject_selector.set_pipeline_running(True)

        # Start pipeline
        self.pipeline_manager.start_pipeline()

        self.statusBar().showMessage("Pipeline started")

    def connect_pipeline_signals(self):
        """Connect pipeline manager signals"""
        # Disconnect any existing connections
        try:
            self.pipeline_manager.signals.script_started.disconnect()
            self.pipeline_manager.signals.script_finished.disconnect()
            self.pipeline_manager.signals.status_updated.disconnect()
            self.pipeline_manager.signals.output_line.disconnect()
            self.pipeline_manager.signals.error_line.disconnect()
            self.pipeline_manager.signals.pipeline_finished.disconnect()
            self.pipeline_manager.signals.waiting_for_user.disconnect()
            self.pipeline_manager.signals.parameters_detected.disconnect()
        except:
            pass

        # Connect signals
        self.pipeline_manager.signals.script_started.connect(self.on_script_started)
        self.pipeline_manager.signals.script_finished.connect(self.on_script_finished)
        self.pipeline_manager.signals.status_updated.connect(self.on_status_updated)
        self.pipeline_manager.signals.output_line.connect(self.on_output_line)
        self.pipeline_manager.signals.error_line.connect(self.on_error_line)
        self.pipeline_manager.signals.pipeline_finished.connect(self.on_pipeline_finished)
        self.pipeline_manager.signals.waiting_for_user.connect(self.on_waiting_for_user)
        self.pipeline_manager.signals.parameters_detected.connect(self.on_parameters_detected)

    def pause_pipeline(self):
        """Pause the pipeline"""
        if self.pipeline_manager:
            self.pipeline_manager.pause_pipeline()
            self.statusBar().showMessage("Pipeline paused")

    def resume_pipeline(self):
        """Resume the pipeline"""
        if self.pipeline_manager:
            self.pipeline_manager.resume_pipeline()
            self.statusBar().showMessage("Pipeline resumed")

    def stop_pipeline(self):
        """Stop the pipeline"""
        if self.pipeline_manager and self.pipeline_manager.is_running:
            reply = QMessageBox.question(
                self,
                "Stop Pipeline",
                "Are you sure you want to stop the pipeline?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.pipeline_manager.stop_pipeline()
                self.statusBar().showMessage("Pipeline stopped")

    def on_script_started(self, subject_id: str, script_name: str):
        """Handle script started"""
        self.script_list.update_script_status(subject_id, script_name, "running")
        self.progress_panel.update_status(subject_id, script_name)
        self.progress_panel.set_current_step(script_name)

        # Update progress
        current, total = self.pipeline_manager.get_progress()
        self.progress_panel.update_progress(current, total)

    def on_script_finished(self, subject_id: str, script_name: str, success: bool):
        """Handle script finished"""
        status = "completed" if success else "error"
        self.script_list.update_script_status(subject_id, script_name, status)
        self.progress_panel.mark_step_done(script_name, success)

        # Update progress
        current, total = self.pipeline_manager.get_progress()
        self.progress_panel.update_progress(current, total)

    def on_status_updated(self, subject_id: str, script_name: str, status: str):
        """Handle status update"""
        self.script_list.update_script_status(subject_id, script_name, status)

    def on_output_line(self, subject_id: str, line: str):
        """Handle stdout line."""
        self.log_viewer.append_log(subject_id, line, "INFO")

    def on_error_line(self, subject_id: str, line: str):
        """Handle stderr line.

        Many AFNI/shell tools write informational output to stderr (lines
        starting with ``++``).  Let the log viewer classify by content; only
        fall back to WARNING if nothing in the line looks like an error or info
        marker.  This avoids painting the whole log red.
        """
        self.log_viewer.append_log(subject_id, line, "WARNING")

    def on_apply_additions(self, new_subjects):
        """Queue newly-selected subjects into the running pipeline."""
        if not self.pipeline_manager or not self.pipeline_manager.is_running:
            return
        # Same prompt for the additions: continue vs restart
        if not self._resolve_archive_choices(new_subjects):
            return  # user cancelled — don't add anything
        added = self.pipeline_manager.add_subjects(new_subjects)
        if not added:
            return
        # New log tab for each added subject (script_list is shared across subjects)
        for subject in added:
            self.log_viewer.add_subject_tab(subject.subject_id)
        self.subject_selector.mark_applied(added)
        # Refresh progress total now that more steps are queued
        current, total = self.pipeline_manager.get_progress()
        self.progress_panel.update_progress(current, total)
        self.statusBar().showMessage(
            f"Added {len(added)} subject(s) to the queue: "
            + ", ".join(s.subject_id for s in added)
        )

    def on_pipeline_finished(self, success: bool):
        """Handle pipeline finished"""
        self.progress_panel.set_completed(success)
        self.subject_selector.set_pipeline_running(False)

        if success:
            self.statusBar().showMessage("Pipeline completed successfully!")
            QMessageBox.information(
                self,
                "Pipeline Complete",
                "All subjects processed successfully!"
            )
        else:
            self.statusBar().showMessage("Pipeline finished with errors")
            QMessageBox.warning(
                self,
                "Pipeline Complete",
                "Pipeline finished but some subjects had errors.\n"
                "Check the logs for details."
            )

    def on_waiting_for_user(self, subject_id: str, script_name: str):
        """Handle waiting for user confirmation"""
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Step-by-Step Mode")
        dialog.setText(f"Script completed: {script_name}\n\nContinue to next step?")
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No |
            QMessageBox.StandardButton.Abort
        )
        dialog.setDefaultButton(QMessageBox.StandardButton.Yes)

        result = dialog.exec()

        if result == QMessageBox.StandardButton.Yes:
            self.pipeline_manager.continue_after_pause()
        elif result == QMessageBox.StandardButton.No:
            self.pipeline_manager.skip_current_script()
        else:
            self.pipeline_manager.stop_pipeline()

    def on_parameters_detected(self, tr: float, timepoints: int, num_runs: int, subject_id: str = ""):
        """Handle auto-detected parameters (now includes which subject they came from)."""
        self.config_panel.update_detected_parameters(
            tr=tr, timepoints=timepoints, num_runs=num_runs,
            subject_id=subject_id or None,
        )
        who = f" (from {subject_id})" if subject_id else ""
        self.statusBar().showMessage(
            f"Detected{who}: TR={tr:.3f}s, Timepoints={timepoints}, Runs={num_runs}"
        )

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About AFNI Pipeline Manager",
            "<h2>AFNI Pipeline Manager</h2>"
            "<p><b>A PyQt6 GUI for the AFNI preprocessing pipeline.</b></p>"
            "<p>This application automates the resting-state fMRI preprocessing workflow:</p>"
            "<ul>"
            "<li>DICOM / PAR-REC → NIfTI conversion</li>"
            "<li>BIDS-style renaming</li>"
            "<li>Subject defacing / refacing</li>"
            "<li>FreeSurfer cortical reconstruction</li>"
            "<li>SUMA format conversion + QA</li>"
            "<li>afni_proc.py generation + execution</li>"
            "<li>AFNI → NIfTI conversion + motion extraction</li>"
            "</ul>"
            "<p style='color:#888'>Developed at the Adaptive Brain Networks Neuroimaging Lab "
            "(<b>ABN² Lab</b>).</p>"
        )

    def show_author(self):
        """Show author dialog"""
        QMessageBox.about(
            self,
            "Author",
            "<h3>Author</h3>"
            "<p><b>Lukman E. Ismaila, Ph.D.</b></p>"
            "<p>Adaptive Brain Networks Neuroimaging Lab "
            "(<b>ABN² Lab</b>)</p>"
            "<p>📧 <a href='mailto:ismailukman@gmail.com'>ismailukman@gmail.com</a></p>"
        )

    def show_acknowledgements(self):
        """Show acknowledgements dialog"""
        QMessageBox.about(
            self,
            "Acknowledgements",
            "<h3>Acknowledgements</h3>"
            "<p>This GUI builds on the following open-source tools — many thanks to "
            "their authors and communities:</p>"
            "<ul>"
            "<li><b>AFNI</b> — Robert W. Cox and the NIH/NIMH SSCC group</li>"
            "<li><b>FreeSurfer</b> — Martinos Center, MGH / Harvard</li>"
            "<li><b>dcm2niix</b> — Chris Rorden et al.</li>"
            "<li><b>PyQt6</b> — Riverbank Computing</li>"
            "</ul>"
            "<p>Developed at the <b>Adaptive Brain Networks Neuroimaging Lab "
            "(ABN² Lab)</b>.</p>"
        )

    def open_github_repo(self):
        """Open the project's GitHub repository in the default browser."""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(
            "https://github.com/ismailukman/afni_preprocessing_pipeline"
        ))

    def show_user_manual(self):
        """Show user manual"""
        manual_path = Path(__file__).parent.parent / "ReadMe.pdf"
        if manual_path.exists():
            import subprocess
            import sys
            if sys.platform == "darwin":
                subprocess.run(["open", str(manual_path)])
            elif sys.platform == "win32":
                subprocess.run(["start", str(manual_path)], shell=True)
            else:
                subprocess.run(["xdg-open", str(manual_path)])
        else:
            QMessageBox.information(
                self,
                "User Manual",
                "User manual not found.\n\n"
                "Please refer to ReadMe.pdf in the application directory."
            )

    def closeEvent(self, event):
        """Handle window close event"""
        # Save window state
        self.save_window_state()

        # Check if pipeline is running
        if self.pipeline_manager and self.pipeline_manager.is_running:
            reply = QMessageBox.question(
                self,
                "Pipeline Running",
                "The pipeline is currently running.\n\n"
                "Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

            # Stop pipeline
            self.pipeline_manager.stop_pipeline()

        event.accept()

    def save_window_state(self):
        """Save window geometry and state"""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

    def restore_window_state(self):
        """Restore window geometry and state"""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

        # Restore last parent directory
        last_dir = self.config.get("last_parent_dir")
        if last_dir and Path(last_dir).exists():
            self.subject_selector.set_parent_directory(last_dir)
