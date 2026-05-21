"""Log viewer widget for displaying real-time output"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                              QTabWidget, QPushButton, QLineEdit, QLabel,
                              QGroupBox, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat, QFont


class LogTab(QWidget):
    """Individual log tab for a subject"""

    def __init__(self, subject_id, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.auto_scroll = True
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Text display
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Courier New", 10))
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.text_edit)

        # Control bar
        control_layout = QHBoxLayout()

        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.stateChanged.connect(self.toggle_auto_scroll)
        control_layout.addWidget(self.auto_scroll_check)

        control_layout.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_log)
        control_layout.addWidget(clear_btn)

        export_btn = QPushButton("Export...")
        export_btn.clicked.connect(self.export_log)
        control_layout.addWidget(export_btn)

        layout.addLayout(control_layout)
        self.setLayout(layout)

    def append_line(self, line: str, level: str = "INFO"):
        """Append a line to the log"""
        # Color based on level or content
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        format = QTextCharFormat()

        # Set color based on content
        line_lower = line.lower()
        if "error" in line_lower or "✗" in line or level == "ERROR":
            format.setForeground(QColor("#f44336"))  # Red
        elif "warning" in line_lower or "⚠" in line or level == "WARNING":
            format.setForeground(QColor("#FF9800"))  # Orange
        elif "✓" in line or "success" in line_lower:
            format.setForeground(QColor("#4CAF50"))  # Green
        elif "====" in line or "----" in line:
            format.setForeground(QColor("#2196F3"))  # Blue
            format.setFontWeight(QFont.Weight.Bold)
        else:
            format.setForeground(QColor("#212121"))  # Default

        cursor.setCharFormat(format)
        cursor.insertText(line + "\n")

        # Auto-scroll if enabled
        if self.auto_scroll:
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()

    def toggle_auto_scroll(self, state):
        """Toggle auto-scroll"""
        self.auto_scroll = state == Qt.CheckState.Checked.value

    def clear_log(self):
        """Clear the log"""
        self.text_edit.clear()

    def export_log(self):
        """Export log to file"""
        from PyQt6.QtWidgets import QFileDialog
        from pathlib import Path

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Log",
            str(Path.home() / f"log_{self.subject_id}.txt"),
            "Text Files (*.txt);;All Files (*)"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.text_edit.toPlainText())
            except Exception as e:
                print(f"Error exporting log: {e}")

    def get_text(self):
        """Get all log text"""
        return self.text_edit.toPlainText()


class LogViewer(QWidget):
    """Widget for viewing logs with tabs for each subject"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_tabs = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Group box
        group = QGroupBox("Log Output")
        group_layout = QVBoxLayout()

        # Tab widget
        self.tab_widget = QTabWidget()
        group_layout.addWidget(self.tab_widget)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter text to search...")
        self.search_input.returnPressed.connect(self.search_logs)
        search_layout.addWidget(self.search_input)

        search_btn = QPushButton("Find")
        search_btn.clicked.connect(self.search_logs)
        search_layout.addWidget(search_btn)

        group_layout.addLayout(search_layout)

        group.setLayout(group_layout)
        layout.addWidget(group)
        self.setLayout(layout)

    def add_subject_tab(self, subject_id: str):
        """Add a new tab for a subject"""
        if subject_id not in self.log_tabs:
            log_tab = LogTab(subject_id)
            self.log_tabs[subject_id] = log_tab
            self.tab_widget.addTab(log_tab, subject_id)

    def append_log(self, subject_id: str, line: str, level: str = "INFO"):
        """Append a log line to a subject's tab"""
        if subject_id not in self.log_tabs:
            self.add_subject_tab(subject_id)

        self.log_tabs[subject_id].append_line(line, level)

        # Switch to the active tab
        index = self.tab_widget.indexOf(self.log_tabs[subject_id])
        if index >= 0:
            self.tab_widget.setCurrentIndex(index)

    def clear_all_logs(self):
        """Clear all logs"""
        for log_tab in self.log_tabs.values():
            log_tab.clear_log()

    def remove_subject_tab(self, subject_id: str):
        """Remove a subject's tab"""
        if subject_id in self.log_tabs:
            index = self.tab_widget.indexOf(self.log_tabs[subject_id])
            if index >= 0:
                self.tab_widget.removeTab(index)
            del self.log_tabs[subject_id]

    def search_logs(self):
        """Search current log tab"""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, LogTab):
            search_text = self.search_input.text()
            if search_text:
                current_tab.text_edit.find(search_text)

    def get_current_subject_id(self):
        """Get currently visible subject ID"""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, LogTab):
            return current_tab.subject_id
        return None
