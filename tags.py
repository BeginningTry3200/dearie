"""
tags.py — The "#drama #boyfriend"-style tag picker.

TagInputWidget shows the current entry's tags as removable chips, plus a
small text field for adding more. Typing an existing tag and pressing
Enter (or picking it from the autocomplete dropdown) attaches it; typing
one that doesn't exist yet creates it on the spot and adds it to the
vault-wide tag list, so it shows up as a suggestion everywhere afterward.
"""

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCompleter,
    QHBoxLayout,
    QLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)


class FlowLayout(QLayout):
    """A layout that wraps its children onto new rows as needed — the
    standard recipe for a "tag chip" row, since Qt has no built-in
    wrapping layout."""

    def __init__(self, parent=None, margin=0, spacing=6):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        x, y = rect.x(), rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y()


class TagChip(QWidget):
    """One removable tag pill, e.g. '#drama ×'."""

    removed = Signal(str)

    def __init__(self, tag: str, parent=None):
        super().__init__(parent)
        self.tag = tag
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 6, 4)
        layout.setSpacing(4)

        label = QLineEdit(tag)
        label.setObjectName("TagChipLabel")
        label.setReadOnly(True)
        label.setFrame(False)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        label.setMinimumWidth(len(tag) * 8 + 6)
        layout.addWidget(label)

        close_btn = QPushButton("×")
        close_btn.setObjectName("TagChipClose")
        close_btn.setFixedSize(16, 16)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(lambda: self.removed.emit(self.tag))
        layout.addWidget(close_btn)

        self.setObjectName("TagChip")


def _normalize_tag(raw: str) -> str:
    """'boyfriend' -> '#boyfriend'; trims stray whitespace/commas."""
    text = raw.strip().strip(",")
    if not text:
        return ""
    if not text.startswith("#"):
        text = "#" + text
    return text


class TagInputWidget(QWidget):
    """Row of tag chips + an entry field with autocomplete over the
    vault-wide tag list. Typing a tag that isn't in that list yet creates
    it (emits newTagCreated) as soon as it's committed."""

    tagsChanged = Signal()
    newTagCreated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tags: list[str] = []
        self._available: list[str] = []

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(6)

        self._chip_area = QWidget()
        self._flow = FlowLayout(self._chip_area, margin=0, spacing=6)
        outer.addWidget(self._chip_area, 1)

        self.entry = QLineEdit()
        self.entry.setObjectName("TagEntryField")
        self.entry.setPlaceholderText("Add a tag…")
        self.entry.setFixedWidth(140)
        self.entry.returnPressed.connect(self._commit_entry_text)
        self._flow.addWidget(self.entry)

        self._completer = QCompleter([])
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.activated.connect(self._on_completer_activated)
        self.entry.setCompleter(self._completer)

        self.setObjectName("TagInputWidget")

    # ------------------------------------------------------------- state
    def set_available_tags(self, tags: list[str]):
        self._available = list(tags)
        self._completer.setModel(None)
        self._completer = QCompleter(self._available)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.activated.connect(self._on_completer_activated)
        self.entry.setCompleter(self._completer)

    def set_tags(self, tags: list[str]):
        self._tags = list(tags)
        self._rebuild_chips()

    def get_tags(self) -> list[str]:
        return list(self._tags)

    def clear_tags(self):
        self.set_tags([])

    # ------------------------------------------------------------- chips
    def _rebuild_chips(self):
        while self._flow.count() > 1:
            item = self._flow.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Re-add chips before the entry field, which is always last.
        entry_item = self._flow.takeAt(0)  # the entry field
        for tag in self._tags:
            chip = TagChip(tag)
            chip.removed.connect(self._remove_tag)
            self._flow.addWidget(chip)
        if entry_item is not None:
            self._flow.addItem(entry_item)
        self._chip_area.updateGeometry()

    def _remove_tag(self, tag: str):
        self._tags = [t for t in self._tags if t != tag]
        self._rebuild_chips()
        self.tagsChanged.emit()

    def _add_tag(self, raw: str):
        tag = _normalize_tag(raw)
        if not tag:
            return
        is_new = tag.lower() not in (t.lower() for t in self._available)
        if tag.lower() not in (t.lower() for t in self._tags):
            self._tags.append(tag)
            self._rebuild_chips()
            self.tagsChanged.emit()
        if is_new:
            self._available.append(tag)
            self.newTagCreated.emit(tag)
        self.entry.clear()

    def _commit_entry_text(self):
        self._add_tag(self.entry.text())

    def _on_completer_activated(self, text: str):
        self._add_tag(text)
