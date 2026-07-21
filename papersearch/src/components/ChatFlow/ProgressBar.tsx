import { useAppStore } from '../../stores/useAppStore';

function ProgressBar() {
  const taskStatus = useAppStore((s) => s.taskStatus);
  const agentsStatus = useAppStore((s) => s.agentsStatus);

  if (taskStatus !== 'processing' && taskStatus !== 'paused') return null;

  // Calculate overall progress from agent statuses
  const agentStates = Object.values(agentsStatus);
  const doneCount = agentStates.filter(a => a.status === 'done').length;
  const progressPct = agentStates.length > 0
    ? Math.round((doneCount / agentStates.length) * 100)
    : 0;

  return (
    <div className="px-4 py-2 border-t border-[var(--border)] shrink-0">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs text-[var(--muted)]">总体进度</span>
        <span className="text-xs text-[var(--accent)] font-medium">{progressPct}%</span>
      </div>
      <div className="w-full h-1.5 bg-[var(--bg)] rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-[var(--accent)] to-[var(--purple)] rounded-full transition-all duration-500 ease-out"
          style={{ width: `${Math.max(progressPct, 5)}%` }}
        />
      </div>
    </div>
  );
}

export default ProgressBar;
