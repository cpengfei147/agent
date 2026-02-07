# ERABU Agent

搬家顾问 AI 助手 - MVP 版本

## 快速开始

### 1. 环境准备

确保已安装：
- Docker & Docker Compose
- OpenAI API Key

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 API Key
# OPENAI_API_KEY=sk-your-api-key-here
```

### 3. 启动服务

```bash
# 启动所有服务（API、Redis、PostgreSQL）
docker-compose up

# 或后台运行
docker-compose up -d
```

### 4. 访问应用

- **前端页面**: http://localhost:8000/static/index.html
- **健康检查**: http://localhost:8000/health
- **API 文档**: http://localhost:8000/docs

## 本地开发（不使用 Docker）

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动 Redis 和 PostgreSQL

```bash
# 使用 Docker 启动基础设施
docker-compose up redis db
```

### 3. 启动应用

```bash
# 设置环境变量
export OPENAI_API_KEY=sk-your-api-key
export REDIS_URL=redis://localhost:6379
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/erabu

# 启动应用
uvicorn app.main:app --reload --port 8000
```

## 项目结构

```
erabu-agent/
├── app/
│   ├── api/           # API 接口
│   ├── agents/        # Agent 实现
│   ├── core/          # 核心模块（LLM 客户端等）
│   ├── models/        # 数据模型
│   ├── services/      # 工具服务
│   ├── storage/       # 存储层
│   └── main.py        # 入口文件
├── frontend/          # 前端文件
├── tests/             # 测试文件
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## API 说明

### WebSocket 对话接口

```
ws://localhost:8000/ws/chat?session_token={token}
```

**客户端发送：**
```json
{"type": "message", "content": "我要搬家"}
{"type": "quick_option", "content": "单身"}
{"type": "submit_quote", "email": "user@example.com", "phone": "090-1234-5678"}
{"type": "reset_session"}
{"type": "ping"}
```

**服务端响应：**
```json
{"type": "text_delta", "content": "你好"}
{"type": "text_done"}
{"type": "metadata", "current_phase": 1, "quick_options": [...]}
{"type": "quote_submitted", "quote_id": "uuid", "message": "..."}
{"type": "quote_error", "code": "incomplete_fields", "message": "..."}
{"type": "session_reset", "session_token": "...", "fields_status": {...}}
{"type": "pong"}
```

### Quote API

```
POST /api/quotes/submit
GET  /api/quotes/{quote_id}
GET  /api/quotes/session/{session_token}
PATCH /api/quotes/{quote_id}/status
```

## 开发进度

- [x] P0: 基础框架
- [x] P1: Router Agent (意图分类 + 字段提取)
- [x] P2: Collector Agent (信息收集引导)
- [x] P3: Advisor + Companion Agents
- [x] P4: 前端优化 (进度条、信息面板)
- [x] P5: 数据持久化 + 报价提交
- [ ] P6: 测试优化

## 相关文档

- [架构设计 V2](../docs/plans/2026-02-06-erabu-architecture-v2.md)
- [开发计划](../docs/plans/2026-02-06-erabu-dev-plan.md)
- [产品设计](../docs/plans/2026-02-05-erabu-agent-design.md)
