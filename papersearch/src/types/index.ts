// src/types/index.ts

export type AgentStatus = 'idle' | 'running' | 'done' | 'error';
export type TaskStatus = 'processing' | 'paused' | 'completed' | 'error';

export interface AgentInfo {
  id: string;
  name: string;
  role: string;
  emoji: string;
  color: string;
}

export interface AgentStatusInfo {
  status: AgentStatus;
  progress: number;
}

export interface Message {
  agent_id: string;
  agent_name: string;
  emoji: string;
  color: string;
  message: string;
  timestamp: number;
  needs_confirm?: boolean;
}

export interface MatchResult {
  user_sentence: string;
  similar_sentence: string;
  source_title: string;
  source_url: string;
  similarity: number;
}

export interface Modification {
  user_sentence: string;
  direction: string;
  modified_sentence: string;
  explanation: string;
}

export interface Report {
  report_title: string;
  summary: string;
  risk_assessment: string;
  total_matches: number;
}

export interface TaskConfig {
  auto_mode: boolean;
  sources: string[];
  threshold: number;
  cnki_url?: string;
  cnki_html?: string;
  cnki_papers?: any[];
}

export interface SSEMessage {
  event: string;
  data: Record<string, any>;
}

export const AGENTS_INFO: AgentInfo[] = [
  { id: 'agent1', name: '深析·奥利', role: '论文解析', emoji: '🔍', color: '#5b9bd5' },
  { id: 'agent2', name: '猎手·艾瑞', role: '网络检索', emoji: '🕸️', color: '#f0a040' },
  { id: 'agent3', name: '校验·维拉', role: '逐句查重', emoji: '⚖️', color: '#e0556a' },
  { id: 'agent4', name: '解构·雷欧', role: '修改分析', emoji: '📖', color: '#4caf84' },
  { id: 'agent5', name: '智囊·赛诺', role: '改写方案', emoji: '💡', color: '#f0c060' },
  { id: 'agent6', name: '整合·尤娜', role: '生成报告', emoji: '📋', color: '#a78bfa' },
];
