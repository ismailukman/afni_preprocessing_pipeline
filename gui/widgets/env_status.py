"""Environment status widget — shows whether each required tool is available."""
import shutil
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QGroupBox, QPushButton, QSizePolicy)


def _has_any(*names):
    """Return the first command from *names* found on PATH, or None."""
    for n in names:
        path = shutil.which(n)
        if path:
            return path
    return None


class EnvironmentStatus(QWidget):
    """Compact panel listing required external tools with ✓ / ✗ indicators.

    A "Re-check" button reruns the check on demand.  The widget reads its
    FreeSurfer home from the ConfigManager passed in, so it stays in sync
    with whatever the user configured.
    """

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self._rows = {}     # name -> (chip QLabel, detail QLabel)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._init_ui()
        self.refresh()

    # ── UI ─────────────────────────────────────────────────────────────────
    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 0)

        group = QGroupBox("Environment Check")
        v = QVBoxLayout(group)
        v.setSpacing(4)

        for tool in ("AFNI", "FreeSurfer", "dcm2niix", "tcsh"):
            row = QHBoxLayout()
            chip = QLabel("…")
            chip.setFixedWidth(20)
            chip.setStyleSheet("font-weight: bold; font-size: 11pt;")
            row.addWidget(chip)
            label = QLabel(tool)
            label.setMinimumWidth(80)
            label.setStyleSheet("font-weight: bold;")
            row.addWidget(label)
            detail = QLabel("checking…")
            detail.setStyleSheet("color: #888; font-size: 9pt;")
            detail.setWordWrap(True)
            row.addWidget(detail, 1)
            v.addLayout(row)
            self._rows[tool] = (chip, detail)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.refresh_btn = QPushButton("🔄 Re-check")
        self.refresh_btn.setToolTip("Re-run the environment check now")
        self.refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self.refresh_btn)
        v.addLayout(btn_row)

        outer.addWidget(group)

    # ── Public API ────────────────────────────────────────────────────────
    def refresh(self):
        """Re-scan PATH and the FreeSurfer config; update the displayed state."""
        # AFNI — look for a few well-known binaries
        afni = _has_any("3dinfo", "afni", "afni_proc.py")
        self._set("AFNI", bool(afni), afni or "not found on PATH")

        # FreeSurfer — check bin/recon-all under FREESURFER_HOME (config)
        fs_home = ""
        if self.config is not None:
            fs_home = self.config.get("freesurfer_home", "") or ""
        fs_recon = Path(fs_home) / "bin" / "recon-all" if fs_home else None
        fs_ok = bool(fs_recon and fs_recon.exists())
        if fs_ok:
            self._set("FreeSurfer", True, str(fs_recon))
        else:
            # fall back to PATH lookup
            fs_path = _has_any("recon-all")
            if fs_path:
                self._set("FreeSurfer", True, fs_path)
            else:
                hint = (f"recon-all not at {fs_recon}" if fs_home
                        else "FREESURFER_HOME not set in Configuration")
                self._set("FreeSurfer", False, hint)

        # dcm2niix (any variant)
        dcm = _has_any("dcm2niix_afni", "dcm2niix_main", "dcm2niix")
        self._set("dcm2niix", bool(dcm), dcm or "not found on PATH")

        # tcsh
        tcsh = _has_any("tcsh")
        self._set("tcsh", bool(tcsh), tcsh or "not found on PATH")

    def all_ok(self) -> bool:
        return all(chip.text() == "✓" for chip, _ in self._rows.values())

    # ── Helpers ───────────────────────────────────────────────────────────
    def _set(self, tool: str, ok: bool, detail: str):
        chip, det = self._rows[tool]
        chip.setText("✓" if ok else "✗")
        chip.setStyleSheet(
            "font-weight: bold; font-size: 13pt; "
            + ("color: #4CAF50;" if ok else "color: #ef5350;")
        )
        det.setText(detail)
        det.setStyleSheet(
            "font-size: 9pt; "
            + ("color: #c0c0c0;" if ok else "color: #ef5350; font-style: italic;")
        )
