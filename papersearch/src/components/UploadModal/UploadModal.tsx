import { useState, useRef, useCallback } from 'react';

const API_BASE = 'http://localhost:5001';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTextReady: (text: string) => void;
}

function UploadModal({ isOpen, onClose, onTextReady }: UploadModalProps) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [extractedText, setExtractedText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = useCallback(async (file: File) => {
    setUploading(true);
    setError(null);
    setFileName(file.name);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setExtractedText(data.text || '');
      }
    } catch (e) {
      setError('上传失败，请检查后端服务是否运行。');
    } finally {
      setUploading(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  }, [handleUpload]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  }, [handleUpload]);

  if (!isOpen) return null;

  const formatIcon = (name: string) => {
    if (name.endsWith('.pdf')) return '📕';
    if (name.endsWith('.docx') || name.endsWith('.doc')) return '📘';
    return '📄';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-[560px] max-h-[80vh] bg-[var(--card)] rounded-2xl border border-[var(--border)] shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
          <h2 className="text-lg font-semibold text-[var(--text)]">📤 上传论文</h2>
          <button
            onClick={onClose}
            className="text-[var(--muted)] hover:text-[var(--text)] text-lg transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {!fileName && (
            <div
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onClick={() => fileInputRef.current?.click()}
              className={`flex flex-col items-center justify-center h-48 border-2 border-dashed rounded-xl cursor-pointer transition-colors ${
                dragOver
                  ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                  : 'border-[var(--border)] hover:border-[var(--muted)]'
              }`}
            >
              <span className="text-3xl mb-2">📂</span>
              <span className="text-sm text-[var(--muted)]">
                拖拽文件到此处，或点击选择文件
              </span>
              <span className="text-xs text-[var(--muted)] mt-1">
                支持 PDF / Word / TXT
              </span>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc,.txt"
                onChange={handleFileSelect}
                className="hidden"
              />
            </div>
          )}

          {uploading && (
            <div className="flex items-center justify-center py-8">
              <div className="w-8 h-8 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
              <span className="ml-3 text-sm text-[var(--muted)]">正在解析文件...</span>
            </div>
          )}

          {error && (
            <div className="p-3 rounded-xl bg-[var(--danger)]/10 border border-[var(--danger)]/30 text-sm text-[var(--danger)]">
              {error}
            </div>
          )}

          {fileName && !uploading && !error && (
            <div className="flex items-center gap-3 p-3 rounded-xl bg-[var(--bg)]/50">
              <span className="text-2xl">{formatIcon(fileName)}</span>
              <span className="text-sm text-[var(--text)] truncate flex-1">{fileName}</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--success)]/20 text-[var(--success)]">
                已解析
              </span>
            </div>
          )}

          {extractedText && (
            <textarea
              value={extractedText}
              onChange={(e) => setExtractedText(e.target.value)}
              className="w-full h-48 p-3 rounded-xl bg-[var(--bg)]/50 border border-[var(--border)] text-sm text-[var(--text)] resize-none focus:outline-none focus:border-[var(--accent)]"
              placeholder="提取的论文文本..."
            />
          )}
        </div>

        {/* Footer */}
        {extractedText && (
          <div className="flex justify-end gap-2 px-5 py-4 border-t border-[var(--border)]">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm rounded-xl bg-[var(--card)]/50 text-[var(--muted)] hover:bg-[var(--card)]/80 transition-colors border border-[var(--border)]"
            >
              取消
            </button>
            <button
              onClick={() => onTextReady(extractedText)}
              className="px-5 py-2 text-sm rounded-xl bg-[var(--accent)] text-white hover:bg-[var(--accent)]/80 transition-colors font-medium"
            >
              🚀 开始分析
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default UploadModal;
