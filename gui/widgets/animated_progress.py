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
    """Horizontal row of small numbered circles.

    Each step is rendered as a circle showing its **number** (1, 2, 3, …).
    The currently-active step pulses with a soft glow halo; done steps are
    green, errored steps red, pending steps dim.

    ``set_steps`` accepts a list of dicts ``{"label": "1", "key": "001a_..."}``
    so the *display label* (a number) is decoupled from the *match key* used
    by ``set_current_by_name`` / ``mark_done_by_name``.
    """

    CIRCLE_D = 28      # circle diameter in px
    CIRCLE_GAP = 10    # spacing between circles

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps = []          # list of dicts: {"label", "key"}
        self._current_index = -1
        self._done = set()
        self._error = set()
        self._glow = 0.0          # 0..1, animated for the active circle

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Extra room above/below for the glow halo
        self.setMinimumHeight(self.CIRCLE_D + 16)

        self._anim = QPropertyAnimation(self, b"glow", self)
        self._anim.setDuration(1100)
        self._anim.setStartValue(0.15)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)

    # ── Public API ─────────────────────────────────────────────────────────
    def set_steps(self, steps):
        """Set the steps to display.

        Accepts either:
          - list of dicts: ``[{"label": "1", "key": "001a_dcm2niix"}, ...]``
          - list of strings (each used as both label and key)
        """
        normalized = []
        for s in steps:
            if isinstance(s, dict):
                normalized.append({"label": str(s.get("label", "?")),
                                   "key":   str(s.get("key", s.get("label", "?")))})
            else:
                normalized.append({"label": str(s), "key": str(s)})
        self._steps = normalized
        self._current_index = -1
        self._done.clear()
        self._error.clear()
        self.update()

    def _match_index(self, name: str) -> int:
        for i, s in enumerate(self._steps):
            if s["key"] == name or name.startswith(s["key"]):
                return i
        return -1

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
        idx = self._match_index(name)
        if idx >= 0:
            self.set_current(idx)

    def mark_done(self, index: int, success: bool = True):
        if 0 <= index < len(self._steps):
            if success:
                self._done.add(index); self._error.discard(index)
            else:
                self._error.add(index); self._done.discard(index)
            self.update()

    def mark_done_by_name(self, name: str, success: bool = True):
        idx = self._match_index(name)
        if idx >= 0:
            self.mark_done(idx, success)

    def reset(self):
        self._current_index = -1
        self._done.clear()
        self._error.clear()
        self._anim.stop()
        self._glow = 0.0
        self.update()

    def freeze(self):
        """Stop the pulsing glow on the active step without changing state.

        Used when the pipeline is stopped/finished: the circle keeps its
        current/done/error colour but the halo no longer pulses.
        """
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
        d = self.CIRCLE_D
        gap = self.CIRCLE_GAP
        total_w = n * d + (n - 1) * gap
        # Center the row horizontally
        x0 = max((self.width() - total_w) // 2, 0)
        cy = self.height() // 2

        # Big bold number font (scaled to circle diameter)
        font = QFont()
        font.setBold(True)
        font.setPointSize(13)
        p.setFont(font)

        for i, step in enumerate(self._steps):
            cx = x0 + i * (d + gap) + d // 2

            # Connector line to previous circle
            if i > 0:
                prev_done = (i - 1) in self._done
                pen = QPen(QColor("#2e7d32") if prev_done else QColor("#2d2d5e"), 2)
                p.setPen(pen)
                p.drawLine(int(cx - d // 2 - gap), cy, int(cx - d // 2), cy)

            self._draw_circle(p, cx, cy, d, i, step["label"])

        p.end()

    def _draw_circle(self, p: QPainter, cx: int, cy: int, d: int, idx: int, label: str):
        is_current = (idx == self._current_index)
        is_done = idx in self._done
        is_error = idx in self._error

        if is_error:
            fill, border, text_color = QColor("#b71c1c"), QColor("#ef5350"), QColor("#ffffff")
        elif is_done:
            fill, border, text_color = QColor("#1b5e20"), QColor("#2e7d32"), QColor("#ffffff")
        elif is_current:
            fill, border, text_color = QColor("#0f3460"), QColor("#64b5f6"), QColor("#ffffff")
        else:
            fill, border, text_color = QColor("#0d1b2a"), QColor("#2d2d5e"), QColor("#9aa5b8")

        # Pulsing glow halo for the active circle
        if is_current:
            alpha = int(40 + self._glow * 160)
            halo = QColor(33, 150, 243, alpha)  # #2196F3 with pulse alpha
            grow = int(4 + self._glow * 6)
            halo_d = d + grow * 2
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QRectF(cx - halo_d / 2, cy - halo_d / 2, halo_d, halo_d))

        # Circle body
        p.setPen(QPen(border, 2))
        p.setBrush(fill)
        p.drawEllipse(QRectF(cx - d / 2, cy - d / 2, d, d))

        # Number / label
        p.setPen(text_color)
        p.drawText(QRectF(cx - d / 2, cy - d / 2, d, d),
                   Qt.AlignmentFlag.AlignCenter, label)
