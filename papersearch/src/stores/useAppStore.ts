// src/stores/useAppStore.ts
import { create } from 'zustand';
import type { AgentStatusInfo, Message, Report, Modification, TaskConfig } from '../types';

interface AppState {
  currentTaskId: string | null;
  taskStatus: 'idle' | 'processing' | 'paused' | 'completed' | 'error';
  autoMode: boolean;
  agentsStatus: Record<string, AgentStatusInfo>;
  conversation: Message[];
  report: Report | null;
  modifications: Modification[];
  docxReady: boolean;
  backendStatus: 'starting' | 'running' | 'stopped' | 'error';

  startTask: (taskId: string, config: TaskConfig) => void;
  updateAgentStatus: (agentId: string, status: string, progress: number) => void;
  addMessage: (msg: Message) => void;
  setReport: (report: Report) => void;
  setModifications: (mods: Modification[]) => void;
  setDocxReady: (ready: boolean) => void;
  setTaskStatus: (status: AppState['taskStatus']) => void;
  setBackendStatus: (status: AppState['backendStatus']) => void;
  setPaused: (paused: boolean) => void;
  resetTask: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentTaskId: null,
  taskStatus: 'idle',
  autoMode: true,
  agentsStatus: {},
  conversation: [],
  report: null,
  modifications: [],
  docxReady: false,
  backendStatus: 'starting',

  startTask: (taskId, config) => set({
    currentTaskId: taskId,
    taskStatus: 'processing',
    autoMode: config.auto_mode,
    conversation: [],
    report: null,
    modifications: [],
    docxReady: false,
    agentsStatus: Object.fromEntries(
      ['agent1','agent2','agent3','agent4','agent5','agent6'].map(id => [
        id, { status: 'idle', progress: 0 }
      ])
    ),
  }),

  updateAgentStatus: (agentId, status, progress) => set((state) => ({
    agentsStatus: {
      ...state.agentsStatus,
      [agentId]: { status: status as AgentStatusInfo['status'], progress },
    },
  })),

  addMessage: (msg) => set((state) => ({
    conversation: [...state.conversation, msg],
  })),

  setReport: (report) => set({ report }),
  setModifications: (modifications) => set({ modifications }),
  setDocxReady: (docxReady) => set({ docxReady }),
  setTaskStatus: (taskStatus) => set({ taskStatus }),
  setBackendStatus: (backendStatus) => set({ backendStatus }),
  setPaused: (paused) => set({ taskStatus: paused ? 'paused' : 'processing' }),
  resetTask: () => set({
    currentTaskId: null, taskStatus: 'idle',
    conversation: [], report: null, modifications: [], docxReady: false,
    agentsStatus: {},
  }),
}));
