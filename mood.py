"""
mood.py — A simple "how are you feeling in this entry?" picker.

A row of emoji buttons, one of which can be selected at a time. Clicking
the already-selected one clears it (an entry doesn't have to have a mood
at all). Purely a per-entry label — there's no separate mood log, just
whatever's picked for the entry that's open.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

# (key, emoji, tooltip) — key is what actually gets stored.
MOOD_OPTIONS = [
    ("happy", "😊", "Happy"),
    ("calm", "😌", "Calm"),
    ("neutral", "😐", "Neutral"),
    ("sad", "😢", "Sad"),
    ("angry", "😠", "Angry"),
    ("anxious", "😰", "Anxious"),
    ("tired", "😴", "Tired"),
]

MOOD_EMOJI = {key: emoji for key, emoji, _label in MOOD_OPTIONS}


class MoodTrackerWidget(QWidget):
    """Emits moodChanged(mood) whenever the selection changes, where mood
    is one of the MOOD_OPTIONS keys, or None if cleared."""

    moodChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MoodTracker")
        self._mood: str | None = None
        self._buttons: dict[str, QPushButton] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(4)

        label = QLabel("Mood:")
        label.setObjectName("MoodLabel")
        layout.addWidget(label)

        for key, emoji, tooltip in MOOD_OPTIONS:
            btn = QPushButton(emoji)
            btn.setObjectName("MoodButton")
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            btn.setFixedSize(30, 30)
            btn.clicked.connect(lambda _checked, k=key: self._on_clicked(k))
            layout.addWidget(btn)
            self._buttons[key] = btn

        layout.addStretch(1)

    def _on_clicked(self, key: str):
        # Toggle off if re-clicking the current mood; otherwise select it
        # exclusively (manual, since QButtonGroup can't easily allow
        # "none selected" once something has been chosen).
        new_mood = None if self._mood == key else key
        self.set_mood(new_mood)
        self.moodChanged.emit(new_mood)

    def set_mood(self, mood: str | None):
        self._mood = mood
        for key, btn in self._buttons.items():
            btn.blockSignals(True)
            btn.setChecked(key == mood)
            btn.blockSignals(False)

    def get_mood(self) -> str | None:
        return self._mood
