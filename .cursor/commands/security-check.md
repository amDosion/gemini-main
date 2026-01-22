# 安全检查

对代码进行专门的安全审计。

## 检查项目

### 1. 认证和授权

```python
# 检查：所有敏感端点是否使用认证
@router.post("/endpoint")
async def endpoint(
    user_id: str = Depends(require_current_user)  # ✅ 必须有
):
    pass
```

### 2. 数据隔离

```python
# 检查：所有查询是否加 user_id 过滤
items = db.query(Model).filter(
    Model.user_id == user_id  # ✅ 必须有
).all()
```

### 3. API Key 安全

```python
# 检查：API Key 是否在 credential_manager 统一解密
api_key, base_url = await get_provider_credentials(
    provider=provider,
    db=db,
    user_id=user_id
)

# ❌ 禁止：直接从请求获取并使用未加密的 API Key
# ❌ 禁止：在日志中记录 API Key
logger.info(f"API Key: {api_key}")  # 禁止！
```

### 4. 输入验证

```python
# 检查：是否使用 Pydantic 模型验证
class RequestModel(BaseModel):
    field: str = Field(..., min_length=1, max_length=1000)

# ❌ 危险：直接使用未验证的输入
query = f"SELECT * FROM users WHERE name = '{request.name}'"  # SQL 注入！
```

### 5. XSS 防护

```typescript
// 检查：是否正确转义用户输入
// ❌ 危险：
<div dangerouslySetInnerHTML={{ __html: userContent }} />

// ✅ 安全：使用 DOMPurify
import DOMPurify from 'dompurify';
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(userContent) }} />
```

### 6. 敏感信息暴露

```python
# 检查：响应是否返回敏感字段
def to_dict(self):
    return {
        "id": self.id,
        "hasApiKey": bool(self.api_key),  # ✅ 只返回是否存在
        # "apiKey": self.api_key,  # ❌ 禁止返回明文
    }
```

### 7. CORS 配置

```python
# 检查：CORS 是否配置正确
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:21573"],  # ✅ 明确指定
    # allow_origins=["*"],  # ❌ 危险：允许所有来源
)
```

### 8. JWT 安全

```python
# 检查：
# - JWT 密钥是否足够强
# - Token 过期时间是否合理
# - 是否正确验证 Token
```

## 输出格式

```markdown
## 安全审计报告

### 严重漏洞 (Critical)
- [ ] **[漏洞名称]**
  - 类型：[SQL注入/XSS/认证绕过/...]
  - 位置：[文件:行号]
  - 描述：[漏洞描述]
  - 影响：[可能的攻击场景]
  - 修复：[修复方案]

### 高风险问题 (High)
...

### 中风险问题 (Medium)
...

### 低风险问题 (Low)
...

### 安全建议
- [改进建议]

### 检查通过项
- [已正确实现的安全措施]
```

## 使用示例

```
/security-check backend/app/routers/auth/auth.py
```

```
/security-check 检查整个认证模块的安全性
```
