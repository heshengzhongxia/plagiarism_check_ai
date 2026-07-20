# 六智Agent论文工坊 — 桌面应用重设计

> 日期：2026-07-20 | 状态：设计中

## 1. 背景与目标

### 1.1 现状

"六智Agent论文工坊"是一个基于 Flask + 原生 HTML 的学术论文查重系统，核心由 6 个 AI Agent 组成 DAG 流水线：解析论文 → 检索文献 → 逐句查重 → 修改方向分析 → 具体改写方案 → 生成查重报告。

当前问题：
- 前端为单个 `index.html`（1000+ 行），难以维护和扩展
- 后端 `server.py`（687 行）承载所有逻辑：路由、Pipeline、文件处理、CNKI 接口混在一起
- 前端通过 1 秒轮询 `/api/status` 获取状态，体验滞后
- API Key 硬编码在 `config.py` 中
- 任务状态存储在内存字典中，重启即丢失
- 用户需手动命令行启动 Python 服务，再打开浏览器

### 1.2 目标

将项目重构为 **Electron 桌面应用**，提供：

1. **一键启动**：双击应用自动拉起 Python 后端，打开主窗口
2. **Agent 协作可视化**：左侧 DAG 流程图实时显示 6 个 Agent 的执行状态
3. **实时消息流**：SSE 推送替代轮询，Agent 消息即时到达
4. **报告面板**：右侧展示查重统计、逐句方案、一键下载 DOCX
5. **平滑体验**：启动加载动画、优雅关闭、错误重试

### 1.3 范围

- **功能不变**：6 个 Agent、7 个论文 API、知网爬虫、PDF/Word/TXT 解析、DOCX 报告下载全部保留
- **UI/UX 全面升级**：三栏布局、暗色主题、响应式交互
- **架构重构**：后端分层模块化、前端现代框架、Electron 桌面壳

## 2. 整体架构

