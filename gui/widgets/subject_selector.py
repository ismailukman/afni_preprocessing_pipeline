"""Subject selector widget for choosing subjects to process"""
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QListWidget, QListWidgetItem, QLabel, QFileDialog,
                              QGroupBox, QCheckBox, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal
from core.pipeline_manager import Subject


class SubjectSelector(QWidget):
    """Widget for selecting subjects to process"""

    subjects_changed = pyqtSignal(list)            # all currently checked subjects
    apply_additions_clicked = pyqtSignal(list)     # only the *new* subjects to append

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dir = None
        self.selected_subjects = []
        self._applied_ids = set()   # subject_ids already pushed into the running pipeline
        self._pipeline_running = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Group box
        group = QGroupBox("Subject Selection")
        group_layout = QVBoxLayout()

        # Browse button
        browse_layout = QHBoxLayout()
        self.path_label = QLabel("No directory selected")
        self.path_label.setWordWrap(True)
        browse_btn = QPushButton("Browse Parent Directory...")
        browse_btn.clicked.connect(self.browse_directory)
        browse_layout.addWidget(self.path_label, 1)
        browse_layout.addWidget(browse_btn)
        group_layout.addLayout(browse_layout)
        
        # Detection mode checkbox
        self.all_subdirs_check = QCheckBox("Assume all subdirectories are subjects")
        self.all_subdirs_check.setToolTip(
            "If checked, all non-hidden subdirectories in the parent folder will be listed as subjects.\n"
            "Use this if automatic detection fails."
        )
        self.all_subdirs_check.stateChanged.connect(self.scan_for_subjects)
        group_layout.addWidget(self.all_subdirs_check)

        # Subject list
        self.subject_list = QListWidget()
        self.subject_list.itemChanged.connect(self.on_selection_changed)
        group_layout.addWidget(QLabel("Available Subjects:"))
        group_layout.addWidget(self.subject_list)

        # Selection buttons
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        deselect_all_btn = QPushButton("Deselect All")
        select_all_btn.clicked.connect(self.select_all)
        deselect_all_btn.clicked.connect(self.deselect_all)
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_all_btn)
        group_layout.addLayout(btn_layout)

        # Count label
        self.count_label = QLabel("0 subjects selected")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        group_layout.addWidget(self.count_label)

        # Apply additions button (only useful while pipeline is running)
        self.apply_btn = QPushButton("➕ Apply Additions")
        self.apply_btn.setToolTip(
            "Add newly selected subjects to the running pipeline.\n"
            "Active only while a pipeline is in progress."
        )
        self.apply_btn.setEnabled(False)
        self.apply_btn.setVisible(False)
        self.apply_btn.clicked.connect(self._emit_additions)
        group_layout.addWidget(self.apply_btn)

        group.setLayout(group_layout)
        layout.addWidget(group)
        self.setLayout(layout)

        # Set size policy
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    def browse_directory(self):
        """Open directory browser"""
        # Use last directory if available
        start_dir = str(self.parent_dir) if self.parent_dir else str(Path.home())

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Parent Directory Containing Subject Folders",
            start_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if directory:
            self.parent_dir = Path(directory)
            self.path_label.setText(str(self.parent_dir))
            self.scan_for_subjects()

    def scan_for_subjects(self):
        """Scan directory for subject folders"""
        if not self.parent_dir:
            return

        self.subject_list.clear()
        subject_folders = []

        # Look for folders that might be subject folders
        for item in self.parent_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it looks like a subject folder
                if self.is_subject_folder(item):
                    subject_folders.append(item)

        # Sort alphabetically
        subject_folders.sort(key=lambda x: x.name)

        # Add to list
        for folder in subject_folders:
            item = QListWidgetItem(folder.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, str(folder))
            self.subject_list.addItem(item)

        self.update_count()

    def is_subject_folder(self, folder: Path) -> bool:
        """Check if folder appears to be a subject folder"""
        # If relaxed mode is on, just accept any non-hidden directory
        if self.all_subdirs_check.isChecked():
            return not folder.name.startswith('.')

        try:
            # Check for common indicators (stricter logic)
            # 1. Contains PreprocessedData folder
            if (folder / "PreprocessedData").exists():
                return True

            # 2. Contains DICOM files (limit check)
            file_count = 0
            for file in folder.iterdir():
                if file.is_file() and file.suffix.lower() in ['.dcm', '.ima', '.rec']:
                    return True
                file_count += 1
                if file_count > 100: break

            # 3. Contains subdirectories like anat/func or with DICOMs
            subdir_count = 0
            for subdir in folder.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('.'):
                    if subdir.name in ['anat', 'func', 'dwi', 'fmap']:
                        return True
                    try:
                        subfile_count = 0
                        for file in subdir.iterdir():
                            if file.is_file() and file.suffix.lower() in ['.dcm', '.ima', '.rec']:
                                return True
                            subfile_count += 1
                            if subfile_count > 50: break
                    except (PermissionError, OSError):
                        continue
                subdir_count += 1
                if subdir_count > 20: break

            # 4. Folder name looks like a BIDS subject ID
            name = folder.name.lower()
            if name.startswith('sub-') or name.startswith('subj') or name.startswith('participant'):
                return True

        except (PermissionError, OSError) as e:
            print(f"Warning: Cannot access folder {folder}: {e}")
            return False

        return False

    def select_all(self):
        """Select all subjects"""
        for i in range(self.subject_list.count()):
            item = self.subject_list.item(i)
            item.setCheckState(Qt.CheckState.Checked)

    def deselect_all(self):
        """Deselect all subjects"""
        for i in range(self.subject_list.count()):
            item = self.subject_list.item(i)
            item.setCheckState(Qt.CheckState.Unchecked)

    def on_selection_changed(self):
        """Handle selection change"""
        self.update_count()
        self.update_selected_subjects()

    def update_count(self):
        """Update the count label"""
        count = sum(1 for i in range(self.subject_list.count())
                   if self.subject_list.item(i).checkState() == Qt.CheckState.Checked)
        total = self.subject_list.count()
        self.count_label.setText(f"{count} of {total} subjects selected")

    def update_selected_subjects(self):
        """Update the list of selected subjects"""
        self.selected_subjects = []
        for i in range(self.subject_list.count()):
            item = self.subject_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                folder_path = Path(item.data(Qt.ItemDataRole.UserRole))
                subject = Subject(folder_path, item.text())
                self.selected_subjects.append(subject)

        self.subjects_changed.emit(self.selected_subjects)
        self._refresh_apply_button()

    # ── Apply-additions support ────────────────────────────────────────────
    def set_pipeline_running(self, running: bool):
        """Show/hide the Apply button based on pipeline state."""
        self._pipeline_running = running
        self.apply_btn.setVisible(running)
        if not running:
            self._applied_ids.clear()
        self._refresh_apply_button()

    def mark_applied(self, subjects):
        """Record subjects as already pushed into the running pipeline."""
        for s in subjects:
            self._applied_ids.add(s.subject_id)
        self._refresh_apply_button()

    def _pending_additions(self):
        return [s for s in self.selected_subjects if s.subject_id not in self._applied_ids]

    def _refresh_apply_button(self):
        if not self._pipeline_running:
            self.apply_btn.setEnabled(False)
            return
        pending = self._pending_additions()
        self.apply_btn.setEnabled(bool(pending))
        if pending:
            self.apply_btn.setText(f"➕ Apply Additions ({len(pending)})")
        else:
            self.apply_btn.setText("➕ Apply Additions")

    def _emit_additions(self):
        pending = self._pending_additions()
        if pending:
            self.apply_additions_clicked.emit(pending)

    def get_selected_subjects(self):
        """Get list of selected subjects"""
        return self.selected_subjects

    def set_parent_directory(self, directory: str):
        """Set parent directory programmatically"""
        self.parent_dir = Path(directory)
        self.path_label.setText(str(self.parent_dir))
        self.scan_for_subjects()
