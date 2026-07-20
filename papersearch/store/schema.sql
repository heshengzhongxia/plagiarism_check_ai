CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'processing',
    auto_mode INTEGER NOT NULL DEFAULT 1,
    threshold INTEGER NOT NULL DEFAULT 60,
    paper_title TEXT,
    agents_status TEXT DEFAULT '{}',
    agent_results TEXT DEFAULT '{}',
    final_report TEXT,
    docx_path TEXT,
    cnki_task_id TEXT,
    batch_progress TEXT DEFAULT '',
    batch_pct INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    agent_name TEXT,
    emoji TEXT,
    color TEXT,
    message TEXT,
    timestamp REAL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_task ON task_messages(task_id);
CREATE INDEX IF NOT EXISTS idx_messages_since ON task_messages(task_id, id);
