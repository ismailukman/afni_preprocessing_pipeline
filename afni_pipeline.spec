# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AFNI Preprocessing Pipeline Manager."""
import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)
GUI_APP = ROOT
ICONS = GUI_APP / "resources" / "icons"


def _icon_for(*candidates):
    """Return the first existing icon path, or None if none ship in the repo."""
    for name in candidates:
        p = ICONS / name
        if p.exists():
            return str(p)
    return None


MAC_ICON = _icon_for("afni_guiapp.icns", "afni_guiapp.png")
WIN_ICON = _icon_for("afni_guiapp.ico", "afni_guiapp.png")

a = Analysis(
    [str(GUI_APP / "main.py")],
    pathex=[str(GUI_APP)],
    binaries=[],
    datas=[
        (str(GUI_APP / "resources"), "resources"),
        (str(GUI_APP / "scripts" / "templates"), "scripts/templates"),
        (str(GUI_APP / "gui" / "styles"), "gui/styles"),
    ],
    hiddenimports=[
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "scipy", "pandas"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── macOS .app bundle ──
if sys.platform == "darwin":
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="AFNI Pipeline Manager",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon=MAC_ICON,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False,
        upx=False,
        name="AFNI Pipeline Manager",
    )
    app = BUNDLE(
        coll,
        name="AFNI Pipeline Manager.app",
        icon=MAC_ICON,
        bundle_identifier="com.afnipipeline.manager",
        info_plist={
            "CFBundleDisplayName": "AFNI Pipeline Manager",
            "CFBundleShortVersionString": "2.0.3",
            "CFBundleVersion": "2.0.3",
            "NSHighResolutionCapable": True,
        },
    )

# ── Windows .exe ──
elif sys.platform == "win32":
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="AFNI Pipeline Manager",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon=WIN_ICON,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False,
        upx=False,
        name="AFNI Pipeline Manager",
    )

# ── Linux ──
else:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="AFNI Pipeline Manager",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False,
        upx=False,
        name="AFNI Pipeline Manager",
    )
