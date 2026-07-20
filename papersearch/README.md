# 六智Agent论文工坊

基于6个协作AI Agent的论文查重与修改方案生成系统，支持7个学术数据源的论文检索和知网爬虫。

## 架构

```
papersearch/
├── app.py                # Flask 入口
├── config.py             # 环境变量配置 (.env)
├── agents/               # 6个 Agent 实现
├── engine/               # SSE Broker + TaskManager + Pipeline
├── routes/               # API 路由层 (4模块)
├── services/             # 文件解析 + 论文API + DOCX生成 + 消息工具
├── store/                # SQLite 持久化
├── src/                  # React 前端
│   ├── components/       # UI 组件
│   ├── hooks/            # SSE Hook
│   ├── stores/           # Zustand 状态管理
│   └── types/            # TypeScript 类型定义
└── electron/             # Electron 桌面壳
```

**DAG 数据流：** agent1 → (agent2, agent3, agent6) → agent2 → agent3 → (agent4, agent6) → agent4 → agent5 → agent6

## 快速开始

### 后端

```bash
cd papersearch
cp .env.example .env       # 编辑 .env 填入 API Key
pip install -r requirements.txt
python app.py              # 启动在 http://localhost:5001
```

### 前端

```bash
cd papersearch
npm install                # 安装依赖 (Electron 下载可能需代理)
npm run dev                # Vite 开发服务器 http://localhost:5173
```

### Electron 桌面应用

```bash
npm run dev:full           # 同时启动后端 + 前端
npm run dev:electron       # Electron 窗口 (需后端先启动)
npm run dist               # 打包 Windows NSIS 安装包
```

## 环境变量

详见 `.env.example`：
- `DEEPSEEK_API_KEY_AGENT1` ~ `AGENT6` — 各 Agent 的 API Key
- `DEEPSEEK_MODEL` — 默认模型 `deepseek-chat`
- `PAPER_PORT` — 后端端口 (默认 5001)
- `DEFAULT_SOURCES` — 7 个论文源 (逗号分隔)
- `DEFAULT_THRESHOLD` — 相似度阈值 (默认 60)
- `BATCH_SIZE` — 批处理大小 (默认 10)

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + TailwindCSS + Zustand + ReactFlow + Vite |
| 后端 | Flask 3.0 + flask-cors + SQLite |
| 桌面 | Electron 33 + electron-builder (NSIS) |
| AI | DeepSeek Chat API (6 Agent 协作) |
