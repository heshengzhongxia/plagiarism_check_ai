import { useEffect, useRef } from 'react';
import { useAppStore } from '../../stores/useAppStore';
import AgentMessage from './AgentMessage';
import SystemMessage from './SystemMessage';

function MessageList() {
  const conversation = useAppStore((s) => s.conversation);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation]);

  return (
    <div className="flex-1 overflow-y-auto py-2">
      {conversation.length === 0 && (
        <div className="flex items-center justify-center h-full">
          <p className="text-sm text-[var(--muted)]">
            上传论文并开始分析，Agent 对话将在这里实时显示。
          </p>
        </div>
      )}
      {conversation.map((msg, i) =>
        msg.agent_id === 'system' ? (
          <SystemMessage key={i} msg={msg} />
        ) : (
          <AgentMessage key={i} msg={msg} />
        )
      )}
      <div ref={bottomRef} />
    </div>
  );
}

export default MessageList;
