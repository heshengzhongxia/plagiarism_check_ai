import { useAppStore } from '../../stores/useAppStore';

function OverviewTab() {
  const report = useAppStore((s) => s.report);

  if (!report) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-[var(--muted)]">报告尚未生成，等待任务完成。</p>
      </div>
    );
  }

  const stats = [
    { label: '总重复数', value: report.total_matches, icon: '🔍', color: 'var(--danger)' },
    { label: '风险等级', value: report.risk_assessment, icon: '⚠️', color: 'var(--gold)' },
  ];

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--text)] leading-relaxed">{report.summary}</p>
      <div className="grid grid-cols-2 gap-3">
        {stats.map((s) => (
          <div
            key={s.label}
            className="p-3 rounded-xl border border-[var(--border)] bg-[var(--card)]/50"
          >
            <div className="text-lg mb-1">{s.icon}</div>
            <div className="text-lg font-bold" style={{ color: s.color }}>
              {s.value}
            </div>
            <div className="text-xs text-[var(--muted)]">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default OverviewTab;
