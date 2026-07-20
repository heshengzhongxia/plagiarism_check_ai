# 六智Agent论文工坊 — 桌面应用重设计实现计划

> **For agentic workers:** 使用 superpowers:subagent-driven-development 来逐个任务实现。步骤使用 checkbox (`- [ ]`) 语法追踪。

**目标：** 将现有的 Flask + 原生 HTML 论文查重系统重构为 Electron 桌面应用，包含 React 三栏前端 + 分层 Python 后端 + SSE 实时推送。

**架构：** Electron 主进程管理窗口和 Python 子进程生命周期；React 前端通过 REST + SSE 与 Python 后端通信；Python 后端拆分为路由层、Pipeline 编排层、Agent 引擎层、外部服务层四层；SQLite 持久化任务状态。

**技术栈：** React 18 + TypeScript + TailwindCSS + Zustand + ReactFlow + Vite | Flask + flask-cors | SQLite | Electron + electron-builder | Python 3.10+

## 全局约束

- Python >= 3.10，Flask >= 3.0，flask-cors >= 4.0
- 所有 API Key 从 `.env` 文件读取，禁止硬编码
- 6 个 Agent 的业务逻辑保持不变，仅重构调用路径
- 7 个论文 API 源必须全部保留
- 暗色主题贯穿所有 UI 组件
- 桌面应用 Windows 优先（NSIS 安装包）
- 前端构建产物输出到 `dist/`，Electron 打包输出到 `dist-electron/`

---

## 阶段一：Python 后端分层重构

### Task 1: 创建 .env.example 和重写 config.py

**Files:**
- Create: `papersearch/.env.example`
- Modify: `papersearch/config.py`

- [ ] **Step 1: 创建 .env.example**

```bash
# LLM 配置（每个Agent可独立配置）
DEEPSEEK_API_KEY_AGENT1=sk-your-key-here
DEEPSEEK_API_KEY_AGENT2=sk-your-key-here
DEEPSEEK_API_KEY_AGENT3=sk-your-key-here
DEEPSEEK_API_KEY_AGENT4=sk-your-key-here
DEEPSEEK_API_KEY_AGENT5=sk-your-key-here
DEEPSEEK_API_KEY_AGENT6=sk-your-key-here
DEEPSEEK_MODEL=deepseek-chat

# 服务配置
PAPER_PORT=5001
FLASK_DEBUG=false

# 论文源（逗号分隔）
DEFAULT_SOURCES=arxiv,semantic_scholar,openalex,crossref,core,dblp,pubmed

# 查重配置
DEFAULT_THRESHOLD=60
BATCH_SIZE=10
```

- [ ] **Step 2: 重写 config.py**

将 `papersearch/config.py` 完整替换为从 `.env` 加载配置的版本。`load_config()` 返回的 `AGENTS_CONFIG` 字典结构保持不变（每个 agent 含 id, name, role, emoji, color, api_key, model, temperature, system_prompt），但 api_key 改为从环境变量读取。新增：`PAPER_PORT`, `DEFAULT_SOURCES`, `DEFAULT_THRESHOLD`, `BATCH_SIZE`, `DB_PATH` 常量。

- [ ] **Step 3: 验证配置**

```bash
cd papersearch && python -c "from config import AGENTS_CONFIG, PAPER_PORT; print(f'Port: {PAPER_PORT}, Agents: {len(AGENTS_CONFIG)}')"
```

- [ ] **Step 4: 提交**

```bash
git add papersearch/.env.example papersearch/config.py
git commit -m "refactor: extract config to .env, remove hardcoded API keys"
```

### Task 2: 创建 SSE Broker

**Files:**
- Create: `papersearch/engine/__init__.py`
- Create: `papersearch/engine/sse_broker.py`

**Interfaces:**
- Produces: `SSEBroker` 类 — `subscribe(task_id) -> queue.Queue`, `publish(task_id, event, data)`, `unsubscribe(task_id)`

- [ ] **Step 1: 创建 engine 包**

创建 `papersearch/engine/__init__.py`（空文件）

- [ ] **Step 2: 实现 SSEBroker**

