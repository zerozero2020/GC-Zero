"""
Quick notes backed by SQLite.

  /note <text>       Save a note
  /note delete <#>   Delete a note by position in the list
  /notes             List all notes (newest first)
"""

import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
DB_PATH = os.path.join(_DATA_DIR, "notes.db")


def _init_db() -> None:
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                text       TEXT    NOT NULL,
                created_at TEXT    NOT NULL
            )
        """)


_init_db()


def handle_note(args: str) -> str:
    parts = args.strip().split(None, 1)
    if not parts:
        return "Usage: /note <text>\nExample: /note Call mom back"
    if parts[0].lower() in ("delete", "del", "remove"):
        return _delete(parts[1].strip() if len(parts) > 1 else "")
    return _add(args.strip())


def handle_notes() -> str:
    return _list()


def _add(text: str) -> str:
    now = datetime.now(EASTERN).isoformat()
    with sqlite3.connect(DB_PATH) as con:
        con.execute("INSERT INTO notes (text, created_at) VALUES (?, ?)", (text, now))
    return f"Noted: {text}"


def _list() -> str:
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT text, created_at FROM notes ORDER BY id DESC LIMIT 20"
        ).fetchall()
    if not rows:
        return "No notes."
    lines = ["*Notes:*"]
    for i, (text, created_at) in enumerate(rows, 1):
        dt = datetime.fromisoformat(created_at).astimezone(EASTERN)
        lines.append(f"{i}. {text} _{dt.strftime('%b %-d')}_")
    return "\n".join(lines)


def _delete(arg: str) -> str:
    if not arg.isdigit():
        return "Usage: /note delete <number>\nExample: /note delete 1"
    n = int(arg)
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT id, text FROM notes ORDER BY id DESC LIMIT 20"
        ).fetchall()
        if n < 1 or n > len(rows):
            return f"No note #{n}. Send /notes to see your list."
        row_id, text = rows[n - 1]
        con.execute("DELETE FROM notes WHERE id = ?", (row_id,))
    return f"Deleted: {text}"
