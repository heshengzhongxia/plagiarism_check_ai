import { useAppStore } from '../../stores/useAppStore';

function ExportTab() {
  const docxReady = useAppStore((s) => s.docxReady);
  const currentTaskId = useAppStore((s) => s.currentTaskId);
  const report = useAppStore((s) => s.report);

  const handleDownload = () => {
    if (!docxReady || !currentTaskId) return;
    window.open(`http://localhost:5001/api/download/${currentTaskId}`);
  };

  const handleCopy = async () => {
    if (!report) return;
    const text = `查重报告: ${report.report_title}\n摘要: ${report.summary}\n风险等级: ${report.risk_assessment}\n总重复数: ${report.total_matches}`;
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {
      console.error('Copy failed:', e);
    }
  };

  return (
    <div className="space-y-3">
      <button
        onClick={handleDownload}
        disabled={!docxReady}
        className={`w-full py-3 rounded-xl text-sm font-medium transition-all ${
          docxReady
            ? 'bg-[var(--accent)] text-white hover:bg-[var(--accent)]/80 cursor-pointer'
            : 'bg-[var(--card)]/50 text-[var(--muted)] cursor-not-allowed'
        }`}
      >
        {docxReady ? '📥 下载 DOCX 报告' : '📥 DOCX 报告（任务完成后生成）'}
      </button>
      <button
        onClick={handleCopy}
        disabled={!report}
        className="w-full py-2.5 rounded-xl text-sm font-medium bg-[var(--card)]/50 text-[var(--text)] hover:bg-[var(--card)]/80 transition-all border border-[var(--border)] disabled:cursor-not-allowed disabled:text-[var(--muted)]"
      >
        📋 复制报告文本
      </button>
    </div>
  );
}

export default ExportTab;
