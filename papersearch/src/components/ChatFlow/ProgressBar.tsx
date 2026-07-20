import { useAppStore } from '../../stores/useAppStore';

function ProgressBar() {
  const taskStatus = useAppStore((s) => s.taskStatus);

  if (taskStatus !== 'processing' && taskStatus !== 'paused') return null;

  return (
    <div className="px-4 py-2 border-t border-[var(--border)] shrink-0">
      <div className="w-full h-1.5 bg-[var(--bg)] rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-[var(--accent)] to-[var(--purple)] rounded-full transition-all duration-500 ease-out"
          style={{ width: '100%' }}
        />
      </div>
    </div>
  );
}

export default ProgressBar;