```python
# papersearch/engine/sse_broker.py
import queue
import threading

class SSEBroker:
    """线程安全的事件队列"""

    def __init__(self):
        self._queues: dict[str, queue.Queue] = {}
        self._lock = threading.Lock()

    def subscribe(self, task_id: str) -> queue.Queue:
        with self._lock:
            q = queue.Queue()
            self._queues[task_id] = q
            return q

    def publish(self, task_id: str, event: str, data: dict) -> None:
        with self._lock:
            q = self._queues.get(task_id)
        if q:
            q.put({"event": event, "data": data})

    def unsubscribe(self, task_id: str) -> None:
        with self._lock:
            self._queues.pop(task_id, None)

# 全局单例
sse_broker = SSEBroker()
```

- [ ] **Step 3: 验证**

```bash
cd papersearch && python -c "
from engine.sse_broker import sse_broker
import queue
q = sse_broker.subscribe('test')
sse_broker.publish('test', 'agent_start', {'agent_id': 'agent1'})
msg = q.get(timeout=2)
assert msg['event'] == 'agent_start'
print('SSEBroker OK')
"
```

- [ ] **Step 4: 提交**

```bash
git add papersearch/engine/__init__.py papersearch/engine/sse_broker.py
git commit -m "feat: add SSE broker for real-time event streaming"
```

### Task 3: 创建 TaskManager（SQLite 持久化）

**Files:**
- Create: `papersearch/store/__init__.py`
- Create: `papersearch/store/schema.sql`
- Create: `papersearch/store/repository.py`
- Create: `papersearch/engine/task_manager.py`

- [ ] **Step 1: 创建 store 包和 SQL schema**

`papersearch/store/__init__.py`（空文件）

`papersearch/store/schema.sql`：

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'processing',
    auto_mode INTEGER NOT NULL DEFAULT 1,
    threshold INTEGER NOT NULL DEFAULT 60,
    paper_title TEXT,
    agents_status TEXT DEFAULT '{}',
    agent_results TEXT DEFAULT '{}',
    final_report TEXT,
    docx_path TEXT,
    cnki_task_id TEXT,
    batch_progress TEXT DEFAULT '',
    batch_pct INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    agent_name TEXT,
    emoji TEXT,
    color TEXT,
    message TEXT,
    timestamp REAL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_task ON task_messages(task_id);
CREATE INDEX IF NOT EXISTS idx_messages_since ON task_messages(task_id, id);
```

- [ ] **Step 2: 实现 Repository 数据访问层**

`papersearch/store/repository.py` — 提供 `Repository` 类，方法包括：`create_task()`, `update_task()`, `get_task()`, `add_message()`, `get_messages()`, `list_tasks()`, `delete_task()`, `cleanup_old()`。内部使用 `sqlite3.connect()` 和参数化查询。

- [ ] **Step 3: 实现 TaskManager**

`papersearch/engine/task_manager.py` — 包装 Repository，提供高层接口：

```python
class TaskManager:
    def __init__(self, db_path: str): ...
    def create_task(self, task_id: str, config: dict) -> None: ...
    def update_agent_status(self, task_id: str, agent_id: str, status: str, progress: int) -> None: ...
    def add_message(self, task_id: str, msg: dict) -> None: ...
    def get_status(self, task_id: str) -> dict | None: ...
    def set_report(self, task_id: str, report: dict, docx_path: str | None) -> None: ...
    def list_history(self, limit: int = 50) -> list[dict]: ...
    def delete_task(self, task_id: str) -> None: ...
