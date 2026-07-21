# 六智Agent论文工坊

基于 6 个协作 AI Agent 的论文查重与修改方案生成系统。上传论文后，6 个 Agent 自动完成**解析 → 检索 → 查重 → 分析 → 建议 → 报告**全流程，输出专业查重报告（Word 文档）。

## 六智 Agent 协作流水线

```
📄 上传论文
    │
    ▼
┌─────────────────────────────────────────────────┐
│  🔍 Agent1 深析·奥利  →  解析论文，提取关键词        │
│  🕸️ Agent2 猎手·艾瑞  →  7大源检索相似论文           │
│  ⚖️ Agent3 校验·维拉  →  逐句查重比对，审核匹配       │
│  📖 Agent4 解构·雷欧  →  分析重复原因，制定修改方向    │
│  💡 Agent5 智囊·赛诺  →  生成具体改写方案             │
│  📋 Agent6 整合·尤娜  →  生成查重报告（Word）         │
└─────────────────────────────────────────────────┘
    │
    ▼
📥 下载查重报告 (.docx)
```

**DAG 数据流：** agent1 → (agent2, agent3, agent6) || agent2 → agent3 → (agent4, agent6) || agent4 → agent5 → agent6

## 截图

![主界面](docs/screenshot.png)

## 功能特性

- 🤖 **6 Agent 协作** — 每个 Agent 专注于一个子任务，通过 DAG 流水线协作
- 📚 **7 大论文源** — arXiv、Semantic Scholar、OpenAlex、Crossref、CORE、DBLP、PubMed
- 🇨🇳 **知网爬虫** — 内置 Playwright CNKI 爬虫，覆盖中文论文
- 🔍 **句级查重** — LCS 算法逐句比对 + LLM 语义审核双重校验
- 📝 **修改方案** — 针对每个重复句子生成具体改写建议
- 📄 **Word 报告** — 一键导出格式化的 .docx 查重报告
- 🖥️ **桌面应用** — Electron 壳打包为 Windows exe，双击即用
- ⚡ **实时推送** — SSE 实时显示 6 个 Agent 的执行进度和日志
- 📊 **DAG 可视化** — ReactFlow 渲染 Agent 数据流有向无环图
- 💾 **任务历史** — SQLite 持久化所有任务状态，支持回顾和重试

## 快速开始

### 1. 环境要求

- Python 3.10+
- Node.js 20+
- Git

### 2. 后端

```bash
cd papersearch

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env 填入 DeepSeek API Key（可配置 6 个独立 Key）

# 启动后端
python app.py
# → http://localhost:5001
```

### 3. 前端

```bash
cd papersearch
npm install

# 开发模式（Vite 热更新）
npm run dev
# → http://localhost:5173

# 或同时启动后端 + 前端
npm run dev:full
```

### 4. Electron 桌面应用

```bash
cd papersearch

# 开发模式
npm run dev:full              # 首先启动后端 + 前端
npm run dev:electron          # 然后启动 Electron 窗口

# 打包为 exe
npm run build:react           # 构建 React
npm run build:electron        # 编译 Electron TS
npm run dist                  # 打包为 Windows 解包版
```

打包后的 exe 在 `release/win-unpacked/`，双击 `六智Agent论文工坊.exe` 即可运行。API Key 可在应用内「设置」界面输入并自动持久化。

## 项目结构

