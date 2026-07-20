import ReportPanel from '../ReportPanel/ReportPanel';

function RightPanel() {
  return (
    <aside className="w-[360px] shrink-0 border-l border-[var(--border)] bg-[var(--bg)]/40">
      <div className="p-3 border-b border-[var(--border)] shrink-0">
        <h2 className="text-sm font-semibold text-[var(--muted)] uppercase tracking-wider">
          报告
        </h2>
      </div>
      <ReportPanel />
    </aside>
  );
}

export default RightPanel;
