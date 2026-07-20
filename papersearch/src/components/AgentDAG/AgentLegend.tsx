const STATUS_ITEMS = [
  { status: 'idle', label: '空闲', color: 'rgba(255,255,255,0.2)' },
  { status: 'running', label: '运行中', color: '#f0c060' },
  { status: 'done', label: '已完成', color: '#4caf84' },
  { status: 'error', label: '错误', color: '#e0556a' },
];

function AgentLegend() {
  return (
    <div className="flex items-center justify-center gap-4 p-2 border-t border-[var(--border)] shrink-0">
      {STATUS_ITEMS.map((item) => (
        <div key={item.status} className="flex items-center gap-1.5">
          <div
            className="w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: item.color }}
          />
          <span className="text-xs text-[var(--muted)]">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

export default AgentLegend;
