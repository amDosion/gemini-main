# 代码审查检查清单

本文档用于确保所有新代码都遵循统一的配置管理原则和架构设计。

## 1. 存储配置使用检查

### ✅ 必须使用 StorageManager

**检查项**:
- [ ] 所有存储配置的获取、解密和上传操作是否使用 `StorageManager`？
- [ ] 是否避免直接查询 `StorageConfig` 和 `ActiveStorage` 表？
- [ ] 是否避免直接调用 `decrypt_config()` 和 `StorageService.upload_file()`？

**正确示例**:
```python
# ✅ 正确：使用 StorageManager
manager = StorageManager(db, user_id)
result = await manager.upload_file(
    filename=filename,
    content=content,
    content_type=content_type,
    storage_id=storage_id  # 可选，如果指定则使用指定配置
)
```

**错误示例**:
```python
# ❌ 错误：直接查询数据库和解密
active = db.query(ActiveStorage).filter(...).first()
config = db.query(StorageConfig).filter(...).first()
decrypted_config = decrypt_config(config.config)
result = await StorageService.upload_file(...)
```

### ✅ 配置解密检查

**检查项**:
- [ ] 是否通过 `StorageManager` 自动处理配置解密？
- [ ] 是否避免手动调用 `decrypt_config()`？
- [ ] 是否处理了解密失败的情况（降级逻辑）？

**注意**: `StorageManager.upload_file()` 内部已经处理了配置解密，不需要手动解密。

---

## 2. 附件显示检查

### ✅ 使用统一的 URL 类型判断

**检查项**:
- [ ] 是否使用 `getUrlType()` 函数判断 URL 类型？
- [ ] 是否避免重复的 URL 类型判断逻辑（如 `url?.startsWith('data:')`）？

**正确示例**:
```typescript
// ✅ 正确：使用统一的 getUrlType() 函数
import { getUrlType } from '../../hooks/handlers/attachmentUtils';

const urlType = getUrlType(att.url, att.uploadStatus);
```

**错误示例**:
```typescript
// ❌ 错误：重复的 URL 类型判断逻辑
const urlType = att.url?.startsWith('data:') ? 'Base64 Data URL' :
               att.url?.startsWith('blob:') ? 'Blob URL' :
               att.url?.startsWith('http://') || att.url?.startsWith('https://') ? 
                 (att.uploadStatus === 'completed' ? '云存储URL' : 'HTTP临时URL') :
               '未知类型';
```

### ✅ 附件显示逻辑

**检查项**:
- [ ] 附件是否在跨模式切换时能正常显示？
- [ ] 是否不依赖上传状态（`uploadStatus`）来决定是否显示？
- [ ] 是否仅依赖 URL 的有效性来决定是否显示？

**原则**: 如果前端能够显示附件（URL 有效），则应该始终显示，无论上传状态如何。

---

## 3. 认证处理检查

### ✅ 使用统一的认证机制

**检查项**:
- [ ] 是否使用 `require_current_user` 或 `get_current_user_optional` 获取用户信息？
- [ ] 是否避免直接解析 JWT token？
- [ ] 是否使用 `UserScopedQuery` 进行用户范围查询？

**正确示例**:
```python
# ✅ 正确：使用统一的认证机制
from ...core.dependencies import require_current_user
from ...core.user_scoped_query import UserScopedQuery

@router.post("/endpoint")
async def endpoint(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    user_query = UserScopedQuery(db, user_id)
    # 使用 user_query 进行查询
```

**错误示例**:
```python
# ❌ 错误：直接解析 JWT token
token = request.headers.get("Authorization")
payload = decode_token(token)
user_id = payload.sub
```

---

## 4. 加密处理检查

### ✅ 使用统一的加密模块

**检查项**:
- [ ] 是否从 `core.encryption` 导入加密/解密函数？
- [ ] 是否避免使用 `utils.encryption`（已删除）？
- [ ] 是否使用 `encrypt_config()` 和 `decrypt_config()` 处理配置字典？
- [ ] 是否使用 `encrypt_data()` 和 `decrypt_data()` 处理单个字符串？

**正确示例**:
```python
# ✅ 正确：使用统一的加密模块
from ...core.encryption import encrypt_config, decrypt_config, encrypt_data, decrypt_data

# 加密配置字典
encrypted_config = encrypt_config(config_dict)

# 加密单个字符串
encrypted_key = encrypt_data(api_key)
```

