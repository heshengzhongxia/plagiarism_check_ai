import { useState } from 'react';
import { useAppStore } from '../../stores/useAppStore';
import OverviewTab from './OverviewTab';
import ModificationsTab from './ModificationsTab';
import ExportTab from './ExportTab';

const TABS = [
  { key: 'overview', label: '概览' },
  { key: 'modifications', label: '修改方案' },
  { key: 'export', label: '导出' },
];

function ReportPanel() {
  const [tab, setTab] = useState('overview');
  const taskStatus = useAppStore((s) => s.taskStatus);

  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-[var(--border)] shrink-0">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 py-2.5 text-sm font-medium transition-colors ${
              tab === t.key
                ? 'text-[var(--accent)] border-b-2 border-[var(--accent)]'
                : 'text-[var(--muted)] hover:text-[var(--text)]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {taskStatus === 'idle' && (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-[var(--muted)]">启动任务后，报告将在此显示。</p>
          </div>
        )}
        {tab === 'overview' && <OverviewTab />}
        {tab === 'modifications' && <ModificationsTab />}
        {tab === 'export' && <ExportTab />}
      </div>
    </div>
  );
}

export default ReportPanel;
