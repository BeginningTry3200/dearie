"""
animation.py — Opening "journal cover" animation overlay.

Simulates a cover flipping open by animating a horizontal squash
(QPropertyAnimation on geometry, easing InOutQuad) combined with an
opacity fade-out (QGraphicsOpacityEffect), then removes itself and
emits `animationFinished`.
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget

from version import APP_NAME


class CoverAnimationWidget(QWidget):
    animationFinished = Signal()

    def __init__(self, parent=None, duration_ms: int = 1200):
        super().__init__(parent)
        self.duration_ms = duration_ms
        self.setObjectName("CoverOverlay")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel(APP_NAME)
        title.setObjectName("CoverTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

        self._geo_anim = None
        self._opacity_anim = None

    def play(self):
        if not self.parent():
            self._finish()
            return
        full_rect = self.parent().rect()
        self.setGeometry(full_rect)

        # Phase 1: "cover" shrinks horizontally toward the center, as if
        # swinging open on a vertical spine — simulated via width squash.
        start_rect = QRect(full_rect)
        mid_rect = QRect(full_rect.center().x(), full_rect.y(), 0, full_rect.height())

        self._geo_anim = QPropertyAnimation(self, b"geometry")
        self._geo_anim.setDuration(int(self.duration_ms * 0.75))
        self._geo_anim.setStartValue(start_rect)
        self._geo_anim.setEndValue(mid_rect)
        self._geo_anim.setEasingCurve(QEasingCurve.InOutQuad)

        # Phase 2: fade the remainder out.
        self._opacity_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._opacity_anim.setDuration(int(self.duration_ms * 0.4))
        self._opacity_anim.setStartValue(1.0)
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)

        self._geo_anim.finished.connect(self._opacity_anim.start)
        self._opacity_anim.finished.connect(self._finish)

        self._geo_anim.start()

    def _finish(self):
        self.animationFinished.emit()
        self.setParent(None)
        self.deleteLater()