```

- [ ] **Step 4: 验证**

```bash
cd papersearch && python -c "
from engine.task_manager import TaskManager
import tempfile, os
db = os.path.join(tempfile.gettempdir(), 'test_task.db')
tm = TaskManager(db)
tm.create_task('test1', {'auto_mode': True, 'threshold': 60})
t = tm.get_status('test1')
assert t['status'] == 'processing'
tm.add_message('test1', {'agent_id': 'system', 'agent_name': 'System', 'emoji': 'G', 'color': '#fff', 'message': 'hello', 'timestamp': 123.0})
msgs = tm.get_messages('test1')
assert len(msgs) == 1
print('TaskManager OK')
"
```

- [ ] **Step 5: 提交**

```bash
git add papersearch/store/ papersearch/engine/task_manager.py
git commit -m "feat: add TaskManager with SQLite persistence"
```

### Task 4: 抽取文件解析服务

**Files:**
- Create: `papersearch/services/__init__.py`
- Create: `papersearch/services/file_parser.py`

- [ ] **Step 1: 从 server.py 抽取文件解析逻辑**

将 `server.py` 中的 `extract_text_from_pdf()`, `extract_text_from_docx()`, `extract_text()` 三个函数移动到 `papersearch/services/file_parser.py`，保持函数签名和实现完全不变。

- [ ] **Step 2: 添加测试验证**

```bash
cd papersearch && python -c "
from services.file_parser import extract_text_from_pdf, extract_text_from_docx, extract_text
# 创建一个简单测试
import tempfile
f = tempfile.NamedTemporaryFile(suffix='.txt', mode='w', delete=False)
f.write('测试文本内容')
f.close()
result = extract_text(f.name, 'test.txt')
import os; os.unlink(f.name)
assert result == '测试文本内容'
print('File parser OK')
"
```

- [ ] **Step 3: 提交**

```bash
git add papersearch/services/__init__.py papersearch/services/file_parser.py
git commit -m "refactor: extract file parser to services layer"
```

### Task 5: 移动论文 API 服务

- [ ] **Step 1: 将 paper_apis.py 移到 services/**

```bash
cd papersearch
git mv paper_apis.py services/paper_api.py
```

- [ ] **Step 2: 验证**

```bash
cd papersearch && python -c "from services.paper_api import ALL_SOURCES, search_all; print(f'Sources: {len(ALL_SOURCES)}')"
```

- [ ] **Step 3: 提交**

```bash
git add papersearch/services/paper_api.py papersearch/paper_apis.py
git commit -m "refactor: move paper API to services layer"
```

### Task 6: 抽取 DOCX 生成服务

- [ ] **Step 1: 将 DOCX 生成逻辑从 agent6 移到 services/docx_generator.py**

从 `papersearch/agents/agent6_integrator.py` 中抽取 `generate_docx()` 函数和 `_set_font()` 辅助函数到 `papersearch/services/docx_generator.py`。保持实现不变。

- [ ] **Step 2: 修改 agent6_integrator.py 导入新路径**

```python
from services.docx_generator import generate_docx
```

- [ ] **Step 3: 验证**

```bash
cd papersearch && python -c "from services.docx_generator import generate_docx; print('DOCX generator OK')"
```

- [ ] **Step 4: 提交**

```bash
git add papersearch/services/docx_generator.py papersearch/agents/agent6_integrator.py
git commit -m "refactor: extract DOCX generation to services layer"
```

### Task 7: 创建路由层 — 拆分 API 端点

**Files:**
- Create: `papersearch/routes/__init__.py`
- Create: `papersearch/routes/task_routes.py`
- Create: `papersearch/routes/upload_routes.py`
- Create: `papersearch/routes/report_routes.py`
- Create: `papersearch/routes/cnki_routes.py`

- [ ] **Step 1: 创建路由包**

`papersearch/routes/__init__.py` 导出 `register_routes(app)` 函数，调用各子模块的注册函数。

- [ ] **Step 2: 实现 upload_routes.py**

包含 `POST /api/upload`（文件上传解析）和 `POST /api/keywords`（仅提取关键词）。从 server.py 迁移对应代码。依赖 `services/file_parser.py`。

- [ ] **Step 3: 实现 task_routes.py**

包含：
- `POST /api/start` — 启动查重流水线
- `GET /api/status/<task_id>` — 任务状态快照
- `GET /api/stream/<task_id>` — SSE 实时事件流
- `POST /api/confirm/<task_id>` — 手动模式确认
- `POST /api/retry/<task_id>` — 重试当前 Agent

SSE 端点实现：

```python
from flask import Response, stream_with_context, Blueprint
from engine.sse_broker import sse_broker
import json, queue

task_bp = Blueprint('task', __name__)