```
┌─────────────────────────────────────────────────────┐
│                   Electron 桌面壳                     │
│  ┌─────────────────────────────────────────────────┐ │
│  │              React 前端 (SPA)                    │ │
│  │  ┌──────────┬──────────────┬─────────────────┐  │ │
│  │  │ Agent DAG│  实时对话流   │  报告预览&导出   │  │ │
│  │  │ 可视化面板│   & 控制面板  │   & 历史管理     │  │ │
│  │  └──────────┴──────────────┴─────────────────┘  │ │
│  └─────────────────────────────────────────────────┘ │
│                       │ HTTP + SSE                    │
│  ┌─────────────────────────────────────────────────┐ │
│  │           Python 后端 (子进程 localhost:5001)     │ │
│  │  ┌─────────┬──────────┬────────┬─────────────┐  │ │
│  │  │ API路由层│ Pipeline │ Agent  │  外部服务层  │  │ │
│  │  │(Flask)  │ 编排引擎  │ 引擎层  │              │  │ │
│  │  └─────────┴──────────┴────────┴─────────────┘  │ │
│  │                         ┌────────────────────┐  │ │
│  │                         │ SQLite 本地存储     │  │ │
│  │                         └────────────────────┘  │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 2.1 各层职责

| 层 | 技术 | 职责 |
|----|------|------|
| Electron 主进程 | Node.js | 窗口管理、Python 子进程生命周期、系统托盘、菜单、文件关联 |
| React 前端 | React + TypeScript + TailwindCSS | 三栏 UI、SSE 消费、状态管理、路由 |
| Python 后端 | Flask + flask-cors | REST API + SSE 端点、Pipeline 编排、任务管理 |
| Agent 引擎 | Python 类 | 6 个 Agent 的 LLM 调用与处理逻辑 |
| 外部服务 | Python 模块 | 7 个学术 API、CNKI 爬虫、文件解析、DOCX 生成 |
| 持久化 | SQLite | 任务状态、历史报告、用户配置 |

## 3. 前端设计

### 3.1 技术选型

| 维度 | 选型 | 理由 |
|------|------|------|
| 框架 | React 18 + TypeScript | 生态丰富、类型安全 |
| 样式 | TailwindCSS | 暗色主题快速定制、与现有暗色设计一致 |
| 状态管理 | Zustand | 轻量、适合 SSE 实时更新场景 |
| 图表/流程图 | ReactFlow | Agent DAG 可视化，节点状态动画 |
| SSE 客户端 | EventSource API | 浏览器原生支持，无额外依赖 |
| 构建 | Vite | 开发热重载、打包快 |

### 3.2 三栏布局

```
┌─────── 顶部导航栏 ──────────────────────────────────────────────┐
│  📄 六智Agent论文工坊    [上传论文] [新建任务]    ⚙️ 设置  📋 历史  │
├──────────────┬──────────────────────────────┬─────────────────────┤
│   Agent DAG  │     实时对话流                 │   报告 & 结果面板     │
│   可视化面板  │                               │                     │
│ (300px)      │  ⚙️ 系统 · 任务已创建           │  📊 查重概览          │
│              │  ─────────────────────────   │  ┌─────────────────┐ │
│   ┌──────┐   │  🔍 奥利 · 解析中...           │  │ 总重复: 23句     │ │
│   │  🔍  │   │  "提取关键词: 深度学习..."       │  │ AIGC率: 15%     │ │
│   │ 解析 ├─┐ │  ─────────────────────────   │  │ 风险: 中        │ │
│   └──┬───┘ │ │  🕸️ 艾瑞 · 检索中...           │  └─────────────────┘ │
│      │     │ │  "arXiv返回 8篇..."            │                     │
│   ┌──┴───┐ │ │  ─────────────────────────   │  📝 逐句修改方案      │
│   │  🕸️  │ │ │  ...                          │  ┌─────────────────┐ │
│   │ 检索 │ │ │                               │  │ 句1 → 同义改写   │ │
│   └──┬───┘ │ │  [⏸️ 暂停] [🔄 重试] [⏭️ 跳过]  │  │ 句2 → 结构调整   │ │
│      │     │ │                               │  └─────────────────┘ │
│   ┌──┴───┐ │ │                               │                     │
│   │  ⚖️  │ │ │                               │  📥 [下载DOCX报告]   │
│   │ 查重 ├─┤ │                               │                     │
│   └──┬───┘ │ │                               │                     │
│   ┌──┴───┐ │ │                               │                     │
│   │  📖  │ │ │                               │                     │
│   │ 分析 ├─┤ │                               │                     │
│   └──┬───┘ │ │                               │                     │
│   ┌──┴───┐ │ │                               │                     │
│   │  💡  │ │ │                               │                     │
│   │ 方案 ├─┤ │                               │                     │
│   └──┬───┘ │ │                               │                     │
│   ┌──┴───┐ │ │                               │                     │
│   │  📋  │ │ │                               │                     │
│   │ 报告 │ │ │                               │                     │
│   └──────┘ │ │                               │                     │
│              │                               │                     │
│  图例:       │                               │                     │
│  🔵 运行中   │                               │                     │
│  ✅ 完成     │                               │                     │
│  ⏳ 待命     │                               │                     │
│  ❌ 失败     │                               │                     │
├──────────────┴──────────────────────────────┴─────────────────────┤
│  🟢 Python 后端运行中 · localhost:5001 · DeepSeek-Chat · 就绪       │
└────────────────────────────────────────────────────────────────────┘
```

### 3.3 组件树

```
App
├── TopNavBar
│   ├── AppTitle
│   ├── UploadButton          # 触发论文上传模态框
│   ├── NewTaskButton         # 新建任务
│   ├── SettingsButton        # 设置模态框（API Key、阈值等）
│   └── HistoryButton         # 历史任务列表
├── MainLayout
│   ├── LeftPanel (AgentDAG)
│   │   ├── ReactFlow Canvas  # DAG 图
│   │   ├── AgentNode ×6      # 自定义节点（含状态动画）
│   │   └── AgentLegend       # 状态图例
│   ├── CenterPanel (ChatFlow)
│   │   ├── MessageList       # 滚动消息列表
│   │   │   ├── SystemMessage
│   │   │   └── AgentMessage  # emoji + 颜色 + 时间戳
│   │   ├── ControlBar        # 暂停/重试/跳过按钮
│   │   └── ProgressBar       # 批次进度条
│   └── RightPanel (Report)
│       ├── TabBar            # 概览 / 方案 / 导出
│       ├── OverviewTab       # 统计卡片 + 风险评级
│       ├── ModificationsTab  # 逐句展开列表
│       └── ExportTab         # 下载按钮 + 格式选择
├── UploadModal               # 文件上传拖拽区
├── SettingsModal             # 配置表单
├── HistoryDrawer             # 历史任务侧边抽屉
└── StatusBar                 # 底部状态栏
```

### 3.4 状态管理（Zustand）

```typescript
interface AppState {
  // 任务
  currentTaskId: string | null;
  taskStatus: 'idle' | 'processing' | 'paused' | 'completed' | 'error';
  autoMode: boolean;