```
papersearch/
├── app.py                 # Flask 入口，静态文件服务
├── config.py              # Agent 配置，.env 加载
├── agents/                # 6 个 AI Agent 实现
│   ├── agent1_parser.py   #   论文解析 + 关键词提取
│   ├── agent2_searcher.py #   学术检索
│   ├── agent3_checker.py  #   逐句查重比对
│   ├── agent4_reader.py   #   修改方向分析
│   ├── agent5_suggester.py#   具体修改方案
│   └── agent6_integrator.py#  报告整合
├── engine/                # 核心引擎
│   ├── pipeline.py        #   DAG 流水线编排
│   ├── task_manager.py    #   任务 SQLite 持久化
│   └── sse_broker.py      #   SSE 实时事件广播
├── routes/                # Flask API 路由
│   ├── task_routes.py     #   任务启动/状态/流/重试
│   ├── upload_routes.py   #   文件上传/关键词/源
│   ├── report_routes.py   #   报告导出
│   ├── cnki_routes.py     #   知网爬虫
│   └── settings_routes.py #   设置/API Key 管理
├── services/              # 服务层
│   ├── paper_api.py       #   7 大学术源 API 封装
│   ├── file_parser.py     #   PDF/DOCX/TXT 解析
│   ├── docx_generator.py  #   Word 报告生成
│   └── message_utils.py   #   消息构建工具
├── store/                 # 数据层
│   ├── repository.py      #   仓库模式 CRUD
│   └── schema.sql         #   数据库建表
├── src/                   # React 前端
│   ├── components/        #   UI 组件（ChatFlow, DAG面板, 报告面板, 设置, 上传, 历史）
│   ├── hooks/             #   useSSE 实时连接
│   ├── stores/            #   Zustand 状态
│   └── types/             #   TypeScript 类型
├── electron/              # Electron 桌面壳
│   ├── main.ts            #   主进程 (窗口管理/IPC)
│   ├── preload.ts         #   预加载脚本
│   └── python-manager.ts  #   Python 后端生命周期管理
├── .env.example           # 环境变量模板
└── electron-builder.yml   # Electron 打包配置
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY_AGENT1` ~ `AGENT6` | 6 个 Agent 的 API Key | (必填) |
| `DEEPSEEK_MODEL` | 大模型名称 | `deepseek-chat` |
| `PAPER_PORT` | 后端监听端口 | `5001` |
| `DEFAULT_SOURCES` | 默认论文检索源 | `arxiv,semantic_scholar,openalex,crossref,core,dblp,pubmed` |
| `DEFAULT_THRESHOLD` | 相似度阈值 (40-90) | `60` |
| `BATCH_SIZE` | 批处理大小 (5-20) | `10` |

## API 端点

### 任务
| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/start` | 启动查重任务 |
| `GET` | `/api/status/<task_id>` | 查询任务状态 |
| `GET` | `/api/stream/<task_id>` | SSE 实时事件流 |
| `POST` | `/api/confirm/<task_id>` | 确认查重结果 |
| `POST` | `/api/retry/<task_id>` | 重试失败任务 |

### 上传
| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/upload` | 上传论文文件 |
| `POST` | `/api/keywords` | 提取关键词 |
| `GET` | `/api/sources` | 获取可用论文源 |

### 设置
| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/settings` | 获取当前 API Key (脱敏) |
| `POST` | `/api/settings` | 保存 API Key (写入 .env) |

### 报告
| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/report/<task_id>` | 下载查重报告 (.docx) |

### 健康
| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 |

## 论文数据源

| 源 | 覆盖范围 | 认证 |
|------|------|------|
| [arXiv](https://arxiv.org) | 物理/数学/CS 预印本 | 无需 |
| [Semantic Scholar](https://semanticscholar.org) | 综合学术 | 无需 |
| [OpenAlex](https://openalex.org) | 综合学术 (开源) | 无需 |
| [Crossref](https://crossref.org) | DOI 注册论文 | 无需 |
| [CORE](https://core.ac.uk) | OA 全文 | 无需 |
| [DBLP](https://dblp.org) | CS 论文 | 无需 |
| [PubMed](https://pubmed.gov) | 生物医学 | 无需 |
| 知网 (CNKI) | 中文学位/期刊论文 | 需爬虫 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + TailwindCSS 4 + Zustand + ReactFlow + Vite 6 |
| 后端 | Flask 3 + python-dotenv + SQLite + KeyBERT + scikit-learn |
| AI | DeepSeek Chat API (OpenAI 兼容) |
| 桌面 | Electron 33 + electron-builder (NSIS / Portable) |
| 实时 | SSE (Server-Sent Events) |
| 解析 | PyPDF2 + python-docx + jieba 分词 + KeyBERT 关键词 |
| 爬虫 | Playwright (知网) + BeautifulSoup4 |

## 开发

```bash
# 后端
python app.py                     # 端口 5001

# 前端 (开发服务器)
npm run dev                       # 端口 5173

# 同时启动
npm run dev:full                  # concurrently

# Electron
npm run dev:electron              # 需后端已启动

# 打包
npm run build:full                # 构建 React + Electron
npm run dist                      # 打包 exe
```

## License

MIT
