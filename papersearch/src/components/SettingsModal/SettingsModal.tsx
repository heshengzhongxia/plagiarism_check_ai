import { useState, useEffect } from 'react';

const API_BASE = 'http://localhost:5001';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const ALL_SOURCES = [
  { key: 'arxiv', name: 'arXiv' },
  { key: 'semantic_scholar', name: 'Semantic Scholar' },
  { key: 'openalex', name: 'OpenAlex' },
  { key: 'crossref', name: 'Crossref' },
  { key: 'core', name: 'CORE' },
  { key: 'dblp', name: 'DBLP' },
  { key: 'pubmed', name: 'PubMed' },
];

const AGENT_NAMES = ['深析·奥利', '猎手·艾瑞', '校验·维拉', '解构·雷欧', '智囊·赛诺', '整合·尤娜'];

function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [allSame, setAllSame] = useState(false);
  const [masterKey, setMasterKey] = useState('');
  const [keys, setKeys] = useState<string[]>(Array(6).fill(''));
  const [keysMasked, setKeysMasked] = useState<string[]>(Array(6).fill(''));
  const [sources, setSources] = useState<Set<string>>(new Set(ALL_SOURCES.map((s) => s.key)));
  const [threshold, setThreshold] = useState(60);
  const [batchSize, setBatchSize] = useState(10);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // 挂载时从后端加载已保存的 Key
  useEffect(() => {
    if (!isOpen || loaded) return;
    fetch(`${API_BASE}/api/settings`)
      .then(r => r.json())
      .then(data => {
        if (data.any_key) {
          setKeys(data.keys || Array(6).fill(''));
          setKeysMasked(data.keys_masked || Array(6).fill(''));
        }
        // 恢复前端设置
        const local = localStorage.getItem('papersearch-settings');
        if (local) {
          try {
            const s = JSON.parse(local);
            if (s.sources) setSources(new Set(s.sources));
            if (s.threshold) setThreshold(s.threshold);
            if (s.batchSize) setBatchSize(s.batchSize);
          } catch {}
        }
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, [isOpen]);

  if (!isOpen) return null;

  const handleMasterKeyChange = (val: string) => {
    setMasterKey(val);
    if (allSame) {
      setKeys(Array(6).fill(val));
    }
  };

  const handleAllSameToggle = () => {
    if (!allSame) {
      setKeys(Array(6).fill(masterKey));
    }
    setAllSame(!allSame);
  };

  const handleSourceToggle = (key: string) => {
    const next = new Set(sources);
    if (next.has(key)) {
      if (next.size > 1) next.delete(key);
    } else {
      next.add(key);
    }
    setSources(next);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // 发送到后端
      const res = await fetch(`${API_BASE}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keys }),
      });
      const data = await res.json();
      if (data.ok) {
        setKeysMasked(data.keys_masked || []);
      }

      // 前端 localStorage
      localStorage.setItem('papersearch-settings', JSON.stringify({
        sources: Array.from(sources),
        threshold,
        batchSize,
      }));

      onClose();
    } catch (e) {
      console.error('保存设置失败:', e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-[580px] max-h-[80vh] bg-[var(--card)] rounded-2xl border border-[var(--border)] shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
          <h2 className="text-lg font-semibold text-[var(--text)]">⚙️ 设置</h2>
          <button onClick={onClose} className="text-[var(--muted)] hover:text-[var(--text)] text-lg transition-colors">✕</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* API Keys */}
          <section>
            <h3 className="text-sm font-semibold text-[var(--text)] mb-3">🤖 Agent API Keys</h3>
            <div className="flex items-center gap-2 mb-3">
              <input type="checkbox" id="allSame" checked={allSame} onChange={handleAllSameToggle} className="rounded" />
              <label htmlFor="allSame" className="text-xs text-[var(--muted)]">
                所有 Agent 使用相同 API Key
              </label>
            </div>
            {allSame ? (
              <input
                type="password"
                value={masterKey}
                onChange={(e) => handleMasterKeyChange(e.target.value)}
                placeholder="输入 Master API Key"
                className="w-full px-3 py-2 rounded-xl bg-[var(--bg)]/50 border border-[var(--border)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
              />
            ) : (
              <div className="space-y-2">
                {AGENT_NAMES.map((name, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-xs text-[var(--muted)] w-24 shrink-0">Agent {i + 1}</span>
                    <input
                      type="password"
                      value={keys[i]}
                      onChange={(e) => {
                        const next = [...keys];
                        next[i] = e.target.value;
                        setKeys(next);
                      }}
                      placeholder={keysMasked[i] ? `已保存: ${keysMasked[i]}` : `${name} 的 API Key`}
                      className="flex-1 px-3 py-1.5 rounded-lg bg-[var(--bg)]/50 border border-[var(--border)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
                    />
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Paper Sources */}
          <section>
            <h3 className="text-sm font-semibold text-[var(--text)] mb-3">📚 论文数据源</h3>
            <div className="grid grid-cols-2 gap-2">
              {ALL_SOURCES.map((s) => (
                <label
                  key={s.key}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${
                    sources.has(s.key) ? 'border-[var(--accent)] bg-[var(--accent)]/10' : 'border-[var(--border)] bg-[var(--bg)]/30'
                  }`}
                >
                  <input type="checkbox" checked={sources.has(s.key)} onChange={() => handleSourceToggle(s.key)} className="rounded" />
                  <span className="text-sm text-[var(--text)]">{s.name}</span>
                </label>
              ))}
            </div>
          </section>

          {/* Threshold */}
          <section>
            <h3 className="text-sm font-semibold text-[var(--text)] mb-3">
              🎯 相似度阈值: <span className="text-[var(--accent)]">{threshold}%</span>
            </h3>
            <input type="range" min={40} max={90} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} className="w-full accent-[var(--accent)]" />
          </section>

          {/* Batch Size */}
          <section>
            <h3 className="text-sm font-semibold text-[var(--text)] mb-3">📦 批处理大小</h3>
            <input type="number" min={5} max={20} value={batchSize} onChange={(e) => setBatchSize(Number(e.target.value))} className="w-24 px-3 py-2 rounded-xl bg-[var(--bg)]/50 border border-[var(--border)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)]" />
          </section>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-5 py-4 border-t border-[var(--border)]">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-xl bg-[var(--card)]/50 text-[var(--muted)] hover:bg-[var(--card)]/80 transition-colors border border-[var(--border)]">取消</button>
          <button onClick={handleSave} disabled={saving} className="px-5 py-2 text-sm rounded-xl bg-[var(--accent)] text-white hover:bg-[var(--accent)]/80 transition-colors font-medium disabled:opacity-50">
            {saving ? '保存中...' : '保存设置'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default SettingsModal;