  // Agent 状态
  agentsStatus: Record<string, { status: string; progress: number }>;
  conversation: Message[];

  // 报告
  report: Report | null;
  modifications: Modification[];
  docxReady: boolean;

  // 连接
  backendStatus: 'starting' | 'running' | 'stopped' | 'error';

  // Actions
  startTask: (paper: string, config: TaskConfig) => void;
  confirmAgent: () => void;
  retryAgent: () => void;
  downloadReport: () => void;
}
```

### 3.5 SSE 消息流

```
前端 EventSource                    Python SSE Endpoint
  │                                       │
  │ GET /api/stream/task_1                 │
  │ ──────────────────────────────────────>│
  │                                       │
  │ event: agent_start                    │ event: agent_msg
  │ data: {"agent_id":"agent1",           │ data: {"agent_id":"agent1",
  │        "status":"running"}             │        "message":"解析中..."}
  │ <──────────────────────────────────────│
  │                                       │
  │ event: agent_done                     │ event: task_progress
  │ data: {"agent_id":"agent1",           │ data: {"batch":"2/5",
  │        "result":{...}}                 │        "pct":40}
  │ <──────────────────────────────────────│
  │                                       │
  │ event: task_complete                  │ event: task_error
  │ data: {"report":{...}}                │ data: {"error":"..."}
  │ <──────────────────────────────────────│
```

SSE 事件类型：

| 事件 | 触发时机 | 携带数据 |
|------|----------|----------|
| `agent_start` | Agent 开始执行 | agent_id, agent_name, emoji, color |
| `agent_msg` | Agent 发言 | agent_id, message, timestamp |
| `agent_done` | Agent 完成 | agent_id, result (摘要) |
| `agent_error` | Agent 异常 | agent_id, error |
| `task_progress` | 批次进度更新 | batch, pct, batch_progress |
| `task_paused` | 手动模式暂停 | agent_id (待确认的Agent) |
| `task_complete` | 全部完成 | report, docx_ready |
| `task_error` | 流水线异常 | error |

## 4. 后端设计

### 4.1 目录结构

```
papersearch/
├── app.py                  # 入口：创建 Flask app、注册路由、启动
├── config.py               # 配置读取（从 .env 加载，提供默认值）
├── .env.example            # 环境变量模板
├── routes/                 # ── 第 1 层：API 路由层 ──
│   ├── __init__.py
│   ├── task_routes.py      # /api/start, /api/status, /api/stream, /api/confirm, /api/retry
│   ├── upload_routes.py    # /api/upload, /api/keywords
│   ├── report_routes.py    # /api/report, /api/download
│   └── cnki_routes.py      # /api/cnki/start, /api/cnki/status, /api/cnki/solve, /api/cnki/download
├── engine/                 # ── 第 2 层：Pipeline 编排层 ──
│   ├── __init__.py
│   ├── pipeline.py         # execute_pipeline() — DAG 编排核心逻辑
│   ├── task_manager.py     # TaskManager 类 — 任务状态管理 + SQLite 持久化
│   └── sse_broker.py       # SSEBroker 类 — 线程安全的事件发布/订阅
├── agents/                 # ── 第 3 层：Agent 引擎层（保持现有结构）──
│   ├── __init__.py
│   ├── base.py             # BaseAgent — 基类 (think/verify/discuss/speak)
│   ├── agent1_parser.py    # 论文解析
│   ├── agent2_searcher.py  # 文献检索
│   ├── agent3_checker.py   # 逐句查重比对
│   ├── agent4_reader.py    # 修改方向分析
│   ├── agent5_suggester.py # 具体改写方案
│   └── agent6_integrator.py# 报告生成
├── services/               # ── 第 4 层：外部服务层 ──
│   ├── __init__.py
│   ├── paper_api.py        # 7 个学术 API 统一搜索入口
│   ├── file_parser.py      # PDF / Word / TXT 文本提取
│   ├── cnki_spider.py      # 知网爬虫（Playwright）
│   └── docx_generator.py   # DOCX 报告生成（从 agent6 逻辑抽取）
├── llm_client.py           # DeepSeek API 调用封装（OpenAI 兼容）
├── keyword_extractor.py    # KeyBERT + TF-IDF 关键词提取
├── store/                  # SQLite 数据库
│   ├── __init__.py
│   ├── schema.sql          # 建表语句
│   └── repository.py       # 数据访问层
├── reports/                # DOCX 报告输出目录
└── requirements.txt
```

### 4.2 SSE Broker 设计

```python
# engine/sse_broker.py
import queue
import threading