@task_bp.route('/api/stream/<task_id>')
def stream(task_id):
    q = sse_broker.subscribe(task_id)
    def generate():
        try:
            while True:
                msg = q.get(timeout=30)
                yield f"event: {msg['event']}\n"
                yield f"data: {json.dumps(msg['data'], ensure_ascii=False)}\n\n"
                if msg['event'] in ('task_complete', 'task_error'):
                    break
        except queue.Empty:
            yield "event: heartbeat\ndata: {}\n\n"
        finally:
            sse_broker.unsubscribe(task_id)
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )
```

- [ ] **Step 4: 实现 report_routes.py**

包含 `GET /api/report/<task_id>`, `GET /api/download/<task_id>`, `GET /api/history`, `DELETE /api/history/<task_id>`。

- [ ] **Step 5: 实现 cnki_routes.py**

从 server.py 迁移知网爬虫相关路由（/api/cnki/start, /api/cnki/status, /api/cnki/solve, /api/cnki/download, /api/cnki/parse）。

- [ ] **Step 6: 提交**

```bash
git add papersearch/routes/
git commit -m "refactor: split API routes into separate modules"
```

### Task 8: 创建 Pipeline 编排模块

**Files:**
- Create: `papersearch/engine/pipeline.py`
- Modify: `papersearch/server.py`（精简入口）

- [ ] **Step 1: 从 server.py 抽取 pipeline**

将 `server.py` 中的 `execute_pipeline()`, `_update()`, `_wait_confirm()` 函数移动到 `papersearch/engine/pipeline.py`。修改函数签名以接收 `TaskManager` 和 `SSEBroker` 作为参数。

`execute_pipeline(task_id, paper_text, auto_mode, threshold, task_manager, sse_broker, agents_config, reports_dir)` — Agent 执行过程中通过 `sse_broker.publish()` 推送事件，通过 `task_manager` 读写状态。保持 DAG 执行顺序不变。

- [ ] **Step 2: 精简 server.py**

server.py 变为仅 ~50 行的入口文件：

```python
"""六智Agent论文工坊 - 入口"""
import os, sys, threading, time
from flask import Flask, send_from_directory
from flask_cors import CORS
from config import AGENTS_CONFIG, PAPER_PORT, DB_PATH
from routes import register_routes
from engine.task_manager import TaskManager
from engine.sse_broker import sse_broker

app = Flask(__name__, static_folder='.')
CORS(app)
task_manager = TaskManager(DB_PATH)

register_routes(app, task_manager, sse_broker, AGENTS_CONFIG)

# 健康检查
@app.route('/api/health')
def health():
    return {"status": "ok", "agents": len(AGENTS_CONFIG)}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    # ... 启动逻辑
    app.run(debug=False, host='0.0.0.0', port=PAPER_PORT)
```

- [ ] **Step 3: 验证端到端**

```bash
cd papersearch && python app.py &
sleep 2
curl -s http://localhost:5001/api/health | python -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok'; print('Health OK')"
kill %1
```

- [ ] **Step 4: 提交**

```bash
git add papersearch/engine/pipeline.py papersearch/app.py papersearch/server.py
git commit -m "refactor: extract pipeline engine, create clean Flask entry point"
```

---

## 阶段二：React 前端

### Task 9: 初始化 Vite + React + TypeScript 项目

- [ ] **Step 1: 在项目根目录创建前端项目**

```bash
cd papersearch
npm create vite@latest . -- --template react-ts --force
npm install
```

- [ ] **Step 2: 安装依赖**

```bash
npm install zustand reactflow tailwindcss @tailwindcss/vite
```

- [ ] **Step 3: 配置 TailwindCSS + 暗色主题**

更新 `vite.config.ts` 添加 tailwind 插件。创建 `src/index.css`：

```css
@import "tailwindcss";

