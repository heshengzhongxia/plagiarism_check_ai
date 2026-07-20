import type { Message } from '../../types';

interface SystemMessageProps {
  msg: Message;
}

function SystemMessage({ msg }: SystemMessageProps) {
  return (
    <div className="flex justify-center px-4 py-1.5">
      <span className="text-xs text-[var(--muted)] italic">
        {msg.emoji} {msg.message}
      </span>
    </div>
  );
}

export default SystemMessage;