class SSEBroker:
    """线程安全的事件队列，每个任务一个订阅者"""

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
```

SSE 端点实现：

```python
# routes/task_routes.py
from flask import Response, stream_with_context
import json

@app.route('/api/stream/<task_id>')
def stream(task_id):
    q = sse_broker.subscribe(task_id)

    def generate():
        try:
            while True:
                msg = q.get(timeout=30)  # 30s 心跳
                yield f"event: {msg['event']}\n"
                yield f"data: {json.dumps(msg['data'], ensure_ascii=False)}\n\n"
                if msg['event'] in ('task_complete', 'task_error'):
                    break
        except queue.Empty:
            yield f"event: heartbeat\ndata: {{}}\n\n"
        finally:
            sse_broker.unsubscribe(task_id)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )
```

### 4.3 TaskManager — 状态持久化

```python
# engine/task_manager.py
import sqlite3
import json

class TaskManager:
    """任务状态管理，基于 SQLite 持久化"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
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
                )
            """)
            conn.commit()

    def create_task(self, task_id: str, config: dict) -> None: ...
    def update_status(self, task_id: str, **kwargs) -> None: ...
    def add_message(self, task_id: str, msg: dict) -> None: ...
    def get_task(self, task_id: str) -> dict | None: ...
    def get_messages(self, task_id: str, since: int = 0) -> list[dict]: ...
    def list_tasks(self, limit: int = 50) -> list[dict]: ...
    def delete_task(self, task_id: str) -> None: ...
    def cleanup_old(self, days: int = 30) -> int: ...
```

### 4.4 Pipeline 流程（保持 DAG）

```
agent1 (解析) ──┬──> agent2 (检索) ──> agent3 (查重) ──┬──> agent4 (分析) ──> agent5 (方案) ──> agent6 (报告)
                │                                      │
                └──────────────────────────────────────┘
```

Pipeline 执行函数从 `server.py` 抽取为独立模块 `engine/pipeline.py`，职责单一：接收 TaskManager、SSEBroker、Agent 工厂，按 DAG 顺序执行，每步通过 SSEBroker 发送事件。

### 4.5 REST API 完整列表

| 方法 | 路径 | 说明 | SSE 事件 |
|------|------|------|----------|
| GET | `/api/health` | 健康检查 | - |
| GET | `/api/sources` | 获取论文源列表 | - |
| POST | `/api/keywords` | 仅提取关键词（Agent1） | - |
| POST | `/api/upload` | 上传文件，返回文本 | - |
| POST | `/api/start` | 启动查重流水线 | 通过 SSE 流推送 |
| GET | `/api/status/<task_id>` | 获取任务状态快照 | - |
| GET | `/api/stream/<task_id>` | SSE 实时事件流 | 全部 |
| POST | `/api/confirm/<task_id>` | 手动模式确认 | task_resumed |
| POST | `/api/retry/<task_id>` | 重试当前 Agent | agent_retry |
| GET | `/api/report/<task_id>` | 获取完整报告 JSON | - |
| GET | `/api/download/<task_id>` | 下载 DOCX | - |
| GET | `/api/history` | 历史任务列表 | - |
| DELETE | `/api/history/<task_id>` | 删除历史任务 | - |
| POST | `/api/cnki/start` | 启动知网爬取 | - |
| GET | `/api/cnki/status/<task_id>` | 知网爬取状态 | - |
| POST | `/api/cnki/solve/<task_id>` | 提交验证码 | - |
| GET | `/api/cnki/download/<task_id>` | 下载知网论文 ZIP | - |

## 5. Electron 桌面壳设计

### 5.1 主进程职责

```
electron/
├── main.ts                  # 主进程入口：窗口创建、Python 生命周期
├── preload.ts               # 预加载脚本：暴露安全 API 给渲染进程
├── python-manager.ts        # Python 子进程管理
├── ipc-handlers.ts          # IPC 处理：文件对话框、系统通知等
├── window-manager.ts        # 窗口创建与管理
├── menu.ts                  # 应用菜单
├── tray.ts                  # 系统托盘
├── updater.ts               # 自动更新
└── package.json             # Electron 依赖
```

### 5.2 启动流程

```
用户双击应用
    │
    ▼
