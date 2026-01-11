# 环境变量配置指南

## 快速开始

你的 `backend/.env` 文件当前包含：
```bash
DATABASE_URL="postgresql+psycopg2://ai:Z6LwNUH481dnjAmp2kMRPmg8xj8CtE@192.168.50.115:5432/gemini-ai"
```

## 完整配置模板

根据项目代码分析，以下是所有可配置的环境变量：

### 必需配置

```bash
# 数据库连接（已配置）
DATABASE_URL="postgresql+psycopg2://ai:Z6LwNUH481dnjAmp2kMRPmg8xj8CtE@192.168.50.115:5432/gemini-ai"
```

### 推荐配置

```bash
# JWT 密钥（生产环境必须修改！）
JWT_SECRET_KEY=your-super-secret-key-change-in-production

# 是否允许用户注册
ALLOW_REGISTRATION=false
```

### 可选配置

#### Redis 配置（如果使用 Redis）
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
# REDIS_PASSWORD=your-redis-password
```

#### AI 服务提供商 API Keys（根据需要添加）
```bash
# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key

# Google / Gemini
GOOGLE_API_KEY=your-google-api-key

# 阿里云 DashScope（通义千问）
DASHSCOPE_API_KEY=sk-your-dashscope-api-key

# DeepSeek
DEEPSEEK_API_KEY=sk-your-deepseek-api-key

# Moonshot
MOONSHOT_API_KEY=sk-your-moonshot-api-key

# SiliconFlow
SILICONFLOW_API_KEY=sk-your-siliconflow-api-key

# 智谱 AI（GLM）
ZHIPU_API_KEY=your-zhipu-api-key

# Ollama（本地部署，通常不需要）
OLLAMA_API_KEY=ollama
```

#### Google Cloud Platform 配置（如果使用 Vertex AI）
```bash
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

#### 上传队列配置（可选，有默认值）
```bash
UPLOAD_QUEUE_WORKERS=5
UPLOAD_QUEUE_MAX_RETRIES=3
UPLOAD_QUEUE_RETRY_DELAY=2.0
UPLOAD_QUEUE_RATE_LIMIT=10
```

#### JWT Token 过期时间（可选，有默认值）
```bash
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

#### 数据库连接池配置（可选）
```bash
DB_POOL_RECYCLE=1800  # 连接回收时间（秒）
```

## 配置检查清单

- [x] ✅ `DATABASE_URL` - 已配置（PostgreSQL）
- [ ] ⚠️ `JWT_SECRET_KEY` - **建议修改默认值**（生产环境必须修改）
- [ ] ⚠️ `ALLOW_REGISTRATION` - 建议明确设置（默认 false）
- [ ] Redis 配置（如果使用 Redis 功能）
- [ ] AI 服务 API Keys（根据使用的服务添加）

## 安全建议

1. **JWT_SECRET_KEY**: 生产环境必须使用强随机密钥，不要使用默认值
2. **数据库密码**: 确保数据库密码足够复杂
3. **API Keys**: 不要将包含真实 API Keys 的 `.env` 文件提交到 Git
4. **文件权限**: 确保 `.env` 文件权限设置为仅当前用户可读

## 配置优先级

API Key 的获取优先级（从高到低）：
1. 请求体中的 API Key
2. 数据库中的配置（ConfigProfile 表）
3. 环境变量中的 API Key

## 验证配置

启动后端服务后，检查日志确认配置是否正确加载：

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

如果看到数据库连接错误，请检查：
1. PostgreSQL 服务是否运行
2. `DATABASE_URL` 中的主机、端口、用户名、密码是否正确
3. 数据库 `gemini-ai` 是否存在
4. 网络连接是否正常（如果数据库在远程服务器）

## 常见问题

### Q: 数据库连接失败
**检查**：
- PostgreSQL 服务是否运行
- 数据库地址 `192.168.50.115:5432` 是否可达
- 用户名 `ai` 和密码是否正确
- 数据库 `gemini-ai` 是否存在

### Q: API Key 未找到
**解决**：
- 在 `.env` 文件中添加对应的 API Key
- 或在 UI 中配置（如果支持）
- 或在请求中提供 API Key

### Q: Redis 连接失败
**解决**：
- 如果未使用 Redis，可以忽略相关错误
- 如果使用 Redis，确保 Redis 服务运行并配置正确

## 下一步

1. 根据实际需求添加 API Keys
2. 修改 `JWT_SECRET_KEY` 为强随机密钥
3. 配置 Redis（如果需要）
4. 启动服务并验证配置








