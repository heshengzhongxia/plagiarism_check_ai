import type { Message } from '../../types';

interface AgentMessageProps {
  msg: Message;
}

function AgentMessage({ msg }: AgentMessageProps) {
  return (
    <div className="flex items-start gap-3 px-4 py-2 animate-[fadeIn_0.3s_ease-out]">
      <div
        className="w-9 h-9 rounded-full flex items-center justify-center text-base shrink-0"
        style={{ backgroundColor: msg.color + '22', color: msg.color }}
      >
        {msg.emoji}
      </div>
      <div className="flex flex-col min-w-0">
        <span className="text-xs font-medium mb-0.5" style={{ color: msg.color }}>
          {msg.agent_name}
        </span>
        <div className="text-sm text-[var(--text)] bg-[var(--card)]/60 rounded-xl rounded-tl-sm px-3 py-2 leading-relaxed break-words">
          {msg.message}
        </div>
        {msg.needs_confirm && (
          <span className="text-xs text-[var(--gold)] mt-1">⏸ 等待确认</span>
        )}
      </div>
    </div>
  );
}

export default AgentMessage;