┌──────────┐    启动页窗口      ┌──────────────┐   健康检查    ┌──────────────┐
│ 显示启动页  │ ────────────────>│ Python 子进程  │─────────────>│ 加载主窗口     │
│ (Splash)   │   (2秒超时消失)   │ 启动 + 等待    │  GET /health │ React 前端     │
└──────────┘                   └──────────────┘              └──────────────┘
                                    │                               │
                                    │ 启动失败                       │ 连接断开
                                    ▼                               ▼
                              ┌──────────┐                   ┌──────────────┐
                              │ 错误页面   │                   │ 重连提示      │
                              │ + 重试按钮  │                   │ + 自动重试    │
                              └──────────┘                   └──────────────┘
```

### 5.3 Python 子进程管理

```typescript
// python-manager.ts
class PythonManager {
  private process: ChildProcess | null = null;
  private port: number = 5001;

  async start(): Promise<void> {
    const pythonPath = this.isPackaged
      ? path.join(process.resourcesPath, 'python', 'python.exe')
      : 'python';

    const serverPath = this.isPackaged
      ? path.join(process.resourcesPath, 'papersearch', 'app.py')
      : path.join(__dirname, '../../papersearch', 'app.py');

    this.process = spawn(pythonPath, [serverPath], {
      env: { ...process.env, PAPER_PORT: String(this.port) },
    });

    // 监听 stdout/stderr 用于日志和错误诊断
    this.process.stdout.on('data', (data) => { /* 日志收集 */ });
    this.process.stderr.on('data', (data) => { /* 错误日志 */ });

    // 等待健康检查通过
    await this.waitForReady(15000); // 最多等 15 秒
  }

  async stop(): Promise<void> {
    if (!this.process) return;
    // 先发 SIGTERM，5 秒后强杀
    this.process.kill('SIGTERM');
    await sleep(5000);
    if (this.process && !this.process.killed) {
      this.process.kill('SIGKILL');
    }
  }
}
```

### 5.4 打包配置

```yaml
# electron-builder.yml
appId: com.liuzhi.papersearch
productName: 六智论文工坊
directories:
  output: dist-electron

files:
  - dist/**/*          # React 构建产物
  - electron/**/*.js   # Electron 主进程 (编译后)

extraResources:
  - from: python-dist/    # 嵌入式 Python + 所有依赖
    to: python
  - from: papersearch/    # Python 后端源码
    to: papersearch
    filter:
      - "**/*.py"
      - "requirements.txt"
      - ".env.example"

win:
  target: nsis
  icon: assets/icon.ico

mac:
  target: dmg
  icon: assets/icon.icns

nsis:
  oneClick: false
  allowToChangeInstallationDirectory: true
```

## 6. 数据流 — 完整用户场景

### 6.1 场景：用户上传论文进行查重

```
1. [前端] 用户点击"上传论文" → UploadModal 弹出
2. [前端] 用户拖拽/选择 PDF → POST /api/upload → [后端] 解析为纯文本
3. [前端] 文本回显在编辑区，用户可编辑
4. [前端] 用户点击"开始分析"
5. [前端] POST /api/start { paper, auto_mode, threshold }
6. [后端] TaskManager.create_task() → 返回 task_id
7. [后端] Pipeline 线程启动
8. [前端] 打开 GET /api/stream/{task_id} → SSE 连接
9. [后端] Agent1 执行 → SSEBroker.publish("agent_start") → SSEBroker.publish("agent_msg")
10. [前端] DAG 面板 agent1 节点变蓝（运行中），对话流追加消息
11. [后端] Agent1 完成 → SSEBroker.publish("agent_done")
12. [前端] agent1 节点变绿（完成），agent2 节点变蓝
13. ... 依次执行 Agent2→3→4→5→6 ...
14. [后端] 批次处理 (agent4/agent5 循环) → SSEBroker.publish("task_progress")
15. [前端] 进度条更新
16. [后端] Agent6 完成 → SSEBroker.publish("task_complete", {report, docx_ready})
17. [前端] 右侧报告面板填充数据，DOCX 下载按钮亮起
18. [前端] 用户点击"下载 DOCX" → window.open('/api/download/{task_id}')
```

### 6.2 场景：手动模式

```
手动模式下，每个 Agent 完成后暂停：
  ...
  [后端] Agent 完成 → SSEBroker.publish("task_paused", {agent_id})
  [前端] 控制栏显示"请检查 Agent 结果，点击确认继续"
  [前端] 用户点击"继续" → POST /api/confirm/{task_id}
  [后端] Pipeline 继续执行下一个 Agent
  ...
