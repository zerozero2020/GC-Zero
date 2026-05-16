"""
Task list backed by a local SQLite database.

  /task                List open tasks
  /task list           List open tasks
  /task add <text>     Add a task
  /task done <#>       Mark a task done
  /task delete <#>     Remove a task permanently
  /task clear          Remove all completed tasks
"""

import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
DB_PATH = os.path.join(_DATA_DIR, "tasks.db")


def _init_db() -> None:
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                text    TEXT    NOT NULL,
                done    INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)


_init_db()


def handle_task(args: str) -> str:
    parts = args.strip().split(None, 1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1].strip() if len(parts) > 1 else ""

    if sub == "add":
        return _add(rest)
    if sub in ("done", "complete"):
        return _done(rest)
    if sub in ("delete", "del", "remove"):
        return _delete(rest)
    if sub == "clear":
        return _clear()
    return _list()


def _add(text: str) -> str:
    if not text:
        return "Usage: /task add <text>\nExample: /task add Call dentist"
    now = datetime.now(EASTERN).isoformat()
    with sqlite3.connect(DB_PATH) as con:
        con.execute("INSERT INTO tasks (text, done, created_at) VALUES (?, 0, ?)", (text, now))
    return f"Added: {text}"


def _list() -> str:
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT text FROM tasks WHERE done = 0 ORDER BY id"
        ).fetchall()
    if not rows:
        return "No open tasks."
    lines = ["*Tasks:*"]
    for i, (text,) in enumerate(rows, 1):
        lines.append(f"{i}. {text}")
    return "\n".join(lines)


def _done(arg: str) -> str:
    if not arg.isdigit():
        return "Usage: /task done <number>\nExample: /task done 2"
    n = int(arg)
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT id, text FROM tasks WHERE done = 0 ORDER BY id"
        ).fetchall()
        if n < 1 or n > len(rows):
            return f"No task #{n}. Send /task to see your list."
        row_id, text = rows[n - 1]
        con.execute("UPDATE tasks SET done = 1 WHERE id = ?", (row_id,))
    return f"Done: {text}"


def _delete(arg: str) -> str:
    if not arg.isdigit():
        return "Usage: /task delete <number>\nExample: /task delete 1"
    n = int(arg)
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT id, text FROM tasks WHERE done = 0 ORDER BY id"
        ).fetchall()
        if n < 1 or n > len(rows):
            return f"No task #{n}. Send /task to see your list."
        row_id, text = rows[n - 1]
        con.execute("DELETE FROM tasks WHERE id = ?", (row_id,))
    return f"Deleted: {text}"


def _clear() -> str:
    with sqlite3.connect(DB_PATH) as con:
        result = con.execute("DELETE FROM tasks WHERE done = 1")
        count = result.rowcount
    if count == 0:
        return "No completed tasks to clear."
    return f"Cleared {count} completed task{'s' if count > 1 else ''}."