:root {
  --bg: #0f1119;
  --card: #1a1e2b;
  --text: #e0e6f0;
  --muted: #7b8ca8;
  --border: rgba(255,255,255,0.08);
  --accent: #5b9bd5;
  --gold: #f0c060;
  --danger: #e0556a;
  --success: #4caf84;
  --purple: #a78bfa;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  background: linear-gradient(160deg, #0a0d15 0%, #151b28 40%, #1a1f30 100%);
  color: var(--text);
  font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
  height: 100vh;
  overflow: hidden;
}
```

- [ ] **Step 4: 验证项目启动**

```bash
npm run dev
# 浏览器打开 http://localhost:5173 看到空白页面即成功
```

- [ ] **Step 5: 提交**

```bash
git add src/ package.json package-lock.json tsconfig.json vite.config.ts index.html
git commit -m "feat: initialize React + Vite + TypeScript + TailwindCSS project"
```

### Task 10: 定义 TypeScript 类型

**Files:**
- Create: `src/types/index.ts`

- [ ] **Step 1: 编写所有类型定义**

```typescript
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
```

- [ ] **Step 2: 提交**

```bash
git add src/types/index.ts
git commit -m "feat: define TypeScript types for agent and task data"
```

### Task 11: 创建 Zustand Store

**Files:**
- Create: `src/stores/useAppStore.ts`

包含完整的状态接口：`currentTaskId`, `taskStatus`, `autoMode`, `agentsStatus`, `conversation`, `report`, `modifications`, `docxReady`, `backendStatus`，以及 actions：`startTask`, `confirmAgent`, `retryAgent`, `resetTask`, `setBackendStatus`, `updateFromSSE`。

- [ ] **Step 1: 实现 store**

```typescript
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
```

- [ ] **Step 2: 提交**

```bash
git add src/stores/useAppStore.ts
git commit -m "feat: implement Zustand store for app state management"
```

### Task 12: 创建 SSE Hook

**Files:**
- Create: `src/hooks/useSSE.ts`

- [ ] **Step 1: 实现 useSSE hook**

```typescript
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
```

- [ ] **Step 2: 提交**

```bash
git add src/hooks/useSSE.ts
git commit -m "feat: implement SSE hook for real-time agent event streaming"
```

### Task 13: 实现 App 布局和顶部导航栏

**Files:**
- Create: `src/components/Layout/TopNavBar.tsx`
- Create: `src/components/Layout/MainLayout.tsx`
- Modify: `src/App.tsx`

- [ ] **Step 1: 实现 TopNavBar**

顶部导航栏包含：应用标题（六智Agent论文工坊）、上传论文按钮、新建任务按钮、设置按钮、历史按钮。使用 TailwindCSS 暗色样式。logo 左侧，按钮右侧。

- [ ] **Step 2: 实现 MainLayout**

三栏布局容器，左右可调整宽度（左侧 300px 固定，右侧 360px 固定，中间弹性）。各面板用 `border-r` / `border-l` 分隔。使用 `overflow-y-auto` 允许独立滚动。

- [ ] **Step 3: 组装 App 组件**

```tsx
function App() {
  return (
    <div className="flex flex-col h-screen">
      <TopNavBar />
      <MainLayout>
        <LeftPanel />   {/* AgentDAG */}
        <CenterPanel /> {/* ChatFlow */}
        <RightPanel />  {/* Report */}
      </MainLayout>
      <StatusBar />
    </div>
  );
}
```

- [ ] **Step 4: 提交**

```bash
git add src/components/Layout/ src/App.tsx
git commit -m "feat: implement app layout with three-panel design"
```

### Task 14: 实现 AgentDAG 可视化面板

**Files:**
- Create: `src/components/AgentDAG/AgentDAG.tsx`
- Create: `src/components/AgentDAG/AgentNode.tsx`
- Create: `src/components/AgentDAG/AgentLegend.tsx`

- [ ] **Step 1: 实现自定义 AgentNode**

使用 ReactFlow 的自定义节点。每个节点显示 emoji、Agent 名称、角色。节点边框颜色根据状态变化（idle: 灰色, running: 金色脉冲动画, done: 绿色, error: 红色）。节点右上角显示状态指示灯。

- [ ] **Step 2: 实现 AgentDAG 画布**

按照 DAG 依赖关系排列 6 个节点：
- agent1（解析）在顶部居中
- agent2（检索）和 agent6（报告）在第二行，agent2 连接 agent1
- agent3（查重）在第三行，连接 agent1 和 agent2
- agent4（分析）和 agent6 在第四行，连接 agent3
- agent5（方案）在第五行，连接 agent4，出边到 agent6

使用 ReactFlow 的 `nodeTypes` 和 `edgeTypes`，节点不可拖拽，只展示状态。

- [ ] **Step 3: 实现 AgentLegend**

底部图例显示四种状态的图标和文字说明。

- [ ] **Step 4: 提交**

```bash
git add src/components/AgentDAG/
git commit -m "feat: implement Agent DAG visualization with ReactFlow"
```

### Task 15: 实现实时对话流面板

**Files:**
- Create: `src/components/ChatFlow/ChatFlow.tsx`
- Create: `src/components/ChatFlow/MessageList.tsx`
- Create: `src/components/ChatFlow/AgentMessage.tsx`
- Create: `src/components/ChatFlow/SystemMessage.tsx`
- Create: `src/components/ChatFlow/ControlBar.tsx`
- Create: `src/components/ChatFlow/ProgressBar.tsx`

- [ ] **Step 1: 实现 AgentMessage 和 SystemMessage**

AgentMessage：左侧圆角头像（emoji + 背景色），右侧气泡（Agent 名称 + 消息内容）。暗色半透明背景气泡，动画淡入效果。

SystemMessage：居中灰色文字，小号字体，斜体。

- [ ] **Step 2: 实现 MessageList**

用 `useRef` + `useEffect` 自动滚动到底部。从 store 读取 `conversation`，根据 `agent_id === 'system'` 切换组件。

- [ ] **Step 3: 实现 ControlBar**

暂停/重试/跳过按钮，仅在 `taskStatus === 'processing'` 或 `'paused'` 时显示。手动模式下暂停时显示"确认继续"按钮组。调用 `POST /api/confirm/{taskId}` 和 `POST /api/retry/{taskId}`。

- [ ] **Step 4: 实现 ProgressBar**

批次处理进度条：`batch_progress` (如 "2/5") + `batch_pct` (如 40)。渐变蓝色进度条，带动画。

- [ ] **Step 5: 提交**

```bash
git add src/components/ChatFlow/
git commit -m "feat: implement chat flow panel with message list and controls"
```

### Task 16: 实现报告面板

**Files:**
- Create: `src/components/ReportPanel/ReportPanel.tsx`
- Create: `src/components/ReportPanel/OverviewTab.tsx`
- Create: `src/components/ReportPanel/ModificationsTab.tsx`
- Create: `src/components/ReportPanel/ExportTab.tsx`

- [ ] **Step 1: 实现 OverviewTab**

统计卡片网格：总重复数、AIGC率、风险等级、匹配论文数。每个卡片用图标 + 数字 + 标签展示。数据从 store 的 `report` 字段读取。

- [ ] **Step 2: 实现 ModificationsTab**

逐句修改方案列表，每项可展开/折叠：
- 折叠态：原句预览（截断50字）+ 修改方向标签
- 展开态：完整原句、相似句子、来源、修改后句子、修改说明

颜色编码：同义改写-蓝、结构调整-橙、补充引用-绿、删除重写-红、合并精简-紫。

- [ ] **Step 3: 实现 ExportTab**

下载 DOCX 按钮（`docxReady ? 亮起 : 灰色禁用`），点击触发 `window.open('/api/download/{taskId}')`。复制报告文本按钮。

- [ ] **Step 4: 提交**

```bash
git add src/components/ReportPanel/
git commit -m "feat: implement report panel with overview, modifications, and export tabs"
```

### Task 17: 实现上传模态框

**Files:**
- Create: `src/components/UploadModal/UploadModal.tsx`

- [ ] **Step 1: 实现 UploadModal**

拖拽上传区域 + 点击选择文件。支持 PDF/Word/TXT，显示文件名、大小、格式图标。上传中显示进度动画，完成后文本回显在可编辑 textarea。调用 `POST /api/upload`（FormData）。

- [ ] **Step 2: 提交**

```bash
git add src/components/UploadModal/
git commit -m "feat: implement file upload modal with drag-and-drop"
```

### Task 18: 实现设置模态框

**Files:**
- Create: `src/components/SettingsModal/SettingsModal.tsx`

- [ ] **Step 1: 实现 SettingsModal**

设置表单包含：
1. 6 个 Agent 的 API Key 输入框（密码类型），支持"全部相同"快捷复选框
2. 论文源多选（7个复选框，已选中的高亮）
3. 相似度阈值滑块（40-90，默认60）
4. 批次大小输入（5-20，默认10）
5. 保存按钮 → 写入后端配置（或通过 IPC 写入 .env）

- [ ] **Step 2: 提交**

```bash
git add src/components/SettingsModal/
git commit -m "feat: implement settings modal for API keys and preferences"
```

### Task 19: 实现历史任务抽屉和状态栏

**Files:**
- Create: `src/components/HistoryDrawer/HistoryDrawer.tsx`
- Create: `src/components/Layout/StatusBar.tsx`

- [ ] **Step 1: 实现 HistoryDrawer**

右侧滑出抽屉，列出历史任务。每项显示：任务时间、论文标题、重复数、风险等级、状态标签。点击可加载历史报告。调用 `GET /api/history`。

- [ ] **Step 2: 实现 StatusBar**

底部固定栏，显示：Python 后端连接状态（绿点/红点 + localhost:5001）、当前使用的模型名、就绪状态。

- [ ] **Step 3: 提交**

```bash
git add src/components/HistoryDrawer/ src/components/Layout/StatusBar.tsx
git commit -m "feat: implement history drawer and status bar"
```

---

## 阶段三：Electron 桌面壳

### Task 20: 创建 Electron 主进程

**Files:**
- Create: `electron/main.ts`
- Create: `electron/preload.ts`
- Create: `electron/python-manager.ts`
- Create: `electron/package.json`
- Create: `electron-builder.yml`
- Modify: `package.json`（根目录）

- [ ] **Step 1: 初始化 Electron 依赖**

```bash
npm install -D electron electron-builder concurrently wait-on
npm install electron-updater
```

- [ ] **Step 2: 实现 PythonManager**

```typescript
// electron/python-manager.ts
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import http from 'http';

