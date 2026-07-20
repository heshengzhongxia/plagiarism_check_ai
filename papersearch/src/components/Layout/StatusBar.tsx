import { useAppStore } from '../../stores/useAppStore';

function StatusBar() {
  const backendStatus = useAppStore((s) => s.backendStatus);

  const statusConfig = {
    starting: { color: 'var(--gold)', label: '启动中...' },
    running: { color: 'var(--success)', label: 'localhost:5001' },
    stopped: { color: 'var(--danger)', label: '已停止' },
    error: { color: 'var(--danger)', label: '连接错误' },
  };

  const config = statusConfig[backendStatus];

  return (
    <footer className="flex items-center justify-between h-7 px-4 border-t border-[var(--border)] bg-[var(--bg)]/80 shrink-0">
      <div className="flex items-center gap-2">
        <div
          className="w-2 h-2 rounded-full"
          style={{ backgroundColor: config.color }}
        />
        <span className="text-xs text-[var(--muted)]">
          Python 后端: <span style={{ color: config.color }}>{config.label}</span>
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-[var(--muted)]">deepseek-chat</span>
        <span className="text-xs text-[var(--muted)]">v5.0</span>
      </div>
    </footer>
  );
}

export default StatusBar;
