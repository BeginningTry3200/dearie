"""
main.py — Dearie entry point.

Wires together: passphrase unlock/setup, the cover-flip opening
animation, the sidebar of encrypted entries, and the rich-text editor
with autosave.
"""

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from animation import CoverAnimationWidget
from database import DatabaseManager
from editor import EditorWidget
from mood import MOOD_EMOJI
from settings import AppSettings, SETTINGS_FILENAME, SettingsDialog
from theming import JournalCard, RibbonBookmark, TableBackgroundWidget
from version import APP_NAME, __version__

DB_FILENAME = "dearie.db"
CARD_MARGIN = 40  # wood table visible around the journal cover, in px


class PassphraseDialog(QDialog):
    """Prompts for the master passphrase. In 'setup' mode, requires a
    confirmation field to guard against typos on first launch."""

    def __init__(self, setup_mode: bool, parent=None):
        super().__init__(parent)
        self.setup_mode = setup_mode
        self.setWindowTitle(f"{APP_NAME} — Unlock" if not setup_mode else f"{APP_NAME} — Set Up")
        self.setModal(True)

        layout = QVBoxLayout(self)
        heading = QLabel(
            f"Welcome! Create a master passphrase to encrypt your {APP_NAME} entries."
            if setup_mode
            else f"Enter your master passphrase to unlock {APP_NAME}."
        )
        heading.setWordWrap(True)
        layout.addWidget(heading)

        form = QFormLayout()
        self.passphrase_edit = QLineEdit()
        self.passphrase_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Passphrase:", self.passphrase_edit)

        self.confirm_edit = None
        if setup_mode:
            self.confirm_edit = QLineEdit()
            self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
            form.addRow("Confirm:", self.confirm_edit)

        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #C0392B;")
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._on_accept)
        layout.addWidget(buttons)

        self.result_passphrase = None

    def _on_accept(self):
        pw = self.passphrase_edit.text()
        if not pw:
            self.error_label.setText("Passphrase cannot be empty.")
            return
        if self.setup_mode:
            if len(pw) < 6:
                self.error_label.setText("Use at least 6 characters.")
                return
            if pw != self.confirm_edit.text():
                self.error_label.setText("Passphrases do not match.")
                return
        self.result_passphrase = pw
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, db: DatabaseManager, settings: AppSettings, settings_path: str):
        super().__init__()
        self.db = db
        self.current_journal_id = None
        self.settings = settings
        self.settings_path = settings_path

        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.resize(1080, 680)

        # --- Table backdrop, positioned manually so the journal "cover"
        # card below can float above it with margins on every side and a
        # drop shadow, rather than filling the window edge-to-edge. -------
        self.table = TableBackgroundWidget()
        self.setCentralWidget(self.table)

        self.card = JournalCard(self.table)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(18, 18, 18, 18)

        self.ribbon = RibbonBookmark(self.table)
        self.ribbon.resize(30, 78)
        self.ribbon.raise_()

        splitter = QSplitter()
        card_layout.addWidget(splitter)

        # --- Sidebar -----------------------------------------------------
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)

        self.journal_list = QListWidget()
        self.journal_list.setObjectName("JournalList")
        self.journal_list.currentItemChanged.connect(self._on_selection_changed)
        sidebar_layout.addWidget(self.journal_list, 1)

        button_row = QHBoxLayout()
        new_btn = QPushButton("+ New Entry")
        new_btn.clicked.connect(self._on_new_entry)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._on_delete_entry)
        button_row.addWidget(new_btn)
        button_row.addWidget(delete_btn)
        sidebar_layout.addLayout(button_row)

        splitter.addWidget(sidebar)

        # --- Editor --------------------------------------------------------
        self.editor = EditorWidget()
        self.editor.saveRequested.connect(self._on_save_requested)
        splitter.addWidget(self.editor)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 740])

        self._build_menu()
        self._apply_settings_to_editor()
        self.editor.newTagCreated.connect(self._on_tag_created)
        self.editor.set_available_tags(self.db.list_tags())

        self._reload_journal_list()
        self._layout_card_and_ribbon()

    # --------------------------------------------------------------- menu
    def _build_menu(self):
        settings_action = QAction("&Settings…", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        settings_action.triggered.connect(self._open_settings)
        # addAction (not just putting it in a menu) keeps the shortcut live
        # even if the menu bar is hidden on some platform/theme.
        self.addAction(settings_action)

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

    def _apply_settings_to_editor(self):
        self.editor.set_autosave_delay(self.settings.autosave_delay_ms)
        self.editor.set_default_font_size(self.settings.editor_default_font_size)

    def _open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.result_settings
            self.settings.save(self.settings_path)
            self._apply_settings_to_editor()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_card_and_ribbon()

    def _layout_card_and_ribbon(self):
        table_rect = self.table.rect()
        margin = min(CARD_MARGIN, max(16, table_rect.width() // 20))
        card_rect = table_rect.adjusted(margin, margin, -margin, -margin)
        if card_rect.isValid():
            self.card.setGeometry(card_rect)
            self.table.set_card_rect(card_rect)
        ribbon_x = card_rect.right() - 96
        ribbon_y = card_rect.top() - 14
        self.ribbon.setGeometry(ribbon_x, ribbon_y, self.ribbon.width(), self.ribbon.height())
        self.ribbon.raise_()

    # ---------------------------------------------------------------- data
    def _reload_journal_list(self, select_id: int | None = None):
        self.journal_list.blockSignals(True)
        self.journal_list.clear()
        entries = self.db.list_journals()
        selected_row = -1
        for row, (jid, title, updated_at, mood) in enumerate(entries):
            prefix = f"{MOOD_EMOJI[mood]} " if mood in MOOD_EMOJI else ""
            item = QListWidgetItem(prefix + (title or "Untitled Entry"))
            item.setData(Qt.ItemDataRole.UserRole, jid)
            self.journal_list.addItem(item)
            if select_id is not None and jid == select_id:
                selected_row = row
        self.journal_list.blockSignals(False)

        if selected_row >= 0:
            self.journal_list.setCurrentRow(selected_row)
        elif self.journal_list.count() > 0:
            self.journal_list.setCurrentRow(0)
        else:
            self.editor.clear_entry()
            self.current_journal_id = None

    def _on_selection_changed(self, current: QListWidgetItem, _previous):
        if current is None:
            self.editor.clear_entry()
            self.current_journal_id = None
            return
        jid = current.data(Qt.ItemDataRole.UserRole)
        entry = self.db.get_journal(jid)
        if entry is None:
            return
        self.current_journal_id = jid
        self.editor.load_entry(entry["title"], entry["content"], entry.get("tags", []), entry.get("mood"))

    def _on_new_entry(self):
        new_id = self.db.create_journal(title="Untitled Entry", content="")
        self._reload_journal_list(select_id=new_id)

    def _on_delete_entry(self):
        if self.current_journal_id is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Entry",
            "Delete this journal entry permanently?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.db.delete_journal(self.current_journal_id)
            self._reload_journal_list()

    def _on_save_requested(self, title: str, markdown: str, tags: list, mood):
        if self.current_journal_id is None:
            return
        self.db.update_journal(self.current_journal_id, title, markdown, tags, mood)
        # Keep sidebar title (and mood prefix) in sync without losing selection.
        current_item = self.journal_list.currentItem()
        if current_item is not None:
            prefix = f"{MOOD_EMOJI[mood]} " if mood in MOOD_EMOJI else ""
            current_item.setText(prefix + (title or "Untitled Entry"))

    def _on_tag_created(self, tag: str):
        # Persist the newly-coined tag to the vault-wide list so it shows
        # up as a suggestion for every other entry from now on.
        self.db.add_tag(tag)


def load_stylesheet(app: QApplication):
    qss_path = os.path.join(os.path.dirname(__file__), "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())


def load_app_icon(base_dir: str) -> QIcon:
    """Loads icon.svg and hands back a QIcon with a few rasterized sizes
    baked in, rather than a single bare SVG. Some places Qt shows an icon
    (the Windows taskbar and alt-tab switcher in particular) pick a size
    that a lone vector source doesn't always resolve cleanly, so we render
    it at the common sizes ourselves and let QIcon pick the best match."""
    icon_path = os.path.join(base_dir, "icon.svg")
    icon = QIcon()
    if os.path.exists(icon_path):
        renderer = QSvgRenderer(icon_path)
        if renderer.isValid():
            for size in (16, 24, 32, 48, 64, 128, 256):
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                icon.addPixmap(pixmap)
        else:
            # Fallback: let QIcon try to load it directly (works if a
            # system SVG icon-engine plugin is present).
            icon = QIcon(icon_path)
    return icon


def _set_windows_app_user_model_id():
    # On Windows, the taskbar groups windows (and picks a taskbar icon) by
    # the process's "App User Model ID", which defaults to the Python
    # interpreter's own ID rather than ours. Without this, a packaged
    # Dearie build can show Python's generic icon in the taskbar even
    # though setWindowIcon() is set correctly on the window itself.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                f"{APP_NAME}.{APP_NAME}.{__version__}"
            )
        except Exception:
            pass


def unlock_database(app: QApplication, db_path: str) -> DatabaseManager | None:
    db = DatabaseManager(db_path)
    db.connect()
    setup_mode = db.is_new_vault()

    while True:
        dialog = PassphraseDialog(setup_mode=setup_mode)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        if setup_mode:
            db.set_passphrase(dialog.result_passphrase)
            return db
        else:
            if db.verify_passphrase(dialog.result_passphrase):
                return db
            QMessageBox.warning(None, "Incorrect Passphrase", "That passphrase did not unlock the vault. Try again.")


def main():
    _set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    load_stylesheet(app)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, DB_FILENAME)
    settings_path = os.path.join(base_dir, SETTINGS_FILENAME)

    app_icon = load_app_icon(base_dir)
    app.setWindowIcon(app_icon)

    app_settings = AppSettings.load(settings_path)

    db = unlock_database(app, db_path)
    if db is None:
        sys.exit(0)

    window = MainWindow(db, app_settings, settings_path)
    window.setWindowIcon(app_icon)
    window.show()

    if app_settings.show_opening_animation:
        # Play the cover-opening animation as an overlay on top of the window.
        overlay = CoverAnimationWidget(window, duration_ms=1200)
        overlay.show()
        overlay.play()

    app.aboutToQuit.connect(db.close)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
