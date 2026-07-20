"""
Repository: SQLite data access layer for tasks and task messages.

All SQL operations use parameterized queries. Column names in SET clauses
are validated against the schema to prevent injection.
"""

import sqlite3
import os
import time
from pathlib import Path

# Allowed columns in the tasks table (whitelist for dynamic SET clauses)
_TASK_COLUMNS = {
    "id", "status", "auto_mode", "threshold", "paper_title",
    "agents_status", "agent_results", "final_report", "docx_path",
    "cnki_task_id", "batch_progress", "batch_pct",
    "created_at", "updated_at",
}

# Allowed columns in the task_messages table
_MESSAGE_COLUMNS = {
    "task_id", "agent_id", "agent_name", "emoji", "color",
    "message", "timestamp",
}


def _load_schema(conn):
    """Execute schema.sql to create tables and indices if they do not exist."""
    schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())


class Repository:
    """Low-level SQLite operations for tasks and messages.

    All methods use parameterized queries.  Column names for UPDATE
    are validated against a whitelist and interpolated via f-string
    (safe because they come from our own whitelist, not user input).
    """

    def __init__(self, db_path: str):
        """Open (or create) the SQLite database and ensure schema exists.

        Args:
            db_path: Path to the .db file on disk.
        """
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        _load_schema(self._conn)

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------

    def create_task(self, task_id: str, config: dict) -> None:
        """Insert a new task row.

        Args:
            task_id: Primary key for the task.
            config: Dict whose keys must be a subset of _TASK_COLUMNS.
                    ``id`` is always set from *task_id* regardless of *config*.
        """
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "id": task_id,
            "status": "processing",
            "auto_mode": 1,
            "threshold": 60,
            "agents_status": "{}",
            "agent_results": "{}",
            "batch_progress": "",
            "batch_pct": 0,
            "created_at": now,
            "updated_at": now,
        }
        # Merge caller-supplied config, skipping unknown keys
        for k, v in config.items():
            if k in _TASK_COLUMNS and k != "id":
                row[k] = v

        columns = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        sql = f"INSERT INTO tasks ({columns}) VALUES ({placeholders})"
        self._conn.execute(sql, list(row.values()))
        self._conn.commit()

    def update_task(self, task_id: str, **kwargs) -> None:
        """Update columns on an existing task row.

        Only keys present in ``_TASK_COLUMNS`` are accepted; unknown keys
        are silently dropped.  ``id`` can never be changed.
        ``updated_at`` is always set to the current timestamp.
        """
        kwargs.pop("id", None)                       # never change PK
        kwargs["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        safe = {k: v for k, v in kwargs.items() if k in _TASK_COLUMNS}
        if not safe:
            return

        assignments = ", ".join(f"{k} = ?" for k in safe)
        sql = f"UPDATE tasks SET {assignments} WHERE id = ?"
        self._conn.execute(sql, list(safe.values()) + [task_id])
        self._conn.commit()

    def get_task(self, task_id: str) -> dict | None:
        """Return the task row as a plain dict, or *None*."""
        cur = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def add_message(self, task_id: str, msg_dict: dict) -> None:
        """Insert a message row linked to *task_id*."""
        safe = {}
        for k in _MESSAGE_COLUMNS:
            safe[k] = msg_dict.get(k)
        safe["task_id"] = task_id

        columns = ", ".join(safe.keys())
        placeholders = ", ".join("?" for _ in safe)
        sql = f"INSERT INTO task_messages ({columns}) VALUES ({placeholders})"
        self._conn.execute(sql, list(safe.values()))
        self._conn.commit()

    def get_messages(self, task_id: str, since: int = 0) -> list[dict]:
        """Return messages for *task_id* whose rowid > *since*, ordered by id."""
        cur = self._conn.execute(
            "SELECT * FROM task_messages WHERE task_id = ? AND id > ? ORDER BY id",
            (task_id, since),
        )
        return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Listing & housekeeping
    # ------------------------------------------------------------------

    def list_tasks(self, limit: int = 50) -> list[dict]:
        """Return the most recent tasks, newest first."""
        cur = self._conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

    def delete_task(self, task_id: str) -> None:
        """Delete a task and all of its messages (cascaded manually for clarity)."""
        self._conn.execute("DELETE FROM task_messages WHERE task_id = ?", (task_id,))
        self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self._conn.commit()

    def cleanup_old(self, days: int = 30) -> int:
        """Delete completed tasks older than *days* and return the count.

        Only removes tasks whose status is 'completed', 'error', or 'cancelled'.
        """
        cutoff = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(time.time() - days * 86400),
        )
        cur = self._conn.execute(
            "SELECT id FROM tasks WHERE updated_at < ? AND status IN ('completed','error','cancelled')",
            (cutoff,),
        )
        old_ids = [r["id"] for r in cur.fetchall()]
        for tid in old_ids:
            self.delete_task(tid)
        return len(old_ids)