**错误示例**:
```python
# ❌ 错误：使用已删除的 utils.encryption
from ...utils.encryption import decrypt_config  # 文件已删除
```

---

## 5. 错误处理检查

### ✅ 错误处理完整性

**检查项**:
- [ ] 是否处理了所有可能的异常情况？
- [ ] 是否提供了有意义的错误消息？
- [ ] 是否记录了详细的错误日志？

**正确示例**:
```python
try:
    result = await manager.upload_file(...)
except HTTPException as e:
    logger.error(f"[Upload] HTTP error: {e.detail}")
    return {"success": False, "error": e.detail}
except Exception as e:
    logger.error(f"[Upload] Unexpected error: {e}")
    return {"success": False, "error": str(e)}
```

---

## 6. 日志记录检查

### ✅ 日志记录充分性

**检查项**:
- [ ] 是否记录了关键操作步骤？
- [ ] 是否记录了配置解密状态？
- [ ] 是否记录了上传结果？
- [ ] 日志是否包含足够的上下文信息（user_id, filename, storage_id 等）？

**正确示例**:
```python
logger.info(f"[Storage] Async upload for user: {user_id}, file: {filename}")
logger.debug(f"[Storage] 已解密存储配置: {config.id} (provider={config.provider})")
logger.info(f"[Storage] Upload successful: {result.get('url', '')[:60]}...")
```

---

## 7. 代码质量检查

### ✅ 代码规范

**检查项**:
- [ ] 代码是否符合项目规范（PEP 8 / ESLint）？
- [ ] 函数是否有完整的文档字符串（docstring / JSDoc）？
- [ ] 是否有适当的类型注解（TypeScript / Python type hints）？
- [ ] 代码是否易于理解和维护？

### ✅ 测试覆盖

**检查项**:
- [ ] 是否为新功能添加了单元测试？
- [ ] 测试是否覆盖了主要场景（成功、失败、边界情况）？
- [ ] 测试是否使用了适当的 mock 策略？

---

## 8. 性能检查

### ✅ 性能优化

**检查项**:
- [ ] 是否避免了不必要的数据库查询？
- [ ] 是否使用了适当的缓存策略？
- [ ] 是否避免了重复的配置解密操作？

---

## 9. 安全检查

### ✅ 安全最佳实践

**检查项**:
- [ ] 敏感信息是否被正确加密？
- [ ] 日志中是否避免了敏感信息的泄露？
- [ ] 是否使用了 `mask_sensitive_fields()` 在日志中隐藏敏感信息？
- [ ] 用户权限是否被正确验证？

**正确示例**:
```python
# ✅ 正确：在日志中隐藏敏感信息
from ...core.encryption import mask_sensitive_fields

masked_config = mask_sensitive_fields(config)
logger.info(f"[Storage] Config: {masked_config}")
```

---

## 10. 向后兼容性检查

### ✅ 向后兼容

**检查项**:
- [ ] 是否支持未加密的历史数据？
- [ ] 是否提供了降级逻辑（解密失败时使用原配置）？
- [ ] API 接口是否保持向后兼容？

---

## 检查清单使用指南

### 何时使用

- **代码审查时**: 审查者应使用此清单检查所有新代码
- **提交代码前**: 开发者应自检代码是否符合清单要求
- **重构代码时**: 确保重构后的代码符合清单要求

### 如何使用

1. **逐项检查**: 按照清单逐项检查代码
2. **记录问题**: 对于不符合要求的代码，记录具体问题
3. **修复问题**: 修复所有发现的问题
4. **再次检查**: 修复后再次检查，确保所有项都通过

### 优先级

- **P0（必须）**: 存储配置使用、认证处理、加密处理
- **P1（重要）**: 附件显示、错误处理、日志记录
- **P2（建议）**: 代码质量、测试覆盖、性能优化

---

## 常见问题

### Q1: 什么时候应该使用 StorageManager？

**A**: 所有需要获取存储配置、解密配置或上传文件的地方都应该使用 `StorageManager`，而不是直接查询数据库。

### Q2: 什么时候应该使用 getUrlType()？

**A**: 所有需要判断 URL 类型的地方都应该使用 `getUrlType()`，而不是重复实现 URL 类型判断逻辑。

### Q3: 如何处理未加密的历史数据？

**A**: `StorageManager` 和 `decrypt_config()` 都支持未加密的历史数据，会自动降级使用原配置。

---

**文档版本**: 1.0  
**最后更新**: 2025-01-18  
**维护者**: 代码审查Agent
