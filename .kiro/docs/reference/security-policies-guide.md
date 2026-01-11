# 安全策略详细指南

## 认证和授权

### JWT 令牌策略
- **Access Token 有效期**: 15 分钟
- **Refresh Token 有效期**: 7 天
- **算法**: HS256
- **密钥管理**: 环境变量存储，定期轮换

### API 密钥管理
- **加密存储**: 使用 Fernet 对称加密
- **传输加密**: HTTPS only
- **权限隔离**: 用户只能访问自己的密钥
- **密钥验证**: 每次 API 调用前验证密钥有效性

### 密码策略
- **哈希算法**: Bcrypt（慢速哈希）
- **最小长度**: 8 字符
- **复杂度**: 建议包含大小写字母、数字和特殊字符
- **盐值**: 自动生成

---

## 输入验证

### 参数验证
```python
# 使用 Pydantic 验证所有输入
class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=10000)
    model: str | None = Field(None, pattern=r'^[a-z0-9\-\.]+$')
```

### 文件上传验证
- **文件大小**: 最大 50MB
- **文件类型**: 白名单验证（image/*, application/pdf, text/*）
- **文件名**: 移除特殊字符，防止路径遍历
- **病毒扫描**: 集成病毒扫描（生产环境）

---

## 防护措施

### SQL 注入防护
- ✅ 使用 SQLAlchemy ORM 参数化查询
- ❌ 禁止拼接 SQL 字符串
- ✅ 输入验证和转义

### XSS 防护
- ✅ React 默认转义
- ✅ Markdown 渲染使用安全库
- ❌ 避免 `dangerouslySetInnerHTML`

### CSRF 防护
- ✅ SameSite Cookie 属性
- ✅ CORS 配置限制来源
- ✅ Token 验证（JWT）

### 速率限制
- **API 调用**: 100 请求/分钟/用户
- **登录尝试**: 5 次/小时/IP
- **注册**: 3 次/小时/IP

---

## 敏感数据处理

### 不得存储
- ❌ 明文 API 密钥
- ❌ 明文密码
- ❌ 信用卡信息
- ❌ 私钥文件

### 加密存储
- ✅ API 密钥（Fernet 加密）
- ✅ 用户密码（Bcrypt 哈希）
- ✅ OAuth Token（加密存储）

### 日志脱敏
```python
# 避免记录敏感信息
logger.info(f"User {user_id} logged in")  # ✅
logger.info(f"API key: {api_key}")        # ❌ 禁止

# 脱敏处理
logger.info(f"API key: {api_key[:8]}***")  # ✅
```

---

## 依赖安全

### 定期扫描
```bash
# Python 依赖扫描
pip-audit --desc

# Node.js 依赖扫描
npm audit --audit-level=moderate
```

### 依赖更新策略
- 关键安全更新: 立即更新
- 次要更新: 每月审查
- 主版本更新: 评估后更新

---

## HTTPS 配置

### 生产环境要求
- ✅ 强制 HTTPS
- ✅ HSTS 头部
- ✅ 安全的 TLS 配置（TLS 1.2+）
- ✅ 有效的 SSL 证书

### Nginx 配置示例
```nginx
# 强制 HTTPS
server {
    listen 80;
    return 301 https://$host$request_uri;
}

# HTTPS 配置
server {
    listen 443 ssl http2;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # 安全头部
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

---

## 环境变量安全

### 敏感配置
```bash
# .env（加入 .gitignore）
DATABASE_URL=postgresql://user:password@localhost/db
GOOGLE_API_KEY=AIzaSy...
JWT_SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-encryption-key-here
```

### 禁止提交
- ❌ .env 文件
- ❌ API 密钥
- ❌ 数据库密码
- ❌ 加密密钥

### 示例配置
```bash
# .env.example（可提交）
DATABASE_URL=postgresql://user:password@localhost/db
GOOGLE_API_KEY=your_google_api_key_here
JWT_SECRET_KEY=your_jwt_secret_key_here
```

---

## 错误处理

### 错误信息脱敏
```python
try:
    result = process_data(api_key, data)
except Exception as e:
    # ❌ 泄露敏感信息
    return {"error": str(e)}

    # ✅ 脱敏处理
    logger.error(f"Process failed: {e}")  # 详细信息记录到日志
    return {"error": "Processing failed", "error_code": "PROCESSING_ERROR"}
```

---

## 审计和监控

### 操作日志
记录关键操作：
- 用户登录/登出
- API 密钥创建/删除
- 敏感配置变更
- 异常访问尝试

### 监控指标
- 异常错误率
- 认证失败次数
- API 调用速率
- 资源使用情况

---

## 应急响应

### 密钥泄露处理
1. 立即轮换泄露的密钥
2. 撤销受影响的访问令牌
3. 通知受影响用户
4. 审查访问日志
5. 评估损失和影响

### 安全事件报告
- 记录事件详情
- 评估影响范围
- 采取缓解措施
- 事后分析和改进

---

**更新日期**：2026-01-09
**版本**：v1.0.0
