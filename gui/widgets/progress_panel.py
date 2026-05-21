"""Progress panel widget for tracking overall progress"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QProgressBar,
                              QLabel, QPushButton, QGroupBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from datetime import datetime, timedelta

from gui.widgets.animated_progress import AnimatedProgressBar, StepIndicator


class ProgressPanel(QWidget):
    """Widget for displaying overall progress"""

    start_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    resume_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_time = None
        self.is_running = False
        self.is_paused = False
        self.elapsed_seconds = 0
        self.init_ui()

        # Timer for updating elapsed time
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_elapsed_time)

    def init_ui(self):
        layout = QVBoxLayout()

        # Group box
        group = QGroupBox("Progress")
        group_layout = QVBoxLayout()

        # Overall progress bar (animated shimmer)
        self.overall_progress = AnimatedProgressBar()
        self.overall_progress.setMaximum(100)
        self.overall_progress.setFormat("%p% (%v/%m steps)")
        group_layout.addWidget(QLabel("Overall Progress:"))
        group_layout.addWidget(self.overall_progress)

        # Current status
        self.status_label = QLabel("Ready to start")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        group_layout.addWidget(self.status_label)

        # Horizontal step indicator with active glow
        self.step_indicator = StepIndicator()
        group_layout.addWidget(self.step_indicator)

        # Time info
        time_layout = QHBoxLayout()

        self.elapsed_label = QLabel("Elapsed: --:--:--")
        time_layout.addWidget(self.elapsed_label)

        time_layout.addStretch()

        self.eta_label = QLabel("ETA: --:--:--")
        time_layout.addWidget(self.eta_label)

        group_layout.addLayout(time_layout)

        # Control buttons
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶ Start")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.start_btn.clicked.connect(self.on_start_clicked)
        button_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.on_pause_clicked)
        button_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.stop_btn.clicked.connect(self.on_stop_clicked)
        button_layout.addWidget(self.stop_btn)

        group_layout.addLayout(button_layout)

        group.setLayout(group_layout)
        layout.addWidget(group)
        self.setLayout(layout)

    def on_start_clicked(self):
        """Handle start button click"""
        self.start_clicked.emit()
        self.set_running(True)

    def on_pause_clicked(self):
        """Handle pause button click"""
        if not self.is_paused:
            self.pause_clicked.emit()
            self.set_paused(True)
        else:
            self.resume_clicked.emit()
            self.set_paused(False)

    def on_stop_clicked(self):
        """Handle stop button click"""
        self.stop_clicked.emit()
        self.set_running(False)

    def set_running(self, running: bool):
        """Update running state"""
        self.is_running = running

        if running:
            self.start_time = datetime.now()
            self.elapsed_seconds = 0
            self.timer.start(1000)  # Update every second
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
        else:
            self.timer.stop()
            self.start_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.is_paused = False
            self.pause_btn.setText("⏸ Pause")

    def set_paused(self, paused: bool):
        """Update paused state"""
        self.is_paused = paused

        if paused:
            self.timer.stop()
            self.pause_btn.setText("▶ Resume")
            self.status_label.setText("⏸ Paused")
        else:
            self.timer.start(1000)
            self.pause_btn.setText("⏸ Pause")

    def update_progress(self, current: int, total: int):
        """Update progress bar"""
        self.overall_progress.setMaximum(total)
        self.overall_progress.setValue(current)

        if total > 0:
            percentage = (current / total) * 100
            self.overall_progress.setFormat(f"{percentage:.1f}% ({current}/{total} steps)")

            # Calculate ETA
            if current > 0 and self.elapsed_seconds > 0:
                avg_time_per_step = self.elapsed_seconds / current
                remaining_steps = total - current
                eta_seconds = int(avg_time_per_step * remaining_steps)
                eta = timedelta(seconds=eta_seconds)
                self.eta_label.setText(f"ETA: {str(eta)}")
            else:
                self.eta_label.setText("ETA: Calculating...")
        else:
            self.eta_label.setText("ETA: --:--:--")

    def update_status(self, subject_id: str, script_name: str):
        """Update current status display"""
        self.status_label.setText(f"Processing: {subject_id} → {script_name}")

    def update_elapsed_time(self):
        """Update elapsed time display"""
        if self.start_time and not self.is_paused:
            self.elapsed_seconds = int((datetime.now() - self.start_time).total_seconds())
            elapsed = timedelta(seconds=self.elapsed_seconds)
            self.elapsed_label.setText(f"Elapsed: {str(elapsed)}")

    def reset(self):
        """Reset progress panel"""
        self.overall_progress.setValue(0)
        self.status_label.setText("Ready to start")
        self.elapsed_label.setText("Elapsed: --:--:--")
        self.eta_label.setText("ETA: --:--:--")
        self.start_time = None
        self.elapsed_seconds = 0
        self.step_indicator.reset()
        self.set_running(False)

    def set_steps(self, labels):
        """Populate the horizontal step indicator with step labels."""
        self.step_indicator.set_steps(labels)

    def set_current_step(self, name: str):
        """Highlight the active step by name in the step indicator."""
        self.step_indicator.set_current_by_name(name)

    def mark_step_done(self, name: str, success: bool = True):
        """Mark a step as completed (green) or errored (red)."""
        self.step_indicator.mark_done_by_name(name, success)

    def set_completed(self, success: bool):
        """Set completion state"""
        self.set_running(False)
        if success:
            self.status_label.setText("✅ Pipeline completed successfully!")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 12pt; color: #4CAF50;")
        else:
            self.status_label.setText("❌ Pipeline finished with errors")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 12pt; color: #f44336;")