```

## 7. 配置管理

### 7.1 .env 文件

```bash
# LLM 配置
DEEPSEEK_API_KEY_AGENT1=sk-xxx
DEEPSEEK_API_KEY_AGENT2=sk-xxx
DEEPSEEK_API_KEY_AGENT3=sk-xxx
DEEPSEEK_API_KEY_AGENT4=sk-xxx
DEEPSEEK_API_KEY_AGENT5=sk-xxx
DEEPSEEK_API_KEY_AGENT6=sk-xxx
DEEPSEEK_MODEL=deepseek-chat

# 服务配置
PAPER_PORT=5001
FLASK_DEBUG=false

# 论文源
DEFAULT_SOURCES=arxiv,semantic_scholar,openalex,crossref,core,dblp,pubmed

# 查重配置
DEFAULT_THRESHOLD=60
BATCH_SIZE=10
```

### 7.2 首次启动向导

当 `.env` 不存在或缺少必要配置时，前端显示设置向导：
1. 输入 6 个 Agent 的 API Key（支持"全部相同"快捷填入）
2. 选择默认论文源
3. 设置默认相似度阈值
4. 保存 → 写入 `.env` → 重启 Python 后端

## 8. 错误处理策略

| 层级 | 错误类型 | 处理方式 |
|------|----------|----------|
| Electron | Python 进程崩溃 | 显示错误页 + 自动重启 + 日志查看 |
| Electron | 端口被占用 | 自动尝试下一个端口 (5002, 5003...) |
| Python | LLM API 调用失败 | Agent 内部重试 2 次，失败则跳过该 Agent（可配置） |
| Python | 论文 API 超时 | 单个源超时不影响其他源，返回已获取的结果 |
| Python | 文件解析失败 | 返回明确错误信息，前端展示不支持的格式提示 |
| React | SSE 连接断开 | 自动重连（3 秒间隔），重连后拉取 `/api/status` 补全状态 |
| React | 网络错误 | Toast 通知 + 错误详情折叠 |

## 9. 技术风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| Python 依赖打包复杂 | 高 | 使用 PyInstaller 预构建嵌入式 Python；sentence-transformers 模型文件首次运行时下载并缓存 |
| 模型文件大（200MB+） | 中 | 安装包不含模型，首次使用时分语言按需下载，显示下载进度 |
| Electron 包体积大 | 中 | electron-builder 压缩 + NSIS 安装包约 300MB（含 Python），可接受 |
| 知网爬虫维护成本高 | 低 | 作为可选功能，默认隐藏，需用户在设置中启用 |
| SSE 兼容性 | 低 | EventSource 所有现代浏览器/Electron 均支持 |

## 10. 目录总览（最终产物）

```
papersearch/
├── docs/superpowers/specs/
│   └── 2026-07-20-papersearch-desktop-redesign.md   # 本文件
├── electron/                   # Electron 主进程
│   ├── main.ts
│   ├── preload.ts
│   ├── python-manager.ts
│   └── package.json
├── src/                        # React 前端
│   ├── App.tsx
│   ├── main.tsx
│   ├── components/
│   │   ├── Layout/
│   │   ├── AgentDAG/
│   │   ├── ChatFlow/
│   │   ├── ReportPanel/
│   │   ├── UploadModal/
│   │   ├── SettingsModal/
│   │   └── common/
│   ├── stores/
│   │   └── useAppStore.ts
│   ├── hooks/
│   │   └── useSSE.ts
│   ├── types/
│   │   └── index.ts
│   └── styles/
├── papersearch/                # Python 后端（重构后）
│   ├── app.py
│   ├── config.py
│   ├── routes/
│   ├── engine/
│   ├── agents/                 # 保持现有
│   ├── services/
│   ├── store/
│   └── requirements.txt
├── assets/                     # 图标等静态资源
├── electron-builder.yml
├── package.json                # 根 package.json（脚本入口）
└── README.md
```
