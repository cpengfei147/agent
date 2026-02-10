# ERABU Agent 部署与运行手册

## 目录

1. [环境要求](#环境要求)
2. [快速开始（本地开发）](#快速开始本地开发)
3. [Docker 部署](#docker-部署)
4. [配置说明](#配置说明)
5. [常见问题](#常见问题)

---

## 环境要求

### 必需

| 依赖 | 版本 | 说明 |
|-----|------|------|
| Python | 3.10+ | 后端运行环境 |
| Node.js | 18+ | 前端构建 |
| Redis | 7.0+ | 会话存储（可选，有内存降级） |

### API Keys（必需）

| Key | 用途 | 获取地址 |
|-----|------|---------|
| OpenAI API Key | LLM 调用（Router/Collector） | https://platform.openai.com |
| Google Maps API Key | 地址验证 | https://console.cloud.google.com |
| Google Gemini API Key | 图片识别 | https://aistudio.google.com |

---

## 快速开始（本地开发）

### 1. 克隆代码

```bash
git clone git@github.com:cpengfei147/agent.git
cd agent
```

### 2. 后端配置

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
```

编辑 `.env` 文件，填入 API Keys：

```env
# LLM - OpenAI
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o

# Google Maps (地址验证)
GOOGLE_MAPS_API_KEY=your-google-maps-api-key

# Google Gemini (图片识别)
GEMINI_API_KEY=your-gemini-api-key

# Redis (可选，不配置会使用内存降级)
REDIS_URL=redis://localhost:6379
```

### 3. 启动后端

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动成功后：
- API 地址：http://localhost:8000
- WebSocket：ws://localhost:8000/ws/chat

### 4. 前端配置与启动

```bash
cd frontend

# 安装依赖
npm install

# 开发模式启动
npm run dev
```

前端启动成功后：
- 访问地址：http://localhost:5173

### 5. 验证运行

打开浏览器访问 http://localhost:5173，应该看到聊天界面。

发送消息测试：
```
用户：你好
Agent：你好！我是 ERABU 搬家助手...
```

---

## Docker 部署

### 1. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
OPENAI_API_KEY=sk-your-openai-api-key
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
GEMINI_API_KEY=your-gemini-api-key
```

### 2. 启动服务

```bash
# 启动所有服务（API + Redis + PostgreSQL）
docker-compose up -d

# 查看日志
docker-compose logs -f api
```

### 3. 服务说明

| 服务 | 端口 | 说明 |
|-----|------|------|
| api | 8000 | 后端 API |
| redis | 6379 | 会话存储 |
| db | 5432 | PostgreSQL（预留） |

### 4. 停止服务

```bash
docker-compose down
```

---

## 配置说明

### 环境变量完整列表

| 变量 | 必需 | 默认值 | 说明 |
|-----|------|-------|------|
| `OPENAI_API_KEY` | ✅ | - | OpenAI API Key |
| `OPENAI_MODEL` | ❌ | gpt-4o | 使用的模型 |
| `OPENAI_TIMEOUT` | ❌ | 30 | API 超时时间（秒） |
| `GOOGLE_MAPS_API_KEY` | ✅ | - | Google Maps API Key |
| `GEMINI_API_KEY` | ✅ | - | Google Gemini API Key |
| `REDIS_URL` | ❌ | - | Redis 连接地址 |
| `DATABASE_URL` | ❌ | - | PostgreSQL 连接地址 |
| `SESSION_TTL_HOURS` | ❌ | 24 | 会话过期时间（小时） |
| `LOG_LEVEL` | ❌ | INFO | 日志级别 |

### Redis 降级说明

如果不配置 `REDIS_URL`，系统会自动使用内存存储，日志会显示：

```
WARNING - Redis not available, using memory fallback
```

这在开发环境下完全可用，但重启后会话数据会丢失。

---

## 项目结构

```
erabu-agent/
├── backend/
│   ├── app/
│   │   ├── agents/              # Agent 实现
│   │   │   ├── router.py        # Router Agent
│   │   │   ├── collector.py     # Collector Agent
│   │   │   └── prompts/         # Prompt 模板
│   │   ├── api/
│   │   │   └── websocket.py     # WebSocket 接口
│   │   ├── core/
│   │   │   ├── llm_client.py    # LLM 调用封装
│   │   │   └── phase_inference.py
│   │   ├── services/
│   │   │   ├── address_service.py  # 地址验证
│   │   │   ├── item_service.py     # 图片识别
│   │   │   └── smart_options.py
│   │   ├── models/              # 数据模型
│   │   └── storage/             # 存储层
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   └── App.jsx              # 主组件
│   ├── package.json
│   └── vite.config.js
│
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## 常见问题

### 1. 后端启动报错：ModuleNotFoundError

```bash
# 确保激活了虚拟环境
source venv/bin/activate

# 重新安装依赖
pip install -r requirements.txt
```

### 2. WebSocket 连接失败

检查后端是否正常运行：
```bash
curl http://localhost:8000/health
```

检查前端 WebSocket 地址配置（默认连接 `ws://localhost:8000/ws/chat`）

### 3. 地址验证失败

检查 Google Maps API Key：
- 确保已启用 Geocoding API
- 确保 API Key 没有 IP 限制（开发环境）

### 4. 图片识别失败

检查 Gemini API：
- 确保 `GEMINI_API_KEY` 配置正确
- 如果 API 配额用尽，系统会返回 mock 数据

### 5. Redis 连接失败

开发环境可以不配置 Redis，系统会自动降级到内存存储。

如需使用 Redis：
```bash
# macOS
brew install redis
brew services start redis

# 或使用 Docker
docker run -d -p 6379:6379 redis:7-alpine
```

---

## 开发命令

```bash
# 后端
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000    # 开发模式
pytest                                         # 运行测试

# 前端
cd frontend
npm run dev      # 开发模式
npm run build    # 构建生产版本
npm run preview  # 预览生产版本
```

---

## 生产部署建议

1. **使用 HTTPS**：配置 Nginx 反向代理 + SSL 证书
2. **配置 Redis 持久化**：生产环境必须配置 Redis
3. **设置日志收集**：配置 LOG_LEVEL=WARNING，接入日志系统
4. **监控 API 调用**：监控 OpenAI/Google API 用量和成本
5. **限流配置**：根据实际情况调整 RATE_LIMIT_PER_MINUTE

---

## 联系方式

如有问题，请联系开发团队。
