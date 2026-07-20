import { useAppStore } from '../../stores/useAppStore';

const API_BASE = 'http://localhost:5001';

function ControlBar() {
  const taskStatus = useAppStore((s) => s.taskStatus);
  const currentTaskId = useAppStore((s) => s.currentTaskId);
  const autoMode = useAppStore((s) => s.autoMode);

  if (taskStatus === 'idle' || taskStatus === 'completed' || taskStatus === 'error') return null;

  const handleConfirm = async () => {
    if (!currentTaskId) return;
    try {
      await fetch(`${API_BASE}/api/confirm/${currentTaskId}`, { method: 'POST' });
    } catch (e) {
      console.error('Confirm failed:', e);
    }
  };

  const handleRetry = async () => {
    if (!currentTaskId) return;
    try {
      await fetch(`${API_BASE}/api/retry/${currentTaskId}`, { method: 'POST' });
    } catch (e) {
      console.error('Retry failed:', e);
    }
  };

  return (
    <div className="flex items-center justify-center gap-2 px-4 py-2 border-t border-[var(--border)] shrink-0">
      {taskStatus === 'processing' && (
        <button
          onClick={handleRetry}
          className="px-3 py-1 text-xs rounded-lg bg-[var(--card)] text-[var(--muted)] hover:bg-[var(--card)]/80 transition-colors border border-[var(--border)]"
        >
          🔄 重试
        </button>
      )}
      {taskStatus === 'paused' && !autoMode && (
        <button
          onClick={handleConfirm}
          className="px-4 py-1.5 text-sm rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent)]/80 transition-colors font-medium"
        >
          ▶️ 确认继续
        </button>
      )}
    </div>
  );
}

export default ControlBar;
