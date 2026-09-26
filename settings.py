"""
settings.py — Dearie's user-configurable settings: a small dataclass
persisted to a local JSON file (not the encrypted vault, since none of
this is sensitive — it's app preferences, not journal content), plus the
dialog used to edit them.
"""

import json
import os
from dataclasses import asdict, dataclass, fields

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

SETTINGS_FILENAME = "dearie_settings.json"


@dataclass
class AppSettings:
    autosave_delay_ms: int = 1000
    show_opening_animation: bool = True
    editor_default_font_size: int = 13

    @classmethod
    def load(cls, path: str) -> "AppSettings":
        defaults = cls()
        if not os.path.exists(path):
            return defaults
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            return defaults

        valid_keys = {f.name for f in fields(cls)}
        cleaned = {k: v for k, v in raw.items() if k in valid_keys}
        try:
            return cls(**{**asdict(defaults), **cleaned})
        except TypeError:
            return defaults

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)


class SettingsDialog(QDialog):
    """Edits an AppSettings instance. On accept, the validated result is
    available as `self.result_settings`; the original passed in is never
    mutated in place."""

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self._original = settings
        self.result_settings = None

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.autosave_spin = QSpinBox()
        self.autosave_spin.setRange(200, 10_000)
        self.autosave_spin.setSingleStep(100)
        self.autosave_spin.setSuffix(" ms")
        self.autosave_spin.setValue(settings.autosave_delay_ms)
        form.addRow("Autosave delay:", self.autosave_spin)

        self.animation_check = QCheckBox("Play the cover-opening animation on launch")
        self.animation_check.setChecked(settings.show_opening_animation)
        form.addRow("", self.animation_check)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 48)
        self.font_size_spin.setValue(settings.editor_default_font_size)
        form.addRow("Default entry font size:", self.font_size_spin)

        layout.addLayout(form)

        note = QLabel("Font size applies to new entries; it won't resize existing text.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #B08498; font-style: italic;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        self.result_settings = AppSettings(
            autosave_delay_ms=self.autosave_spin.value(),
            show_opening_animation=self.animation_check.isChecked(),
            editor_default_font_size=self.font_size_spin.value(),
        )
        self.accept()
