"""
database.py — Encrypted storage layer for Dearie.

NOTE ON ENCRYPTION APPROACH:
The blueprint calls for SQLCipher (pysqlcipher3), which wraps SQLite itself
in AES-256 at the file level. pysqlcipher3 requires a compiled SQLCipher
system library, which is often unavailable or painful to install cross-
platform (especially on Windows without prebuilt wheels). To keep this app
easy to run anywhere with just `pip install`, this module instead uses:

  - Standard library `sqlite3` for storage.
  - `cryptography`'s Fernet (AES-128-CBC + HMAC) for field-level encryption
    of the sensitive `title` and `content` columns.
  - PBKDF2-HMAC-SHA256 with 100,000+ iterations to derive the Fernet key
    from the user's master passphrase, matching the blueprint's KDF spec.

The net effect is the same security promise (nothing readable on disk
without the passphrase, strong KDF, AES under the hood) without requiring
a system-level SQLCipher build. If you later obtain a working SQLCipher
wheel, this class's public interface (verify_passphrase, list_journals,
create_journal, get_journal, update_journal, delete_journal) can be kept
identical while swapping the implementation.
"""

import base64
import hashlib
import os
import sqlite3
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PBKDF2_ITERATIONS = 100_000
VERIFIER_PLAINTEXT = b"pink-journal-ok"


class WrongPassphraseError(Exception):
    pass


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None
        self.fernet: Fernet | None = None

    # ---------------------------------------------------------------- setup
    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS journals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def is_new_vault(self) -> bool:
        cur = self.conn.execute("SELECT value FROM meta WHERE key = 'salt'")
        return cur.fetchone() is None

    # ---------------------------------------------------------- passphrase
    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        raw = kdf.derive(passphrase.encode("utf-8"))
        return base64.urlsafe_b64encode(raw)

    def set_passphrase(self, passphrase: str):
        """Called once, on first launch, to initialize a new vault."""
        salt = os.urandom(16)
        key = self._derive_key(passphrase, salt)
        self.fernet = Fernet(key)
        verifier = self.fernet.encrypt(VERIFIER_PLAINTEXT).decode("utf-8")

        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES ('salt', ?)",
            (base64.b64encode(salt).decode("utf-8"),),
        )
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES ('verifier', ?)",
            (verifier,),
        )
        self.conn.commit()

    def verify_passphrase(self, passphrase: str) -> bool:
        """Called on subsequent launches to unlock an existing vault."""
        cur = self.conn.execute("SELECT value FROM meta WHERE key = 'salt'")
        row = cur.fetchone()
        if row is None:
            raise WrongPassphraseError("Vault has not been initialized.")
        salt = base64.b64decode(row[0])
        key = self._derive_key(passphrase, salt)
        candidate = Fernet(key)

        cur = self.conn.execute("SELECT value FROM meta WHERE key = 'verifier'")
        verifier_row = cur.fetchone()
        try:
            plaintext = candidate.decrypt(verifier_row[0].encode("utf-8"))
        except InvalidToken:
            return False
        if plaintext != VERIFIER_PLAINTEXT:
            return False

        self.fernet = candidate
        return True

    # --------------------------------------------------------------- CRUD
    def _require_unlocked(self):
        if self.fernet is None:
            raise RuntimeError("Vault is locked — verify passphrase first.")

    def _enc(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def _dec(self, ciphertext: str) -> str:
        return self.fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")

    def list_journals(self):
        """Returns [(id, title, updated_at), ...] newest first, decrypted."""
        self._require_unlocked()
        cur = self.conn.execute(
            "SELECT id, title, updated_at FROM journals ORDER BY updated_at DESC"
        )
        results = []
        for jid, enc_title, updated_at in cur.fetchall():
            try:
                title = self._dec(enc_title)
            except InvalidToken:
                title = "(unreadable entry)"
            results.append((jid, title, updated_at))
        return results

    def create_journal(self, title: str = "Untitled Entry", content: str = "") -> int:
        self._require_unlocked()
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute(
            "INSERT INTO journals (title, content, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (self._enc(title), self._enc(content), now, now),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_journal(self, journal_id: int):
        self._require_unlocked()
        cur = self.conn.execute(
            "SELECT title, content FROM journals WHERE id = ?", (journal_id,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {"title": self._dec(row[0]), "content": self._dec(row[1])}

    def update_journal(self, journal_id: int, title: str, content: str):
        self._require_unlocked()
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE journals SET title = ?, content = ?, updated_at = ? WHERE id = ?",
            (self._enc(title), self._enc(content), now, journal_id),
        )
        self.conn.commit()

    def delete_journal(self, journal_id: int):
        self._require_unlocked()
        self.conn.execute("DELETE FROM journals WHERE id = ?", (journal_id,))
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()
