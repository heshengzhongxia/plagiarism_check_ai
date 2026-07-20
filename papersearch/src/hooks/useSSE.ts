// src/hooks/useSSE.ts
import { useEffect, useRef } from 'react';
import { useAppStore } from '../stores/useAppStore';

const API_BASE = 'http://localhost:5001';

export function useSSE(taskId: string | null) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const store = useAppStore();

  useEffect(() => {
    if (!taskId) return;

    const es = new EventSource(`${API_BASE}/api/stream/${taskId}`);
    eventSourceRef.current = es;

    es.addEventListener('agent_start', (e) => {
      const { agent_id, agent_name, emoji, color } = JSON.parse(e.data);
      store.updateAgentStatus(agent_id, 'running', 0);
      store.addMessage({
        agent_id, agent_name, emoji, color,
        message: `${agent_name} 开始工作...`,
        timestamp: Date.now() / 1000,
      });
    });

    es.addEventListener('agent_msg', (e) => {
      const data = JSON.parse(e.data);
      store.addMessage({ ...data, timestamp: data.timestamp || Date.now() / 1000 });
    });

    es.addEventListener('agent_done', (e) => {
      const { agent_id } = JSON.parse(e.data);
      store.updateAgentStatus(agent_id, 'done', 100);
    });

    es.addEventListener('agent_error', (e) => {
      const { agent_id, error } = JSON.parse(e.data);
      store.updateAgentStatus(agent_id, 'error', 0);
      store.addMessage({
        agent_id: 'system', agent_name: '系统', emoji: '❌', color: '#e0556a',
        message: error, timestamp: Date.now() / 1000,
      });
    });

    es.addEventListener('task_progress', (e) => {
      const { batch, pct } = JSON.parse(e.data);
      store.addMessage({
        agent_id: 'system', agent_name: '系统', emoji: '📦', color: '#7b8ca8',
        message: `批次 ${batch} 处理中... (${pct}%)`,
        timestamp: Date.now() / 1000,
      });
    });

    es.addEventListener('task_paused', () => {
      store.setPaused(true);
    });

    es.addEventListener('task_complete', (e) => {
      const { report, docx_ready } = JSON.parse(e.data);
      store.setTaskStatus('completed');
      store.setReport(report);
      store.setDocxReady(docx_ready);
    });

    es.addEventListener('task_error', (e) => {
      const { error } = JSON.parse(e.data);
      store.setTaskStatus('error');
      store.addMessage({
        agent_id: 'system', agent_name: '系统', emoji: '❌', color: '#e0556a',
        message: error, timestamp: Date.now() / 1000,
      });
    });

    es.onerror = () => {
      // EventSource will auto-reconnect
      setTimeout(() => {
        if (es.readyState === EventSource.CLOSED) {
          store.setBackendStatus('error');
        }
      }, 3000);
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [taskId]);
}
