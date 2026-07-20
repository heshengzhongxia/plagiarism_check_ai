"""
TaskManager: high-level interface over the SQLite Repository.

Handles JSON serialisation for the agents_status, agent_results, and
final_report columns so callers work with plain Python dicts.
"""

from __future__ import annotations

import json
import time

from papersearch.store.repository import Repository


class TaskManager:
    """Persistent task store backed by SQLite.

    Usage::

        tm = TaskManager("path/to/store.db")
        tm.create_task("task-1", {"auto_mode": True, "threshold": 60})
        tm.update_agent_status("task-1", "agent1", "运行中", 0)
        tm.add_message("task-1", {"agent_id": "agent1", ...})
        status = tm.get_status("task-1")
    """

    def __init__(self, db_path: str):
        self._repo = Repository(db_path)

    # ------------------------------------------------------------------
    # Task lifecycle
    # ------------------------------------------------------------------

    def create_task(self, task_id: str, config: dict) -> None:
        """Create a new task row with initial state.

        *config* may contain any of: ``auto_mode``, ``threshold``,
        ``paper_title``, ``cnki_task_id``.
        Boolean ``auto_mode`` is coerced to 0/1 for storage.
        """
        row = {"id": task_id}

        for key in ("auto_mode", "threshold", "paper_title", "cnki_task_id"):
            if key in config:
                val = config[key]
                if key == "auto_mode":
                    val = 1 if val else 0
                row[key] = val

        self._repo.create_task(task_id, row)

    # ------------------------------------------------------------------
    # Agent status helpers
    # ------------------------------------------------------------------

    def update_agent_status(
        self, task_id: str, agent_id: str, status: str, progress: int
    ) -> None:
        """Set the status and progress for a single agent.

        Reads the current ``agents_status`` JSON, updates the entry for
        *agent_id*, and writes it back.
        """
        task = self._repo.get_task(task_id)
        if task is None:
            return

        agents = json.loads(task.get("agents_status", "{}"))
        agents[agent_id] = {"status": status, "progress": progress}
        self._repo.update_task(task_id, agents_status=json.dumps(agents, ensure_ascii=False))

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def add_message(self, task_id: str, msg: dict) -> None:
        """Persist one message row linked to *task_id*.

        *msg* should contain at least ``agent_id`` and ``message``.
        Optional keys: ``agent_name``, ``emoji``, ``color``, ``timestamp``.
        """
        self._repo.add_message(task_id, msg)

    def get_messages(self, task_id: str, since: int = 0) -> list[dict]:
        """Return messages for *task_id* whose id is greater than *since*."""
        return self._repo.get_messages(task_id, since)

    # ------------------------------------------------------------------
    # Status & reports
    # ------------------------------------------------------------------

    def get_status(self, task_id: str) -> dict | None:
        """Return the full task record with JSON fields parsed into Python
        objects (``agents_status``, ``agent_results``, ``final_report``).
        """
        task = self._repo.get_task(task_id)
        if task is None:
            return None

        for col in ("agents_status", "agent_results", "final_report"):
            raw = task.get(col)
            if raw and isinstance(raw, str):
                try:
                    task[col] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    pass  # keep as-is if not valid JSON
        return task

    def set_report(
        self, task_id: str, report: dict, docx_path: str | None = None
    ) -> None:
        """Store the final report JSON and optional docx path, marking the
        task as completed.
        """
        updates = {
            "final_report": json.dumps(report, ensure_ascii=False),
            "status": "completed",
        }
        if docx_path is not None:
            updates["docx_path"] = docx_path
        self._repo.update_task(task_id, **updates)

    # ------------------------------------------------------------------
    # History & housekeeping
    # ------------------------------------------------------------------

    def list_history(self, limit: int = 50) -> list[dict]:
        """Return recent tasks with essential summary fields."""
        tasks = self._repo.list_tasks(limit)
        return [
            {
                "task_id": t["id"],
                "status": t["status"],
                "paper_title": t.get("paper_title"),
                "created_at": t["created_at"],
                "updated_at": t["updated_at"],
            }
            for t in tasks
        ]

    def delete_task(self, task_id: str) -> None:
        """Remove a task and all its messages."""
        self._repo.delete_task(task_id)
