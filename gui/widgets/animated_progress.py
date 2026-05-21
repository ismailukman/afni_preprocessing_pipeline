"""Animated progress bar and horizontal step indicator with glowing current step."""
from PyQt6.QtWidgets import QProgressBar, QWidget, QSizePolicy
from PyQt6.QtCore import (Qt, QTimer, QRectF, pyqtProperty, QPropertyAnimation,
                          QEasingCurve, QSize)
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen, QFont, QBrush


# ── Animated Progress Bar ──────────────────────────────────────────────────
class AnimatedProgressBar(QProgressBar):
    """QProgressBar with a moving shimmer band across the filled portion."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shimmer_pos = 0.0  # 0.0 -> 1.0, wraps
        self.setTextVisible(True)
        self.setMinimumHeight(28)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(40)  # ~25 fps

    def _advance(self):
        if self.value() <= 0 or self.value() >= self.maximum():
            # idle: keep ticking but don't waste paint when 0% or 100%
            return
        self._shimmer_pos = (self._shimmer_pos + 0.018) % 1.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        radius = 6

        # Track (background)
        p.setPen(QPen(QColor("#2d2d5e"), 1))
        p.setBrush(QColor("#0d1b2a"))
        p.drawRoundedRect(rect.adjusted(0, 0, -1, -1), radius, radius)

        # Filled portion
        if self.maximum() > 0 and self.value() > 0:
            frac = self.value() / self.maximum()
            fill_w = int(rect.width() * frac)
            fill_rect = QRectF(0, 0, fill_w, rect.height())

            # Base gradient (premium blue)
            grad = QLinearGradient(0, 0, fill_w, 0)
            grad.setColorAt(0.0, QColor("#1a5276"))
            grad.setColorAt(0.5, QColor("#2196F3"))
            grad.setColorAt(1.0, QColor("#64b5f6"))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill_rect, radius, radius)

            # Moving shimmer band
            band_w = max(60, fill_w // 4)
            band_x = (self._shimmer_pos * (fill_w + band_w)) - band_w
            band = QLinearGradient(band_x, 0, band_x + band_w, 0)
            band.setColorAt(0.0, QColor(255, 255, 255, 0))
            band.setColorAt(0.5, QColor(255, 255, 255, 90))
            band.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setClipRect(fill_rect)
            p.setBrush(QBrush(band))
            p.drawRoundedRect(fill_rect, radius, radius)
            p.setClipping(False)

        # Centered text
        p.setPen(QColor("#ffffff"))
        f = p.font()
        f.setBold(True)
        p.setFont(f)
        text = self.format().replace("%p", f"{self.value() / max(self.maximum(), 1) * 100:.1f}") \
                            .replace("%v", str(self.value())) \
                            .replace("%m", str(self.maximum()))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        p.end()


# ── Horizontal Step Indicator ──────────────────────────────────────────────
class StepIndicator(QWidget):
    """Horizontal row of step pills.  The current step pulses with a glow."""

    PILL_H = 30
    PILL_GAP = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps = []          # list of (label, full_name)
        self._current_index = -1
        self._done = set()
        self._error = set()
        self._glow = 0.0          # 0..1, animated for the active pill

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(self.PILL_H + 8)

        # Glow pulse animation
        self._anim = QPropertyAnimation(self, b"glow", self)
        self._anim.setDuration(1100)
        self._anim.setStartValue(0.15)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)

    # ── Public API ─────────────────────────────────────────────────────────
    def set_steps(self, labels):
        """labels: list of short step labels, e.g. ['001a','001c','002',...]"""
        self._steps = list(labels)
        self._current_index = -1
        self._done.clear()
        self._error.clear()
        self.update()

    def set_current(self, index: int):
        if 0 <= index < len(self._steps):
            self._current_index = index
            if self._anim.state() != QPropertyAnimation.State.Running:
                self._anim.start()
        else:
            self._current_index = -1
            self._anim.stop()
        self.update()

    def set_current_by_name(self, name: str):
        for i, lbl in enumerate(self._steps):
            if lbl == name or name.startswith(lbl):
                self.set_current(i)
                return

    def mark_done(self, index: int, success: bool = True):
        if 0 <= index < len(self._steps):
            if success:
                self._done.add(index)
                self._error.discard(index)
            else:
                self._error.add(index)
                self._done.discard(index)
            self.update()

    def mark_done_by_name(self, name: str, success: bool = True):
        for i, lbl in enumerate(self._steps):
            if lbl == name or name.startswith(lbl):
                self.mark_done(i, success)
                return

    def reset(self):
        self._current_index = -1
        self._done.clear()
        self._error.clear()
        self._anim.stop()
        self._glow = 0.0
        self.update()

    # ── Animated property ─────────────────────────────────────────────────
    def _get_glow(self):
        return self._glow

    def _set_glow(self, v):
        self._glow = float(v)
        self.update()

    glow = pyqtProperty(float, _get_glow, _set_glow)

    # ── Painting ──────────────────────────────────────────────────────────
    def paintEvent(self, event):
        if not self._steps:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        n = len(self._steps)
        gap = self.PILL_GAP
        avail = self.width() - gap * (n - 1)
        pill_w = max(60, avail // n)
        h = self.PILL_H
        y = (self.height() - h) // 2

        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        p.setFont(font)

        for i, label in enumerate(self._steps):
            x = i * (pill_w + gap)
            rect = QRectF(x, y, pill_w, h)
            self._draw_pill(p, rect, i, label)

            # Connector line between pills
            if i < n - 1:
                cx1 = x + pill_w
                cx2 = cx1 + gap
                cy = y + h / 2
                done = i in self._done
                pen = QPen(QColor("#2e7d32") if done else QColor("#2d2d5e"), 2)
                p.setPen(pen)
                p.drawLine(int(cx1), int(cy), int(cx2), int(cy))

        p.end()

    def _draw_pill(self, p: QPainter, rect: QRectF, idx: int, label: str):
        is_current = (idx == self._current_index)
        is_done = idx in self._done
        is_error = idx in self._error

        if is_error:
            fill = QColor("#b71c1c")
            border = QColor("#ef5350")
            text_color = QColor("#ffffff")
        elif is_done:
            fill = QColor("#1b5e20")
            border = QColor("#2e7d32")
            text_color = QColor("#ffffff")
        elif is_current:
            fill = QColor("#0f3460")
            border = QColor("#64b5f6")
            text_color = QColor("#ffffff")
        else:
            fill = QColor("#0d1b2a")
            border = QColor("#2d2d5e")
            text_color = QColor("#9aa5b8")

        # Glow halo for active pill
        if is_current:
            alpha = int(40 + self._glow * 150)
            halo = QColor(33, 150, 243, alpha)  # #2196F3 with pulse alpha
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            grow = 4 + self._glow * 4
            halo_rect = rect.adjusted(-grow, -grow, grow, grow)
            p.drawRoundedRect(halo_rect, halo_rect.height() / 2, halo_rect.height() / 2)

        # Pill body
        p.setPen(QPen(border, 2))
        p.setBrush(fill)
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        # Label
        p.setPen(text_color)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
