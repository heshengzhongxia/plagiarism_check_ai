import { useState } from 'react';
import { useAppStore } from '../../stores/useAppStore';
import type { Modification } from '../../types';

const DIRECTION_COLORS: Record<string, string> = {
  '同义改写': 'var(--accent)',
  '结构调整': 'var(--gold)',
  '补充引用': 'var(--success)',
  '删除重写': 'var(--danger)',
  '合并精简': 'var(--purple)',
};

function ModItem({ mod }: { mod: Modification }) {
  const [open, setOpen] = useState(false);
  const color = DIRECTION_COLORS[mod.direction] || 'var(--muted)';
  const truncated = mod.user_sentence.length > 50
    ? mod.user_sentence.slice(0, 50) + '...'
    : mod.user_sentence;

  return (
    <div className="border border-[var(--border)] rounded-xl bg-[var(--card)]/30 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-[var(--card)]/40 transition-colors"
      >
        <span
          className="text-xs px-2 py-0.5 rounded-full shrink-0 font-medium"
          style={{ backgroundColor: color + '22', color }}
        >
          {mod.direction}
        </span>
        <span className="text-sm text-[var(--text)] truncate flex-1">{truncated}</span>
        <span className="text-xs text-[var(--muted)]">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2">
          <div>
            <div className="text-xs text-[var(--muted)] mb-0.5">原句</div>
            <div className="text-sm text-[var(--text)] bg-[var(--bg)]/50 rounded-lg p-2">
              {mod.user_sentence}
            </div>
          </div>
          <div>
            <div className="text-xs text-[var(--muted)] mb-0.5">修改后</div>
            <div className="text-sm text-[var(--text)] bg-[var(--bg)]/50 rounded-lg p-2">
              {mod.modified_sentence}
            </div>
          </div>
          <div>
            <div className="text-xs text-[var(--muted)] mb-0.5">修改说明</div>
            <div className="text-sm text-[var(--text)]">{mod.explanation}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function ModificationsTab() {
  const modifications = useAppStore((s) => s.modifications);

  if (modifications.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-[var(--muted)]">暂无修改方案。</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {modifications.map((mod, i) => (
        <ModItem key={i} mod={mod} />
      ))}
    </div>
  );
}

export default ModificationsTab;
