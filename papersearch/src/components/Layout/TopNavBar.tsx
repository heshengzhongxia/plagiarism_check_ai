interface TopNavBarProps {
  onUpload: () => void;
  onNewTask: () => void;
  onSettings: () => void;
  onHistory: () => void;
}

function TopNavBar({ onUpload, onNewTask, onSettings, onHistory }: TopNavBarProps) {
  return (
    <header className="flex items-center justify-between h-14 px-5 border-b border-[var(--border)] bg-[var(--bg)]/80 backdrop-blur-sm shrink-0">
      <div className="flex items-center gap-3">
        <span className="text-xl">📄</span>
        <h1 className="text-lg font-semibold tracking-wide text-[var(--text)]">
          六智Agent论文工坊
        </h1>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onUpload}
          className="px-3 py-1.5 text-sm rounded-lg bg-[var(--accent)]/20 text-[var(--accent)] hover:bg-[var(--accent)]/30 transition-colors"
        >
          📤 上传论文
        </button>
        <button
          onClick={onNewTask}
          className="px-3 py-1.5 text-sm rounded-lg bg-[var(--card)] text-[var(--text)] hover:bg-[var(--card)]/80 transition-colors border border-[var(--border)]"
        >
          🚀 新建任务
        </button>
        <button
          onClick={onSettings}
          className="px-3 py-1.5 text-sm rounded-lg bg-[var(--card)] text-[var(--text)] hover:bg-[var(--card)]/80 transition-colors border border-[var(--border)]"
        >
          ⚙️ 设置
        </button>
        <button
          onClick={onHistory}
          className="px-3 py-1.5 text-sm rounded-lg bg-[var(--card)] text-[var(--text)] hover:bg-[var(--card)]/80 transition-colors border border-[var(--border)]"
        >
          📋 历史
        </button>
      </div>
    </header>
  );
}

export default TopNavBar;
