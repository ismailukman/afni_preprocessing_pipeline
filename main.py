#!/usr/bin/env python3
"""
AFNI Preprocessing Pipeline GUI
Main application entry point

Author: Lukman E Ismaila Ph.D
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap, QGuiApplication
from PyQt6.QtCore import Qt, QTimer
from gui.main_window import MainWindow

STYLES_DIR = Path(__file__).parent / "gui" / "styles"


def _is_dark_mode() -> bool:
    palette = QGuiApplication.palette()
    return palette.window().color().lightness() < 128


def _load_stylesheet(app: QApplication) -> None:
    theme = "dark" if _is_dark_mode() else "light"
    qss_path = STYLES_DIR / f"stylesheet_{theme}.qss"
    fallback = STYLES_DIR / "stylesheet.qss"
    path = qss_path if qss_path.exists() else fallback
    if path.exists():
        app.setStyleSheet(path.read_text())


def main():
    app = QApplication(sys.argv)

    app.setApplicationName("AFNI Preprocessing Pipeline")
    app.setOrganizationName("AFNI Preprocessing")
    app.setOrganizationDomain("afni.nimh.nih.gov")

    _load_stylesheet(app)

    # Re-apply theme when the user toggles OS dark/light mode
    try:
        app.styleHints().colorSchemeChanged.connect(lambda _: _load_stylesheet(app))
    except AttributeError:
        pass  # colorSchemeChanged not available on older Qt versions

    # Show splash screen
    splash_pixmap_path = Path(__file__).parent / "resources" / "icons" / "afni_guiapp.png"
    splash = None
    if splash_pixmap_path.exists():
        splash_pixmap = QPixmap(str(splash_pixmap_path))
        splash_pixmap = splash_pixmap.scaledToWidth(600, Qt.TransformationMode.SmoothTransformation)
        splash = QSplashScreen(splash_pixmap, Qt.WindowType.WindowStaysOnTopHint)
        splash.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        splash.show()
        app.processEvents()

    window = MainWindow()

    if splash:
        QTimer.singleShot(2000, lambda: (splash.finish(window), window.show()))
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
