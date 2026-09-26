"""
editor.py — Rich-text/Markdown page editor with formatting toolbar and
debounced autosave.
"""

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QTextCharFormat, QTextCursor, QTextListFormat
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

AUTOSAVE_DEBOUNCE_MS = 1000

PASTEL_SWATCHES = ["#D46A8C", "#8C6A9E", "#5A8F7B", "#4A6FA5", "#B8860B"]


class EditorWidget(QWidget):
    """Emits contentDirty() immediately on edit, and saveRequested(title,
    markdown) after the debounce window elapses with no further edits."""

    saveRequested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._autosave_delay_ms = AUTOSAVE_DEBOUNCE_MS
        self._default_font_size = 13
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._do_autosave)
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Title field -----------------------------------------------
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("EntryTitle")
        self.title_edit.setPlaceholderText("Entry title...")
        self.title_edit.textChanged.connect(self._on_changed)
        root.addWidget(self.title_edit)

        # --- Toolbar -----------------------------------------------------
        toolbar = QToolBar()
        toolbar.setObjectName("FormatToolbar")
        toolbar.setMovable(False)

        self.bold_action = QAction("B", self, checkable=True)
        self.bold_action.triggered.connect(self._toggle_bold)
        toolbar.addAction(self.bold_action)

        self.italic_action = QAction("I", self, checkable=True)
        self.italic_action.triggered.connect(self._toggle_italic)
        toolbar.addAction(self.italic_action)

        self.underline_action = QAction("U", self, checkable=True)
        self.underline_action.triggered.connect(self._toggle_underline)
        toolbar.addAction(self.underline_action)

        self.strike_action = QAction("S", self, checkable=True)
        self.strike_action.triggered.connect(self._toggle_strike)
        toolbar.addAction(self.strike_action)

        toolbar.addSeparator()

        self.heading_box = QComboBox()
        self.heading_box.addItems(["Body", "Heading 1", "Heading 2", "Heading 3"])
        self.heading_box.currentIndexChanged.connect(self._apply_heading)
        toolbar.addWidget(self.heading_box)

        toolbar.addSeparator()

        bullet_action = QAction("• List", self)
        bullet_action.triggered.connect(lambda: self._apply_list(QTextListFormat.ListDisc))
        toolbar.addAction(bullet_action)

        numbered_action = QAction("1. List", self)
        numbered_action.triggered.connect(
            lambda: self._apply_list(QTextListFormat.ListDecimal)
        )
        toolbar.addAction(numbered_action)

        toolbar.addSeparator()

        align_left = QAction("Left", self)
        align_left.triggered.connect(lambda: self.body.setAlignment(_qt_align_left()))
        toolbar.addAction(align_left)

        align_center = QAction("Center", self)
        align_center.triggered.connect(lambda: self.body.setAlignment(_qt_align_center()))
        toolbar.addAction(align_center)

        align_right = QAction("Right", self)
        align_right.triggered.connect(lambda: self.body.setAlignment(_qt_align_right()))
        toolbar.addAction(align_right)

        toolbar.addSeparator()

        self.font_size_box = QSpinBox()
        self.font_size_box.setRange(8, 48)
        self.font_size_box.setValue(13)
        self.font_size_box.valueChanged.connect(self._apply_font_size)
        toolbar.addWidget(self.font_size_box)

        color_action = QAction("Color", self)
        color_action.triggered.connect(self._pick_color)
        toolbar.addAction(color_action)

        root.addWidget(toolbar)

        # --- Body ----------------------------------------------------------
        self.body = QTextEdit()
        self.body.setObjectName("EntryBody")
        self.body.setAcceptRichText(True)
        self.body.textChanged.connect(self._on_changed)
        root.addWidget(self.body, 1)

        # --- Status bar ------------------------------------------------
        status_row = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setObjectName("SaveStatus")
        status_row.addStretch(1)
        status_row.addWidget(self.status_label)
        root.addLayout(status_row)

        self.setEnabled(False)

    # ------------------------------------------------------------- content
    def load_entry(self, title: str, markdown: str):
        self._loading = True
        self.setEnabled(True)
        self.title_edit.setText(title)
        self.body.setMarkdown(markdown)
        self.status_label.setText("")
        self._loading = False

    def clear_entry(self):
        self._loading = True
        self.setEnabled(False)
        self.title_edit.clear()
        self.body.clear()
        self.body.setFontPointSize(self._default_font_size)
        self.status_label.setText("")
        self._loading = False

    def current_title(self) -> str:
        return self.title_edit.text().strip() or "Untitled Entry"

    def current_markdown(self) -> str:
        return self.body.toMarkdown()

    def set_autosave_delay(self, delay_ms: int):
        self._autosave_delay_ms = max(200, int(delay_ms))

    def set_default_font_size(self, size: int):
        self._default_font_size = max(8, int(size))

    # ------------------------------------------------------------- autosave
    def _on_changed(self):
        if self._loading:
            return
        self.status_label.setText("Saving...")
        self._autosave_timer.start(self._autosave_delay_ms)

    def _do_autosave(self):
        self.saveRequested.emit(self.current_title(), self.current_markdown())
        self.status_label.setText("All changes saved locally")

    # ---------------------------------------------------------- formatting
    def _merge_format(self, fmt: QTextCharFormat):
        cursor = self.body.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self.body.mergeCurrentCharFormat(fmt)

    def _toggle_bold(self, checked: bool):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal)
        self._merge_format(fmt)

    def _toggle_italic(self, checked: bool):
        fmt = QTextCharFormat()
        fmt.setFontItalic(checked)
        self._merge_format(fmt)

    def _toggle_underline(self, checked: bool):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(checked)
        self._merge_format(fmt)

    def _toggle_strike(self, checked: bool):
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(checked)
        self._merge_format(fmt)

    def _apply_heading(self, index: int):
        cursor = self.body.textCursor()
        fmt = QTextCharFormat()
        sizes = {0: 13, 1: 24, 2: 20, 3: 16}
        fmt.setFontPointSize(sizes.get(index, 13))
        fmt.setFontWeight(
            QFont.Weight.Bold if index in (1, 2, 3) else QFont.Weight.Normal
        )
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        cursor.mergeCharFormat(fmt)
        self.body.mergeCurrentCharFormat(fmt)

    def _apply_list(self, list_style):
        cursor = self.body.textCursor()
        cursor.createList(list_style)

    def _apply_font_size(self, size: int):
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self._merge_format(fmt)

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(PASTEL_SWATCHES[0]), self, "Text Color")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self._merge_format(fmt)


def _qt_align_left():
    from PySide6.QtCore import Qt
    return Qt.AlignmentFlag.AlignLeft


def _qt_align_center():
    from PySide6.QtCore import Qt
    return Qt.AlignmentFlag.AlignCenter


def _qt_align_right():
    from PySide6.QtCore import Qt
    return Qt.AlignmentFlag.AlignRight
