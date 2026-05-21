"""Script list widget showing pipeline steps"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
                              QLabel, QGroupBox, QProgressBar)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush


class ScriptListItem(QWidget):
    """Custom widget for script list item"""

    def __init__(self, script_name, description, estimated_time, parent=None):
        super().__init__(parent)
        self.script_name = script_name
        self.description = description
        self.estimated_time = estimated_time
        self.status = "pending"

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Title
        self.title_label = QLabel(f"{description}")
        self.title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.title_label)

        # Details
        self.details_label = QLabel(f"Estimated: {estimated_time}")
        self.details_label.setStyleSheet("font-size: 10pt; color: #666;")
        layout.addWidget(self.details_label)

        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)
        self.update_appearance()

    def set_status(self, status: str):
        """Update status (pending, running, completed, error, skipped)"""
        self.status = status
        self.update_appearance()

        if status == "running":
            self.progress_bar.show()
            self.progress_bar.setMaximum(0)  # Indeterminate
        else:
            self.progress_bar.hide()

    def update_appearance(self):
        """Update visual appearance based on status"""
        status_colors = {
            "pending": "#9e9e9e",
            "running": "#2196F3",
            "completed": "#4CAF50",
            "error": "#f44336",
            "skipped": "#FFC107"
        }

        status_icons = {
            "pending": "⏸️",
            "running": "▶️",
            "completed": "✅",
            "error": "❌",
            "skipped": "⏭️"
        }

        color = status_colors.get(self.status, "#9e9e9e")
        icon = status_icons.get(self.status, "")

        self.title_label.setText(f"{icon} {self.description}")

        # Update background color
        self.setStyleSheet(f"""
            ScriptListItem {{
                background-color: {color}22;
                border-left: 4px solid {color};
                border-radius: 4px;
            }}
        """)


class ScriptList(QWidget):
    """Widget displaying pipeline scripts"""

    script_toggled = pyqtSignal(str, bool)  # script_name, enabled

    def __init__(self, scripts, parent=None):
        super().__init__(parent)
        self.scripts = scripts
        self.script_items = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Group box
        group = QGroupBox("Pipeline Steps")
        group_layout = QVBoxLayout()

        # Script list
        self.list_widget = QListWidget()
        self.list_widget.setSpacing(2)

        for i, script in enumerate(self.scripts):
            # Create custom widget
            script_widget = ScriptListItem(
                script.name,
                f"{i+1}. {script.description}",
                script.estimated_time
            )
            self.script_items[script.name] = script_widget

            # Create list item
            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(script_widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, script_widget)

        group_layout.addWidget(self.list_widget)
        group.setLayout(group_layout)
        layout.addWidget(group)
        self.setLayout(layout)

    def update_script_status(self, subject_id: str, script_name: str, status: str):
        """Update status of a script"""
        if script_name in self.script_items:
            self.script_items[script_name].set_status(status)

    def reset_all_status(self):
        """Reset all scripts to pending"""
        for widget in self.script_items.values():
            widget.set_status("pending")

    def get_script_widget(self, script_name: str):
        """Get widget for a specific script"""
        return self.script_items.get(script_name)
