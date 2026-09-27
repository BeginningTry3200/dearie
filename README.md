# Dearie

A private, encrypted desktop journal built with PySide6. Dearie looks like a
journal sitting on a wooden table — a "cover" card with a ribbon bookmark,
a sidebar of entries, and a rich-text editor with autosave — and everything
you write is encrypted at rest behind a single master passphrase.

## Features

- **Passphrase-locked vault** — on first launch you set a master passphrase;
  every launch after that requires it to unlock your entries.
- **Encrypted storage** — entry titles and content are encrypted field-by-field
  before they touch disk (see [Encryption](#encryption) below).
- **Sidebar of entries** — create, select, rename (via title), and delete
  journal entries from a simple list.
- **Tags** — attach `#hashtag`-style tags to any entry. A handful of default
  tags (`#drama`, `#boyfriend`, `#work`, `#family`, `#vent`, `#good day`) are
  seeded on first launch; typing a tag that doesn't exist yet in the tag
  field creates it on the spot and adds it to the vault-wide suggestion list.
- **Mood tracker** — a row of emoji buttons at the bottom of the editor lets
  you tag an entry's mood (happy, calm, neutral, sad, angry, anxious, tired).
  Click one to set it, click it again to clear it — an entry doesn't have to
  have a mood at all. The current entry's mood emoji also shows next to its
  title in the sidebar.
- **Rich-text editor with autosave** — a formatting toolbar (bold/italic/
  underline/strikethrough, headings, lists, alignment, font family & size,
  text color, highlight, blockquote, inline code, clear formatting,
  undo/redo) plus debounced autosave, so edits are saved automatically
  ~1 second after you stop typing.
- **Skeuomorphic UI** — a procedurally painted wood-table backdrop, a journal
  "cover" card with a drop shadow, and a ribbon bookmark, all drawn with
  `QPainter` (no image assets to ship).
- **Opening animation** — an optional "book cover" animation plays when the
  app starts: two pink cover panels sit closed over the window, then swing
  open to either side, revealing the interface underneath. Toggleable in
  Settings.
- **Configurable settings** — autosave delay, opening animation on/off, and
  default editor font size, persisted to a local (unencrypted) preferences
  file.

## Requirements

- Python 3.10+
- [PySide6](https://pypi.org/project/PySide6/) >= 6.5
- [cryptography](https://pypi.org/project/cryptography/) >= 41.0

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

On first run, you'll be prompted to create a master passphrase (minimum 6
characters). On every subsequent run, you'll be asked to enter it to unlock
your vault. **There is no password reset** — if you forget your passphrase,
your existing entries cannot be decrypted.

## Usage

- **New Entry** — click "+ New Entry" in the sidebar to create an untitled
  entry.
- **Edit** — select an entry from the sidebar and start typing in the editor.
  Changes save automatically about a second after you stop typing.
- **Delete** — select an entry and click "Delete" (asks for confirmation).
- **Settings** — `File → Settings…` (or `Ctrl+,`) to adjust autosave delay,
  the opening animation, and default font size.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | App entry point; wires together unlock, main window, sidebar, editor, and animation. |
| `database.py` | Encrypted storage layer (SQLite + Fernet field encryption); also stores entry tags, mood, and the vault-wide tag list. |
| `editor.py` | Rich-text/Markdown page editor with formatting toolbar and debounced autosave. |
| `tags.py` | The tag chip row: removable chips, autocomplete, and on-the-fly tag creation. |
| `mood.py` | The emoji mood-picker row at the bottom of the editor. |
| `animation.py` | The opening two-panel "book cover" animation overlay. |
| `theming.py` | Procedurally painted wood-table backdrop, journal cover card, and ribbon bookmark. |
| `settings.py` | User-configurable settings (dataclass + JSON persistence) and the Settings dialog. |
| `style.qss` | Qt stylesheet for the app's look and feel. |
| `version.py` | Single source of truth for app name and version. |

## Data files

- `dearie.db` — the encrypted SQLite vault (created on first run). Journal
  `title` and `content` fields are encrypted; nothing readable lives here
  without your passphrase.
- `dearie_settings.json` — plain-text app preferences (autosave delay,
  animation toggle, font size). Not sensitive, so it isn't encrypted.

Both files are created next to the app's source on first run.

## Encryption

Dearie's original design called for SQLCipher (full database-file
encryption), but `pysqlcipher3` requires a compiled system library that's
often unavailable or painful to install cross-platform, especially on
Windows. To keep the app installable anywhere with just `pip install`,
Dearie instead uses:

- Standard library `sqlite3` for storage.
- `cryptography`'s `Fernet` (AES-128-CBC + HMAC) for field-level encryption
  of the sensitive `title` and `content` columns.
- PBKDF2-HMAC-SHA256 with 100,000+ iterations to derive the encryption key
  from your master passphrase.

This gives the same practical security promise — nothing readable on disk
without the passphrase, a strong KDF, AES under the hood — without requiring
a system-level SQLCipher build. The `DatabaseManager` class keeps a stable
public interface (`verify_passphrase`, `list_journals`, `create_journal`,
`get_journal`, `update_journal`, `delete_journal`), so the implementation
could be swapped for real SQLCipher later without changing the rest of the
app.

## Notes

- This is a v1.0.0 desktop app intended for local, single-user use — there's
  no sync, cloud backup, or multi-device support.
- Losing the master passphrase means losing access to existing entries; there
  is no recovery mechanism by design.
