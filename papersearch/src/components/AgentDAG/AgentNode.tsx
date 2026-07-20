import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { useAppStore } from '../../stores/useAppStore';

interface AgentNodeData {
  agentId: string;
  name: string;
  role: string;
  emoji: string;
  color: string;
}

function AgentNode({ data }: NodeProps<AgentNodeData>) {
  const agentStatus = useAppStore((s) => s.agentsStatus[data.agentId]);
  const status = agentStatus?.status ?? 'idle';

  const statusColors: Record<string, string> = {
    idle: 'rgba(255,255,255,0.12)',
    running: '#f0c060',
    done: '#4caf84',
    error: '#e0556a',
  };

  const borderColor = statusColors[status] || statusColors.idle;
  const pulseClass = status === 'running' ? 'animate-pulse' : '';

  return (
    <div
      className={`${pulseClass} relative px-4 py-3 rounded-xl border-2 bg-[var(--card)] min-w-[160px]`}
      style={{ borderColor }}
    >
      <Handle type="target" position={Position.Top} className="!bg-[var(--muted)]" />
      <div className="flex items-center gap-3">
        <span className="text-2xl">{data.emoji}</span>
        <div>
          <div className="text-sm font-semibold text-[var(--text)]">{data.name}</div>
          <div className="text-xs text-[var(--muted)]">{data.role}</div>
        </div>
      </div>
      <div
        className="absolute top-2 right-2 w-2.5 h-2.5 rounded-full"
        style={{ backgroundColor: borderColor }}
      />
      <Handle type="source" position={Position.Bottom} className="!bg-[var(--muted)]" />
    </div>
  );
}

export default memo(AgentNode);
