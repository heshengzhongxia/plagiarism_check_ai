function LeftPanel() {
  return (
    <aside className="w-[300px] shrink-0 border-r border-[var(--border)] bg-[var(--bg)]/40 overflow-y-auto">
      <div className="p-4">
        <h2 className="text-sm font-semibold text-[var(--muted)] uppercase tracking-wider mb-3">
          Agent 流程
        </h2>
        <p className="text-xs text-[var(--muted)]">AgentDAG 可视化面板将在 Task 14 中实现。</p>
      </div>
    </aside>
  );
}

export default LeftPanel;
