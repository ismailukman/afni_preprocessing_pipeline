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
from core.logger import PipelineLogger
from core.pipeline_manager import PipelineManager, Subject


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Initialize managers
        self.config = ConfigManager()
        self.logger = PipelineLogger()
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
        
        # Add logo
        logo_path = Path(__file__).parent.parent / "resources" / "icons" / "afni_guiapp.png"
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaledToWidth(300, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setStyleSheet("background-color: white; padding: 10px; border-radius: 8px; margin: 5px;")
            left_layout.addWidget(logo_label)

        # Subject selector
        self.subject_selector = SubjectSelector()
        left_layout.addWidget(self.subject_selector)

        # Configuration tabs
        config_tabs = QTabWidget()
        self.config_panel = ConfigPanel(self.config)
        config_tabs.addTab(self.config_panel, "Configuration")
        left_layout.addWidget(config_tabs)
        left_layout.addStretch() # Pushes content to the top

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

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        user_manual_action = QAction("&User Manual", self)
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

    def setup_connections(self):
        """Setup signal/slot connections"""
        # Subject selector
        self.subject_selector.subjects_changed.connect(self.on_subjects_changed)

        # Progress panel
        self.progress_panel.start_clicked.connect(self.start_pipeline)
        self.progress_panel.pause_clicked.connect(self.pause_pipeline)
        self.progress_panel.resume_clicked.connect(self.resume_pipeline)
        self.progress_panel.stop_clicked.connect(self.stop_pipeline)

        # Configuration
        self.config_panel.config_changed.connect(self.on_config_changed)

        # Logger signals
        self.logger.signals.log_message.connect(self.on_log_message)

    def on_subjects_changed(self, subjects):
        """Handle subject selection change"""
        self.statusBar().showMessage(f"{len(subjects)} subject(s) selected")

    def on_config_changed(self):
        """Handle configuration change"""
        self.config_panel.save_config()
        if self.pipeline_manager:
            # Reload config in pipeline manager
            self.pipeline_manager.config = self.config

    def on_log_message(self, message: str, level: str):
        """Handle log message"""
        # This is the global log - we can add a separate tab for it
        pass

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

        # Validate FreeSurfer path
        fs_home = self.config.get("freesurfer_home")
        if not Path(fs_home).exists():
            QMessageBox.warning(
                self,
                "Invalid FreeSurfer Path",
                f"FreeSurfer home directory not found:\n{fs_home}\n\n"
                "Please check the configuration."
            )
            return

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

        # Populate step indicator with enabled scripts
        enabled_scripts = self.pipeline_manager.get_enabled_scripts()
        step_labels = [s.name.split("_")[0] for s in enabled_scripts]
        self.progress_panel.set_steps(step_labels)

        # Set up pipeline manager
        self.pipeline_manager.set_subjects(subjects)

        # Connect pipeline signals
        self.connect_pipeline_signals()

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

    def on_pipeline_finished(self, success: bool):
        """Handle pipeline finished"""
        self.progress_panel.set_completed(success)

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

    def on_parameters_detected(self, tr: float, timepoints: int, num_runs: int):
        """Handle auto-detected parameters"""
        self.config_panel.update_detected_parameters(tr=tr, timepoints=timepoints, num_runs=num_runs)
        self.statusBar().showMessage(f"Detected: TR={tr:.2f}s, Timepoints={timepoints}, Runs={num_runs}")

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About AFNI Preprocessing GUI",
            "<h2>AFNI Preprocessing Pipeline</h2>"
            "<p>Version 1.0</p>"
            "<p>A graphical user interface for running AFNI preprocessing scripts.</p>"
            "<p>This application automates the preprocessing workflow including:</p>"
            "<ul>"
            "<li>DICOM to NIfTI conversion</li>"
            "<li>Subject defacing/refacing</li>"
            "<li>FreeSurfer reconstruction</li>"
            "<li>AFNI preprocessing</li>"
            "<li>Data format conversion</li>"
            "</ul>"
            "<p><b>Author:</b> Lukman E Ismaila Ph.D</p>"
        )

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
