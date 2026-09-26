"""
theming.py — Skeuomorphic dressing for Dearie: a painted wood-table
backdrop, a "journal cover" card with a drop shadow (so it reads as an
object sitting on the table rather than a flat panel), and a ribbon
bookmark that pokes out of the top of the cover.

Everything here is drawn procedurally with QPainter rather than loaded
from image assets, so there's nothing to ship or path-resolve — it looks
right regardless of where the app is run from or how the window is sized.
"""

import math
import random

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QFrame, QWidget

# NOTE: shadows here are hand-painted (many translucent layered rounded
# rects, cheapest fake-blur there is) rather than done with
# QGraphicsDropShadowEffect. The effect-based shadow turned out not to
# render reliably in every environment (it silently produced nothing under
# the offscreen/headless platform used for testing, and effect rendering
# in general depends on the platform's compositor), so painting it
# ourselves guarantees it always shows up.


def paint_layered_shadow(
    painter,
    rect,
    corner_radius=22,
    layers=16,
    max_extra=30,
    y_offset=14,
    base_alpha=13,
    color=QColor(35, 15, 12),
):
    """Draws a soft rounded-rect shadow behind `rect` by stacking many
    slightly larger, increasingly transparent rounded rectangles — a cheap
    but effective stand-in for a real gaussian blur."""
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    for i in range(layers, 0, -1):
        t = i / layers
        extra = max_extra * t
        shadow_rect = QRectF(
            rect.x() - extra,
            rect.y() - extra + y_offset,
            rect.width() + 2 * extra,
            rect.height() + 2 * extra,
        )
        path = QPainterPath()
        path.addRoundedRect(shadow_rect, corner_radius + extra * 0.5, corner_radius + extra * 0.5)
        c = QColor(color)
        c.setAlpha(base_alpha)
        painter.fillPath(path, c)
    painter.restore()


class TableBackgroundWidget(QWidget):
    """Fills itself with a painted wood-desk texture: a warm brown
    gradient, subtle vertical grain streaks, and a soft vignette so the
    center (where the journal sits) reads slightly brighter than the
    corners."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rng = random.Random(7)  # fixed seed: grain doesn't jitter on resize
        self._card_rect = None
        self._card_radius = 22

    def set_card_rect(self, rect, radius=22):
        """Called by the window whenever the journal-cover card is
        (re)positioned, so we know where to paint its shadow."""
        self._card_rect = rect
        self._card_radius = radius
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        base = QLinearGradient(0, 0, rect.width(), rect.height())
        base.setColorAt(0.0, QColor("#96683F"))
        base.setColorAt(0.45, QColor("#7A4A30"))
        base.setColorAt(1.0, QColor("#5E3620"))
        painter.fillRect(rect, base)

        # Wood grain: thin, slightly wobbly vertical streaks.
        painter.setOpacity(0.10)
        x = 0
        step = 7
        while x < rect.width():
            wobble = int(5 * math.sin(x * 0.03))
            shade = self._rng.choice(
                [QColor(0, 0, 0, 70), QColor(255, 235, 210, 35)]
            )
            painter.setPen(QPen(shade, 1))
            painter.drawLine(x + wobble, 0, x + wobble, rect.height())
            x += step
        painter.setOpacity(1.0)

        # Vignette so the edges of the window recede a little.
        vignette = QRadialGradient(
            rect.center(), max(rect.width(), rect.height()) * 0.75
        )
        vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 95))
        painter.fillRect(rect, vignette)

        # Shadow the journal cover casts onto the table, so it reads as an
        # object resting on the surface rather than a flat panel.
        if self._card_rect is not None:
            paint_layered_shadow(
                painter, QRectF(self._card_rect), corner_radius=self._card_radius
            )
        painter.end()


class JournalCard(QFrame):
    """The pink 'cover' of the journal — a rounded card with a leather-
    style gradient (styled via QSS, object name JournalCard) that floats
    above the TableBackgroundWidget with a drop shadow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("JournalCard")


class RibbonBookmark(QWidget):
    """A small ribbon tab that appears to hang out of the top of the
    journal cover, drawn as a rectangle with a triangular notch cut into
    the bottom edge."""

    def __init__(self, parent=None, color="#C1577A"):
        super().__init__(parent)
        self._color = QColor(color)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def _ribbon_path(self, w, h):
        notch = min(16, h * 0.25)
        path = QPainterPath()
        path.moveTo(0, 0)
        path.lineTo(w, 0)
        path.lineTo(w, h - notch)
        path.lineTo(w / 2, h)
        path.lineTo(0, h - notch)
        path.closeSubpath()
        return path, notch

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path, notch = self._ribbon_path(w, h)

        # Soft hand-painted shadow, offset slightly down/right.
        painter.setPen(Qt.PenStyle.NoPen)
        for i, alpha in enumerate((10, 16, 24)):
            offset = 3 - i
            shifted = QPainterPath(path)
            shifted.translate(offset, offset + 2)
            painter.fillPath(shifted, QColor(20, 10, 10, alpha))

        painter.fillPath(path, self._color)
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.drawLine(int(w * 0.32), 5, int(w * 0.32), int(h - notch - 4))
        painter.end()
