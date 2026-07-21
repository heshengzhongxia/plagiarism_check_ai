// src/hooks/useSSE.ts
import { useEffect, useRef } from 'react';
import { useAppStore } from '../stores/useAppStore';

const API_BASE = 'http://localhost:5001';

export function useSSE(taskId: string | null) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const store = useAppStore();

  useEffect(() => {
    if (!taskId) return;

    // 先拉取当前状态，避免 SSE 连接前任务已跑完的竞态
    fetch(`${API_BASE}/api/status/${taskId}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.status === 'completed') {
          store.setTaskStatus('completed');
          if (data.report) {
            store.setReport(data.report);
            // 从 agent_results 中提取 modifications
            if (data.report.modifications) {
              store.setModifications(data.report.modifications);
            }
          }
          store.setDocxReady(data.docx_ready || false);
          return; // 任务已完成，无需建立 SSE
        }
        if (data.status === 'error') {
          store.setTaskStatus('error');
          return;
        }
      })
      .catch(() => {});

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
      // 设置修改方案
      if (report?.modifications) {
        store.setModifications(report.modifications);
      }
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
