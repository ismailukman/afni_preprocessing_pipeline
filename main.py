#!/usr/bin/env python3
"""
AFNI Preprocessing Pipeline GUI
Main application entry point

Author: Lukman E Ismaila Ph.D
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap, QGuiApplication, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QTimer, QRect
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
    repo_root = Path(__file__).parent
    hero_path = repo_root / "docs" / "images" / "afni_guiapp_hero.png"
    icon_path = repo_root / "resources" / "icons" / "afni_guiapp.png"
    splash_pixmap_path = hero_path if hero_path.exists() else icon_path
    splash = None
    if splash_pixmap_path.exists():
        splash_pixmap = QPixmap(str(splash_pixmap_path))
        splash_pixmap = splash_pixmap.scaledToWidth(600, Qt.TransformationMode.SmoothTransformation)

        # Paint title / author / loading text *under* the hero image area.
        # Extend the canvas with a dark band, then draw text on it.
        band_h = 110
        canvas = QPixmap(splash_pixmap.width(), splash_pixmap.height() + band_h)
        canvas.fill(QColor("#1a1a2e"))
        p = QPainter(canvas)
        p.drawPixmap(0, 0, splash_pixmap)
        # Title + version
        try:
            from version import __version__
        except ImportError:
            __version__ = "dev"
        p.setPen(QColor("#64b5f6"))
        p.setFont(QFont("Helvetica Neue", 22, QFont.Weight.Bold))
        p.drawText(QRect(0, splash_pixmap.height() + 8, canvas.width(), 34),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   f"AFNI Pipeline Manager  ·  v{__version__}")
        # Author / lab
        p.setPen(QColor("#cfd8dc"))
        p.setFont(QFont("Helvetica Neue", 11))
        p.drawText(QRect(0, splash_pixmap.height() + 46, canvas.width(), 24),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   "The Adaptive Brain Networks Neuroimaging Lab  (ABN² Lab)")
        # Loading line
        p.setPen(QColor("#4CAF50"))
        p.setFont(QFont("Helvetica Neue", 10))
        p.drawText(QRect(0, splash_pixmap.height() + 74, canvas.width(), 22),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   "Loading …")
        p.end()

        splash = QSplashScreen(canvas, Qt.WindowType.WindowStaysOnTopHint)
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
