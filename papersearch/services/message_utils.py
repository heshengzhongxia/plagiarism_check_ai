"""Shared message utility functions for the papersearch pipeline."""
import time


def add_message(task_store, task_id, msg):
    """Append a message to a task's conversation history."""
    if task_id in task_store:
        task_store[task_id]["conversation"].append(msg)


def system_msg(message, emoji="⚙️"):
    """Create a system message dict."""
    return {"agent_id": "system", "agent_name": "系统", "emoji": emoji,
            "color": "#7b8ca8", "message": message, "timestamp": time.time()}