export class PythonManager {
  private process: ChildProcess | null = null;
  private port: number = 5001;

  get isPackaged(): boolean {
    return !!(process as any).resourcesPath;
  }

  async start(): Promise<void> {
    const pythonPath = this.isPackaged
      ? path.join((process as any).resourcesPath, 'python', 'python.exe')
      : 'python';

    const serverPath = this.isPackaged
      ? path.join((process as any).resourcesPath, 'papersearch', 'app.py')
      : path.join(__dirname, '..', 'papersearch', 'app.py');

    this.process = spawn(pythonPath, [serverPath], {
      env: { ...process.env, PAPER_PORT: String(this.port) },
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    this.process.stdout?.on('data', (data) => {
      console.log(`[Python] ${data.toString().trim()}`);
    });

    this.process.stderr?.on('data', (data) => {
      console.error(`[Python Error] ${data.toString().trim()}`);
    });

    this.process.on('exit', (code) => {
      console.log(`Python process exited with code ${code}`);
    });

    await this.waitForReady(15000);
  }

  private waitForReady(timeout: number): Promise<void> {
    return new Promise((resolve, reject) => {
      const start = Date.now();
      const check = () => {
        http.get(`http://localhost:${this.port}/api/health`, (res) => {
          if (res.statusCode === 200) return resolve();
          if (Date.now() - start > timeout) return reject(new Error('Health check timeout'));
          setTimeout(check, 500);
        }).on('error', () => {
          if (Date.now() - start > timeout) return reject(new Error('Python server failed to start'));
          setTimeout(check, 500);
        });
      };
      check();
    });
  }

  async stop(): Promise<void> {
    if (!this.process) return;
    this.process.kill('SIGTERM');
    await new Promise(r => setTimeout(r, 3000));
    if (this.process && !this.process.killed) {
      this.process.kill('SIGKILL');
    }
    this.process = null;
  }
}
```

- [ ] **Step 3: 实现 preload.ts**

暴露有限 API 给渲染进程：`ipcRenderer.invoke('select-file')` 用于系统文件对话框。

- [ ] **Step 4: 实现 main.ts**

```typescript
// electron/main.ts
import { app, BrowserWindow } from 'electron';
import { PythonManager } from './python-manager';
import path from 'path';

const pythonManager = new PythonManager();
let mainWindow: BrowserWindow | null = null;
let splashWindow: BrowserWindow | null = null;

function createSplash() {
  splashWindow = new BrowserWindow({
    width: 400, height: 300, frame: false, transparent: true,
    alwaysOnTop: true, center: true,
  });
  splashWindow.loadFile(path.join(__dirname, '..', 'dist', 'splash.html'));
}

async function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400, height: 900, minWidth: 1000, minHeight: 700,
    backgroundColor: '#0f1119',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadURL('http://localhost:5001');

  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(async () => {
  createSplash();
  try {
    await pythonManager.start();
  } catch (e) {
    splashWindow?.close();
    createErrorWindow('Python 后端启动失败');
    return;
  }
  await createMainWindow();
  splashWindow?.close();
});

app.on('window-all-closed', async () => {
  await pythonManager.stop();
  app.quit();
});

app.on('before-quit', async () => {
  await pythonManager.stop();
});
```

- [ ] **Step 5: 配置打包**

创建 `electron-builder.yml`（根据 spec 5.4 节配置）。更新根 `package.json` 添加 scripts：

```json
{
  "main": "dist-electron/main.js",
  "scripts": {
    "dev:react": "vite",
    "dev:electron": "wait-on http://localhost:5001 && electron .",
    "dev": "concurrently \"python papersearch/app.py\" \"npm run dev:react\"",
    "build:react": "tsc && vite build",
    "build:electron": "tsc -p electron/tsconfig.json",
    "build": "npm run build:react && npm run build:electron",
    "dist": "npm run build && electron-builder"
  }
}
```

- [ ] **Step 6: 验证开发模式**

```bash
# 终端 1
cd papersearch && python app.py
# 终端 2
npm run dev:react
# 浏览器打开 http://localhost:5173 确认 React 前端加载
```

- [ ] **Step 7: 提交**

```bash
git add electron/ electron-builder.yml package.json
git commit -m "feat: add Electron shell with Python process management"
```

---

## 阶段四：集成与收尾

### Task 21: 删除旧文件，确保所有模块导入正确

- [ ] **Step 1: 清理旧文件**

```bash
# 删除旧的 server.py（已由 app.py 替代）
git rm papersearch/server.py
# 删除旧的 paper_apis.py（已移到 services/）
# 已在 Task 5 中 git mv
```

- [ ] **Step 2: 验证所有导入路径**

```bash
cd papersearch && python -c "
from config import AGENTS_CONFIG, PAPER_PORT, DB_PATH
from agents import create_agent
from services.file_parser import extract_text
from services.paper_api import search_all
from engine.sse_broker import sse_broker
from engine.task_manager import TaskManager
print('All imports OK')
"
```

- [ ] **Step 3: 运行完整端到端测试**

```bash
cd papersearch && python app.py &
sleep 3
# 测试健康检查
curl -s http://localhost:5001/api/health
# 测试关键词提取
curl -s -X POST http://localhost:5001/api/keywords \
  -H "Content-Type: application/json" \
  -d '{"paper":"深度学习在自然语言处理中的应用研究。本文提出了一种基于Transformer的新方法。"}'
kill %1
```

- [ ] **Step 4: 提交**

```bash
git add .
git commit -m "chore: remove old server.py, verify all module imports"
```

### Task 22: 编写 README.md

- [ ] **Step 1: 更新 README**

包含：项目简介、架构说明、快速开始（开发模式）、打包构建命令、目录结构说明、环境配置指南。

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs: update README with new architecture and setup guide"
```

---

## 验证清单

完成所有 Task 后，逐项验证：

- [ ] `python papersearch/app.py` 启动成功，所有 API 端点正常响应
- [ ] `npm run dev` 启动 React 开发服务器
- [ ] 前端能连接后端 SSE 流，实时接收 Agent 事件
- [ ] 上传 PDF 文件能正确提取文本
- [ ] 发起查重任务后，DAG 面板节点状态正确切换
- [ ] 对话流面板实时显示 Agent 消息
- [ ] 报告面板在任务完成后显示统计和数据
- [ ] DOCX 报告可下载
- [ ] 手动模式下暂停/确认/重试功能正常
- [ ] 历史任务列表可加载
- [ ] Electron 开发模式可启动（`npm run dev:electron`）
- [ ] `npm run build` 构建成功
- [ ] `npm run dist` 打包出 Windows .exe 安装包
