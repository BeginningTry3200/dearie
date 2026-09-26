"""
animation.py — Opening "journal cover" animation overlay.

Two pink cover panels sit over the main window like a closed book. After
a brief beat, they swing open — the left panel slides off to the left,
the right panel slides off to the right — revealing the real interface
underneath, then the whole overlay fades and removes itself, emitting
`animationFinished`.
"""

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget

from version import APP_NAME


class CoverAnimationWidget(QWidget):
    animationFinished = Signal()

    def __init__(self, parent=None, duration_ms: int = 1200):
        super().__init__(parent)
        self.duration_ms = duration_ms
        self.setObjectName("CoverOverlay")

        # --- The two cover halves, like a book lying closed. ---------------
        self.left_panel = QWidget(self)
        self.left_panel.setObjectName("CoverPanelLeft")

        self.right_panel = QWidget(self)
        self.right_panel.setObjectName("CoverPanelRight")

        # --- Title, centered across the seam, on top of both panels. -------
        self.title_label = QLabel(APP_NAME, self)
        self.title_label.setObjectName("CoverTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title_opacity = QGraphicsOpacityEffect(self.title_label)
        self.title_label.setGraphicsEffect(self._title_opacity)
        self._title_opacity.setOpacity(1.0)

        self._overlay_opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._overlay_opacity)
        self._overlay_opacity.setOpacity(1.0)

        self._anims = []

    def play(self):
        if not self.parent():
            self._finish()
            return
        full_rect = self.parent().rect()
        self.setGeometry(full_rect)

        width = full_rect.width()
        height = full_rect.height()
        half_w = width // 2

        left_closed = QRect(0, 0, half_w, height)
        right_closed = QRect(half_w, 0, width - half_w, height)
        left_open = QRect(-half_w, 0, half_w, height)
        right_open = QRect(width, 0, width - half_w, height)

        self.left_panel.setGeometry(left_closed)
        self.right_panel.setGeometry(right_closed)
        self.left_panel.show()
        self.right_panel.show()

        self.title_label.setGeometry(full_rect)
        self._title_opacity.setOpacity(1.0)
        self._overlay_opacity.setOpacity(1.0)

        hold_ms = int(self.duration_ms * 0.2)
        open_ms = int(self.duration_ms * 0.55)
        fade_ms = int(self.duration_ms * 0.35)

        # Phase 1: title fades slightly ahead of the panels opening, so it
        # doesn't look like it's being torn in half at the seam.
        title_fade = QPropertyAnimation(self._title_opacity, b"opacity")
        title_fade.setDuration(open_ms)
        title_fade.setStartValue(1.0)
        title_fade.setEndValue(0.0)
        title_fade.setEasingCurve(QEasingCurve.Type.InQuad)

        # Phase 2: the two covers swing open like a book, sliding fully
        # off-screen on either side.
        left_anim = QPropertyAnimation(self.left_panel, b"geometry")
        left_anim.setDuration(open_ms)
        left_anim.setStartValue(left_closed)
        left_anim.setEndValue(left_open)
        left_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        right_anim = QPropertyAnimation(self.right_panel, b"geometry")
        right_anim.setDuration(open_ms)
        right_anim.setStartValue(right_closed)
        right_anim.setEndValue(right_open)
        right_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        open_group = QParallelAnimationGroup(self)
        open_group.addAnimation(title_fade)
        open_group.addAnimation(left_anim)
        open_group.addAnimation(right_anim)

        # Phase 3: fade the whole (now-empty) overlay out and remove it, so
        # nothing lingers even if the panels ended up slightly off-geometry.
        overlay_fade = QPropertyAnimation(self._overlay_opacity, b"opacity")
        overlay_fade.setDuration(fade_ms)
        overlay_fade.setStartValue(1.0)
        overlay_fade.setEndValue(0.0)
        overlay_fade.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._anims = [title_fade, left_anim, right_anim, open_group, overlay_fade]

        overlay_fade.finished.connect(self._finish)
        open_group.finished.connect(overlay_fade.start)

        # Hold the closed cover on screen briefly before it opens, so the
        # title has a beat to register before things start moving.
        QTimer.singleShot(hold_ms, open_group.start)

    def _finish(self):
        self.animationFinished.emit()
        self.setParent(None)
        self.deleteLater()
