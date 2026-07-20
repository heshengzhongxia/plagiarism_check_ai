import AgentDAG from '../AgentDAG/AgentDAG';

function LeftPanel() {
  return (
    <aside className="w-[300px] shrink-0 border-r border-[var(--border)] bg-[var(--bg)]/40 flex flex-col">
      <div className="p-3 border-b border-[var(--border)] shrink-0">
        <h2 className="text-sm font-semibold text-[var(--muted)] uppercase tracking-wider">
          Agent 流程
        </h2>
      </div>
      <div className="flex-1 min-h-0">
        <AgentDAG />
      </div>
    </aside>
  );
}

export default LeftPanel;
