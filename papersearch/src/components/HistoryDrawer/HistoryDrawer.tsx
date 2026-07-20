import { useEffect, useState } from 'react';

const API_BASE = 'http://localhost:5001';

interface HistoryItem {
  id: string;
  status: string;
  paper_title?: string;
  total_matches?: number;
  created_at: string;
}

interface HistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

function HistoryDrawer({ isOpen, onClose }: HistoryDrawerProps) {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    fetch(`${API_BASE}/api/history`)
      .then((r) => r.json())
      .then((data) => setHistory(data.history || []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, [isOpen]);

  const statusLabel = (s: string) => {
    switch (s) {
      case 'processing': return { text: '处理中', color: 'var(--gold)' };
      case 'completed': return { text: '已完成', color: 'var(--success)' };
      case 'error': return { text: '错误', color: 'var(--danger)' };
      default: return { text: s, color: 'var(--muted)' };
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-[360px] h-full bg-[var(--card)] border-l border-[var(--border)] shadow-2xl flex flex-col animate-[slideIn_0.2s_ease-out]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
          <h2 className="text-lg font-semibold text-[var(--text)]">📋 历史任务</h2>
          <button
            onClick={onClose}
            className="text-[var(--muted)] hover:text-[var(--text)] text-lg transition-colors"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {loading && (
            <p className="text-sm text-[var(--muted)] text-center py-8">加载中...</p>
          )}
          {!loading && history.length === 0 && (
            <p className="text-sm text-[var(--muted)] text-center py-8">暂无历史任务</p>
          )}
          {history.map((item) => {
            const s = statusLabel(item.status);
            return (
              <div
                key={item.id}
                className="p-3 rounded-xl border border-[var(--border)] bg-[var(--bg)]/30 hover:bg-[var(--bg)]/50 transition-colors cursor-pointer"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-[var(--muted)]">{item.id}</span>
                  <span
                    className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{ backgroundColor: s.color + '22', color: s.color }}
                  >
                    {s.text}
                  </span>
                </div>
                <div className="text-sm text-[var(--text)] truncate">
                  {item.paper_title || '未命名论文'}
                </div>
                <div className="text-xs text-[var(--muted)] mt-1">
                  {item.total_matches != null ? `${item.total_matches} 处重复 · ` : ''}
                  {item.created_at}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default HistoryDrawer;
