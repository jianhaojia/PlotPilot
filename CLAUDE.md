# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作提供指导。

## 项目概览

**PlotPilot (墨枢)** - AI 驱动的长篇创作平台，集自动驾驶生成、知识图谱管理、风格分析于一体。

- **后端**：Python + FastAPI（DDD 四层架构）
- **前端**：Vue 3 + TypeScript + Vite + Naive UI
- **数据库**：SQLite + FAISS（本地向量存储，无需外部服务）
- **AI**：OpenAI 兼容协议 / Anthropic Claude / 火山方舟 Doubao

## 常用命令

### 后端开发
```bash
# 创建虚拟环境
python -m venv .venv && .venv\Scripts\activate

# 安装核心依赖（轻量级）
pip install -r requirements.txt

# 安装本地嵌入模型依赖（可选）
pip install -r requirements-local.txt

# 启动后端（热重载）
uvicorn interfaces.main:app --host 127.0.0.1 --port 8005 --reload

# 运行测试
pytest tests/ -v

# 仅运行单元测试
pytest tests/unit -v -m unit

# 仅运行集成测试
pytest tests/integration -v -m integration

# 运行测试并生成覆盖率报告
pytest tests/ --cov=. --cov-report=term-missing
```

### 前端开发
```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

### 环境配置
```bash
# 复制示例环境变量并配置
copy .env.example .env
```

必需环境变量：
- `ANTHROPIC_API_KEY` 或 `ARK_API_KEY`：至少配置一个 LLM 凭证
- `EMBEDDING_SERVICE`：`openai`（默认）或 `local`

## 架构：DDD 四层

```
domain/                # 核心业务逻辑与模型
├── bible/            # 故事圣经
├── cast/             # 角色
├── knowledge/        # 知识管理
├── novel/            # 小说核心
├── structure/        # 故事结构
└── worldbuilding/    # 世界观设定

application/           # 应用服务与工作流
├── engine/           # 生成引擎
├── services/         # 业务服务（memory_engine、autopilot_daemon 等）
├── workflows/        # 自动小说生成
└── world/            # 世界观服务

infrastructure/        # 技术实现
├── ai/               # LLM 客户端、提示词管理器
└── persistence/      # 数据库连接

interfaces/           # API 层
└── api/              # REST 端点
```

## 关键服务与模块

| 模块 | 路径 | 用途 |
|------|------|------|
| 记忆引擎 | `application/engine/services/memory_engine.py` | 多层上下文记忆管理 |
| 自动驾驶守护进程 | `application/engine/services/autopilot_daemon.py` | 后台自动生成 |
| 章后管线 | `application/engine/services/chapter_aftermath_pipeline.py` | 章节后处理（摘要、三元组、伏笔） |
| 流式总线 | `application/engine/services/streaming_bus.py` | SSE 实时推送 |

## API 路由 (v1)

- 核心：`/api/v1/novels`、`/api/v1/chapters`
- 世界观：`/api/v1/bible`、`/api/v1/cast`、`/api/v1/knowledge`
- 蓝图：`/api/v1/beat-sheet`、`/api/v1/story-structure`
- 引擎：`/api/v1/generation`、`/api/v1/autopilot`
- 审阅：`/api/v1/chapter-review`
- 分析：`/api/v1/voice`、`/api/v1/foreshadow-ledger`
- 统计：`/api/stats`

## 重要模式

- **统一章后管线**：手动保存与自动驾驶共用同一套章后管线，确保叙事落库与索引逻辑一致。
- **自动驾驶独立进程**：守护进程在独立进程中运行，避免阻塞主事件循环。
- **本地向量存储**：使用 FAISS 本地存储，无需 Qdrant 或外部向量数据库。
- **20+ 提示词接点**：集中式提示词配置，支持定制。

## 前端结构

```
frontend/src/
├── api/              # API 客户端
├── components/       # Vue 组件
│   ├── autopilot/   # 自动驾驶 UI
│   └── workbench/   # 工作台组件
└── views/            # 页面视图
```

## 配置文件

- `.env.example`：环境变量模板
- `pyproject.toml`：pytest 配置
- `pytest.ini`：pytest 标记（unit、integration、slow）
- `frontend/package.json`：npm 脚本与依赖
