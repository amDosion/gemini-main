# 完整附件处理与存储配置架构 - 任务文档

> **项目名称**: 完整附件处理与存储配置架构优化
> **版本**: v1.0
> **创建日期**: 2026-01-19
> **预计工期**: 2-3 周
> **团队规模**: 后端 1人 + 前端 1人

---

## 目录

1. [任务总览](#1-任务总览)
2. [阶段1: 修复后端配置解密问题（第1周）](#2-阶段1-修复后端配置解密问题第1周)
3. [阶段2: 优化前端跨模式附件显示（第1-2周）](#3-阶段2-优化前端跨模式附件显示第1-2周)
4. [阶段3: 合并加密文件（第2周）](#4-阶段3-合并加密文件第2周)
5. [阶段4: 统一配置管理（可选，第3周）](#5-阶段4-统一配置管理可选第3周)
6. [任务依赖关系](#6-任务依赖关系)
7. [风险缓解任务](#7-风险缓解任务)

---

## 1. 任务总览

### 1.1 里程碑

| 里程碑 | 时间 | 交付物 | 验收标准 |
|-------|------|--------|---------|
| **M1: 后端配置解密修复完成** | 第1周末 | `storage.py` 两个函数已修复 | 单元测试通过，加密配置上传成功 |
| **M2: 前端跨模式显示优化完成** | 第2周末 | URL类型判断统一，跨模式附件显示正常 | 集成测试通过，所有场景验证通过 |
| **M3: 加密文件合并完成** | 第2周末 | `utils/encryption.py` 已合并到 `core/encryption.py` | 所有导入已更新，功能测试通过 |
| **M4: 统一配置管理完成（可选）** | 第3周末 | `storage.py` 使用 `StorageManager` | 代码审查通过，文档完整 |

### 1.2 优先级定义

- **P0**: 关键任务，阻塞后续工作，必须按时完成
- **P1**: 重要任务，影响项目进度
- **P2**: 次要任务，可延后或并行

---

## 2. 阶段1: 修复后端配置解密问题（第1周）

### 2.1 任务分解

#### TASK-101: 修复 `upload_to_active_storage_async` 函数（P0）

**负责人**: 后端开发
**工时**: 2小时
**依赖**: 无

**详细步骤**:

1. **定位问题函数**
   - 文件: `backend/app/routers/storage/storage.py`
   - 函数: `upload_to_active_storage_async()` (line 263-315)

2. **添加解密逻辑**
   ```python
   # ✅ 解密配置
   from ...core.encryption import decrypt_config
   try:
       decrypted_config = decrypt_config(config.config)
       logger.debug(f"[Storage] 已解密存储配置: {config.id} (provider={config.provider})")
   except Exception as e:
       logger.error(f"[Storage] 解密存储配置失败: {e}")
       logger.warning(f"[Storage] 使用未解密的配置（可能是历史数据）: {config.id}")
       decrypted_config = config.config  # 降级：使用原配置
   
   # ✅ 使用解密后的配置
   result = await StorageService.upload_file(
       filename=filename,
       content=content,
       content_type=content_type,
       provider=config.provider,
       config=decrypted_config
   )
   ```

3. **添加单元测试**
   - 测试加密配置场景
   - 测试未加密配置场景（向后兼容）

4. **验证**
   - 使用加密的存储配置测试上传功能
   - 验证上传成功（配置已正确解密）
   - 检查日志确认解密过程

**验收标准**:
- [ ] 代码修改完成
- [ ] 单元测试通过
- [ ] 使用加密配置测试上传，上传成功
- [ ] 日志中显示解密过程

---

#### TASK-102: 修复 `process_upload_task` 函数（P0）

**负责人**: 后端开发
**工时**: 2小时
**依赖**: 无

**详细步骤**:

1. **定位问题函数**
   - 文件: `backend/app/routers/storage/storage.py`
   - 函数: `process_upload_task()` (line 383-520)

2. **添加解密逻辑**
   ```python
   if not config or not config.enabled:
       raise Exception("存储配置不可用")
   
   # ✅ 解密配置
   from ...core.encryption import decrypt_config
   try:
       decrypted_config = decrypt_config(config.config)
       logger.debug(f"[UploadTask] 已解密存储配置: {config.id} (provider={config.provider})")
   except Exception as e:
       logger.error(f"[UploadTask] 解密存储配置失败: {e}")
       logger.warning(f"[UploadTask] 使用未解密的配置（可能是历史数据）: {config.id}")
       decrypted_config = config.config  # 降级：使用原配置
   
   # ... 读取文件内容 ...
   
   # 4. 上传到云存储
   result = await StorageService.upload_file(
       filename=task.filename,
       content=image_content,
       content_type='image/png',
       provider=config.provider,
       config=decrypted_config  # ✅ 已解密
   )
   ```

3. **添加单元测试**
   - 测试加密配置场景
   - 测试未加密配置场景（向后兼容）

4. **验证**
   - 使用加密的存储配置测试上传功能
   - 验证上传成功（配置已正确解密）
   - 检查日志确认解密过程

**验收标准**:
- [ ] 代码修改完成
- [ ] 单元测试通过
- [ ] 使用加密配置测试上传，上传成功
- [ ] 日志中显示解密过程

---

### 2.2 测试任务

#### TASK-103: 添加配置解密单元测试（P1）

**负责人**: 后端开发
**工时**: 3小时
**依赖**: TASK-101, TASK-102

**测试用例**:

1. **测试加密配置场景**
   ```python
   def test_upload_with_encrypted_config():
       # 1. 创建加密的存储配置
       encrypted_config = encrypt_config({
           "accessKeyId": "test-key",
           "accessKeySecret": "test-secret",
           "domain": "https://example.com"
       })
       
       # 2. 保存到数据库
       config = StorageConfig(
           id="test-config",
           user_id="test-user",
           provider="lsky",
           config=encrypted_config,
           enabled=True
       )
       db.add(config)
       db.commit()
       
       # 3. 调用 upload_to_active_storage_async
       result = await upload_to_active_storage_async(
           content=b"test",
           filename="test.png",
           content_type="image/png",
           user_id="test-user"
       )
       
       # 4. 验证是否成功（应该成功，因为已解密）
       assert result["success"] == True
   ```

2. **测试未加密配置场景（向后兼容）**
   ```python
   def test_upload_with_unencrypted_config():
       # 1. 使用未加密的配置（历史数据）
       unencrypted_config = {
           "accessKeyId": "test-key",
           "accessKeySecret": "test-secret",
           "domain": "https://example.com"
       }
       
       # 2. 保存到数据库
       config = StorageConfig(...)
       db.add(config)
       db.commit()
       
       # 3. 调用 upload_to_active_storage_async
       result = await upload_to_active_storage_async(...)
       
       # 4. 验证是否成功（应该成功，因为降级使用原配置）
       assert result["success"] == True
   ```

**验收标准**:
- [ ] 所有测试用例通过
- [ ] 测试覆盖率 > 90%

---

## 3. 阶段2: 优化前端跨模式附件显示（第1-2周）

### 3.1 任务分解

#### TASK-201: 创建统一的 `getUrlType()` 函数（P1）

**负责人**: 前端开发
**工时**: 1小时
**依赖**: 无

**详细步骤**:

1. **创建函数**
   - 文件: `frontend/hooks/handlers/attachmentUtils.ts`
   - 函数: `getUrlType(url: string | undefined, uploadStatus?: string): string`

2. **实现逻辑**
   ```typescript
   export const getUrlType = (url: string | undefined, uploadStatus?: string): string => {
     if (!url) return '空URL';
     
     if (url.startsWith('data:')) {
       return 'Base64 Data URL (AI原始返回)';
     }
     
     if (url.startsWith('blob:')) {
       return 'Blob URL (处理后的本地URL)';
     }
     
     if (url.startsWith('/api/temp-images/')) {
       return '临时代理URL (后端创建)';
     }
     
     if (url.startsWith('http://') || url.startsWith('https://')) {
       return uploadStatus === 'completed' 
         ? '云存储URL (已上传完成)' 
         : 'HTTP临时URL (AI原始返回)';
     }
     
     return '未知类型';
   };
   ```

3. **导出函数**
   - 确保函数被正确导出

**验收标准**:
- [ ] 函数创建完成
- [ ] 所有URL类型都能正确识别
- [ ] `/api/temp-images/` 格式被正确识别为"临时代理URL"

---

#### TASK-202: 在 `useChat.ts` 中使用 `getUrlType()`（P1）

**负责人**: 前端开发
**工时**: 30分钟
**依赖**: TASK-201

**详细步骤**:

1. **导入函数**
   ```typescript
   import { getUrlType } from './handlers/attachmentUtils';
   ```

2. **替换现有逻辑**
   - 位置: `frontend/hooks/useChat.ts` (line 191-195)
   - 替换现有的URL类型判断逻辑

3. **验证**
   - 检查日志确认URL类型正确识别

**验收标准**:
- [ ] 代码修改完成
- [ ] 日志中显示正确的URL类型
- [ ] `/api/temp-images/` 格式被正确识别

---

#### TASK-203: 在 `ImageGenView.tsx` 中使用 `getUrlType()`（P1）

**负责人**: 前端开发
**工时**: 30分钟
**依赖**: TASK-201

**详细步骤**:

1. **导入函数**
   ```typescript
   import { getUrlType } from '../../hooks/handlers/attachmentUtils';
   ```

2. **替换现有逻辑**
   - 位置: `frontend/components/views/ImageGenView.tsx` (line 75-79)
   - 替换现有的URL类型判断逻辑

3. **验证**
   - 检查日志确认URL类型正确识别

**验收标准**:
- [ ] 代码修改完成
- [ ] 日志中显示正确的URL类型

---

#### TASK-204: 在 `ImageEditView.tsx` 中使用 `getUrlType()`（P1）

**负责人**: 前端开发
**工时**: 30分钟
**依赖**: TASK-201

**详细步骤**:

1. **导入函数**
   ```typescript
   import { getUrlType } from '../../hooks/handlers/attachmentUtils';
   ```

2. **替换现有逻辑**
   - 位置: `frontend/components/views/ImageEditView.tsx` (相关位置)
   - 替换现有的URL类型判断逻辑

3. **验证**
   - 检查日志确认URL类型正确识别

**验收标准**:
- [ ] 代码修改完成
- [ ] 日志中显示正确的URL类型

---

#### TASK-205: 验证跨模式附件显示（P0）

**负责人**: 前端开发
**工时**: 2小时
**依赖**: TASK-201, TASK-202, TASK-203, TASK-204

**测试场景**:

1. **场景1: 临时URL + 上传中**
   - 在 `gen` 模式生成图片（`uploadStatus: 'pending'`）
   - 点击编辑按钮
   - 验证附件栏能立即显示

2. **场景2: 临时URL + 上传失败**
   - 在 `gen` 模式生成图片（`uploadStatus: 'failed'`）
   - 点击编辑按钮
   - 验证附件栏能立即显示

3. **场景3: 云URL + 上传完成**
   - 在 `gen` 模式生成图片（`uploadStatus: 'completed'`）
   - 点击编辑按钮
   - 验证附件栏能立即显示

4. **场景4: 云URL + 上传中**
   - 在 `gen` 模式生成图片（`uploadStatus: 'pending'`，但已查询到云URL）
   - 点击编辑按钮
   - 验证附件栏能立即显示

**验收标准**:
- [ ] 所有测试场景通过
- [ ] 附件栏在所有场景下都能正常显示
- [ ] 日志中显示正确的URL类型和附件信息

---

## 4. 阶段3: 合并加密文件（第2周）

### 4.1 任务分解

#### TASK-301: 合并函数到 `core/encryption.py`（P1）

**负责人**: 后端开发
**工时**: 2小时
**依赖**: 无

**详细步骤**:

1. **读取 `utils/encryption.py` 的内容**
   - 获取 `SENSITIVE_FIELDS` 常量
   - 获取 `encrypt_config()` 函数
   - 获取 `decrypt_config()` 函数
   - 获取 `mask_sensitive_fields()` 函数

2. **添加到 `core/encryption.py`**
   - 在文件末尾添加配置字典加密/解密部分
   - 更新文档字符串

3. **修改 `is_encrypted()` 的调用**
   - `encrypt_config()` 和 `decrypt_config()` 内部调用 `is_encrypted()` 时，使用 `core/encryption.py` 中的实现（通过实际解密尝试）

4. **移除 `_get_encryption_key()` 函数**
   - 直接使用 `core/encryption.py` 中的 `get_encryption_key()` 和 `_get_encryption_key_bytes()`

5. **运行测试**
   - 确保功能正常

**验收标准**:
- [ ] 所有函数已合并到 `core/encryption.py`
- [ ] 文档字符串已更新
- [ ] 单元测试通过

---

#### TASK-302: 更新 `upload_worker_pool.py` 的导入（P1）

**负责人**: 后端开发
**工时**: 15分钟
**依赖**: TASK-301

**详细步骤**:

1. **修改导入语句**
   - 文件: `backend/app/services/common/upload_worker_pool.py`
   - 位置: Line 25
   - 修改前: `from ...utils.encryption import decrypt_config`
   - 修改后: `from ...core.encryption import decrypt_config`

2. **验证**
   - 运行测试确保功能正常

**验收标准**:
- [ ] 导入路径已更新
- [ ] 功能测试通过

---

#### TASK-303: 更新 `upload_tasks.py` 的导入（P1）

**负责人**: 后端开发
**工时**: 15分钟
**依赖**: TASK-301

**详细步骤**:

1. **修改导入语句**
   - 文件: `backend/app/tasks/upload_tasks.py`
   - 位置: Line 70
   - 修改前: `from app.utils.encryption import decrypt_config`
   - 修改后: `from app.core.encryption import decrypt_config`

2. **验证**
   - 运行测试确保功能正常

**验收标准**:
- [ ] 导入路径已更新
- [ ] 功能测试通过

---

#### TASK-304: 更新 `storage_manager.py` 的导入（P1）

**负责人**: 后端开发
**工时**: 15分钟
**依赖**: TASK-301

**详细步骤**:

1. **修改导入语句**
   - 文件: `backend/app/services/storage/storage_manager.py`
   - 位置: Line 19
   - 修改前: `from ...utils.encryption import encrypt_config, decrypt_config, mask_sensitive_fields`
   - 修改后: `from ...core.encryption import encrypt_config, decrypt_config, mask_sensitive_fields`

2. **验证**
   - 运行测试确保功能正常

**验收标准**:
- [ ] 导入路径已更新
- [ ] 功能测试通过

---

#### TASK-305: 删除 `utils/encryption.py`（P1）

**负责人**: 后端开发
**工时**: 15分钟
**依赖**: TASK-301, TASK-302, TASK-303, TASK-304

**详细步骤**:

1. **确认所有导入已更新**
   - 检查所有使用 `utils.encryption` 的文件
   - 确认都已更新为 `core.encryption`

2. **删除文件**
   - 删除 `backend/app/utils/encryption.py`

3. **运行完整测试套件**
   - 确保所有功能正常

**验收标准**:
- [ ] 文件已删除
- [ ] 所有测试通过
- [ ] 没有导入错误

---

#### TASK-306: 添加加密文件合并测试（P1）

**负责人**: 后端开发
**工时**: 2小时
**依赖**: TASK-301, TASK-302, TASK-303, TASK-304, TASK-305

**测试用例**:

1. **测试存储配置加密/解密**
   ```python
   def test_encrypt_decrypt_config():
       config = {
           "accessKeyId": "test-key",
           "accessKeySecret": "test-secret",
           "domain": "example.com"
       }
       encrypted = encrypt_config(config)
       decrypted = decrypt_config(encrypted)
       assert decrypted["accessKeyId"] == "test-key"
       assert decrypted["accessKeySecret"] == "test-secret"
   ```

2. **测试嵌套字典处理**
   ```python
   def test_nested_dict_encryption():
       config = {
           "nested": {
               "accessKeyId": "test-key",
               "accessKeySecret": "test-secret"
           },
           "domain": "example.com"
       }
       encrypted = encrypt_config(config)
       decrypted = decrypt_config(encrypted)
       assert decrypted["nested"]["accessKeyId"] == "test-key"
   ```

3. **测试历史数据兼容性**
   ```python
   def test_historical_data_compatibility():
       config = {
           "accessKeyId": "plain-text-key",  # 未加密
           "domain": "example.com"
       }
       decrypted = decrypt_config(config)
       assert decrypted["accessKeyId"] == "plain-text-key"
   ```

4. **测试 `is_encrypted()` 准确性**
   ```python
   def test_is_encrypted_accuracy():
       encrypted_data = encrypt_data("test-key")
       assert is_encrypted(encrypted_data) == True
       
       plain_text = "sk-1234567890"
       assert is_encrypted(plain_text) == False
   ```

**验收标准**:
- [ ] 所有测试用例通过
- [ ] 测试覆盖率 > 90%

---

## 5. 阶段4: 统一配置管理（可选，第3周）

### 5.1 任务分解

#### TASK-401: 重构 `upload_to_active_storage_async` 使用 `StorageManager`（P2）

**负责人**: 后端开发
**工时**: 2小时
**依赖**: TASK-101

**详细步骤**:

1. **修改函数实现**
   ```python
   async def upload_to_active_storage_async(content: bytes, filename: str, content_type: str, user_id: Optional[str] = None) -> dict:
       """异步上传文件到当前激活的存储配置"""
       db = SessionLocal()
       try:
           resolved_user_id = user_id or "default"
           logger.info(f"[Storage] Async upload for user: {resolved_user_id}, file: {filename}")

           # ✅ 使用 StorageManager（自动处理解密）
           manager = StorageManager(db, resolved_user_id)
           result = await manager.upload_file(
               filename=filename,
               content=content,
               content_type=content_type,
               storage_id=None  # 使用激活的配置
           )

           return result
       except Exception as e:
           logger.error(f"[Storage] Async upload error: {e}")
           return {"success": False, "error": str(e)}
       finally:
           db.close()
   ```

2. **添加单元测试**
   - 测试使用 `StorageManager` 的上传功能

3. **验证**
   - 运行测试确保功能正常

**验收标准**:
- [ ] 代码重构完成
- [ ] 单元测试通过
- [ ] 功能测试通过

---

#### TASK-402: 重构 `process_upload_task` 使用 `StorageManager`（P2）

**负责人**: 后端开发
**工时**: 2小时
**依赖**: TASK-102

**详细步骤**:

1. **修改函数实现**
   ```python
   async def process_upload_task(task_id: str, _db: Session = None):
       """后台处理上传任务"""
       db = SessionLocal()
       try:
           # ... 查询任务 ...
           
           # ✅ 获取用户 ID（用于 StorageManager）
           user_id = "default"
           if task.session_id:
               session = db.query(ChatSession).filter(ChatSession.id == task.session_id).first()
               if session:
                   user_id = session.user_id
           
           # ... 读取文件内容 ...
           
           # ✅ 使用 StorageManager（自动处理解密）
           manager = StorageManager(db, user_id)
           result = await manager.upload_file(
               filename=task.filename,
               content=image_content,
               content_type='image/png',
               storage_id=task.storage_id  # 如果指定了 storage_id，使用它；否则使用激活的配置
           )
           
           # ... 处理结果 ...
       except Exception as e:
           # ... 错误处理 ...
       finally:
           db.close()
   ```

2. **添加单元测试**
   - 测试使用 `StorageManager` 的任务处理功能

3. **验证**
   - 运行测试确保功能正常

**验收标准**:
- [ ] 代码重构完成
- [ ] 单元测试通过
- [ ] 功能测试通过

---

#### TASK-403: 添加代码审查检查清单（P2）

**负责人**: 后端开发
**工时**: 1小时
**依赖**: TASK-401, TASK-402

**详细步骤**:

1. **创建检查清单文档**
   - 存储配置使用检查
   - 附件显示检查
   - 认证处理检查

2. **添加到代码审查流程**
   - 确保所有新代码都通过检查清单

**验收标准**:
- [ ] 检查清单文档创建完成
- [ ] 代码审查流程已更新

---

## 6. 任务依赖关系

### 6.1 依赖图

```
阶段1: 后端配置解密修复
  ├─ TASK-101: 修复 upload_to_active_storage_async (P0)
  ├─ TASK-102: 修复 process_upload_task (P0)
  └─ TASK-103: 添加单元测试 (P1)
      └─ 依赖: TASK-101, TASK-102

阶段2: 前端跨模式附件显示优化
  ├─ TASK-201: 创建 getUrlType() 函数 (P1)
  ├─ TASK-202: 在 useChat.ts 中使用 (P1)
  │   └─ 依赖: TASK-201
  ├─ TASK-203: 在 ImageGenView.tsx 中使用 (P1)
  │   └─ 依赖: TASK-201
  ├─ TASK-204: 在 ImageEditView.tsx 中使用 (P1)
  │   └─ 依赖: TASK-201
  └─ TASK-205: 验证跨模式附件显示 (P0)
      └─ 依赖: TASK-201, TASK-202, TASK-203, TASK-204

阶段3: 合并加密文件
  ├─ TASK-301: 合并函数到 core/encryption.py (P1)
  ├─ TASK-302: 更新 upload_worker_pool.py (P1)
  │   └─ 依赖: TASK-301
  ├─ TASK-303: 更新 upload_tasks.py (P1)
  │   └─ 依赖: TASK-301
  ├─ TASK-304: 更新 storage_manager.py (P1)
  │   └─ 依赖: TASK-301
  ├─ TASK-305: 删除 utils/encryption.py (P1)
  │   └─ 依赖: TASK-301, TASK-302, TASK-303, TASK-304
  └─ TASK-306: 添加测试 (P1)
      └─ 依赖: TASK-301, TASK-302, TASK-303, TASK-304, TASK-305

阶段4: 统一配置管理（可选）
  ├─ TASK-401: 重构 upload_to_active_storage_async (P2)
  │   └─ 依赖: TASK-101
  ├─ TASK-402: 重构 process_upload_task (P2)
  │   └─ 依赖: TASK-102
  └─ TASK-403: 添加代码审查检查清单 (P2)
      └─ 依赖: TASK-401, TASK-402
```

### 6.2 关键路径

**关键路径 1: 后端配置解密修复**
```
TASK-101 → TASK-102 → TASK-103
```

**关键路径 2: 前端跨模式附件显示优化**
```
TASK-201 → TASK-202 → TASK-203 → TASK-204 → TASK-205
```

**关键路径 3: 合并加密文件**
```
TASK-301 → TASK-302 → TASK-303 → TASK-304 → TASK-305 → TASK-306
```

---

## 7. 风险缓解任务

### 7.1 技术风险缓解

#### TASK-701: 配置解密失败降级处理（P0）

**负责人**: 后端开发
**工时**: 1小时
**依赖**: TASK-101, TASK-102

**任务描述**:
- 确保所有配置解密操作都包含错误处理和降级逻辑
- 支持未加密的历史数据

**验收标准**:
- [ ] 所有解密操作都有 try-except 块
- [ ] 解密失败时降级使用原配置
- [ ] 日志中记录解密失败的情况

---

#### TASK-702: `is_encrypted()` 行为变化测试（P1）

**负责人**: 后端开发
**工时**: 2小时
**依赖**: TASK-301

**任务描述**:
- 测试 `is_encrypted()` 从格式检查改为实际解密尝试的行为变化
- 确保向后兼容

**验收标准**:
- [ ] 所有测试用例通过
- [ ] 向后兼容性测试通过

---

### 7.2 业务风险缓解

#### TASK-703: 历史数据兼容性测试（P0）

**负责人**: 后端开发
**工时**: 2小时
**依赖**: TASK-101, TASK-102, TASK-301

**任务描述**:
- 测试未加密的历史数据
- 确保系统能同时处理加密和未加密的配置

**验收标准**:
- [ ] 未加密配置能正常使用
- [ ] 加密配置能正常使用
- [ ] 日志中正确记录配置状态

---

## 8. 任务时间估算

### 8.1 阶段1: 后端配置解密修复

| 任务 | 工时 | 累计 |
|------|------|------|
| TASK-101 | 2小时 | 2小时 |
| TASK-102 | 2小时 | 4小时 |
| TASK-103 | 3小时 | 7小时 |

**总计**: 7小时（约1天）

---

### 8.2 阶段2: 前端跨模式附件显示优化

| 任务 | 工时 | 累计 |
|------|------|------|
| TASK-201 | 1小时 | 1小时 |
| TASK-202 | 0.5小时 | 1.5小时 |
| TASK-203 | 0.5小时 | 2小时 |
| TASK-204 | 0.5小时 | 2.5小时 |
| TASK-205 | 2小时 | 4.5小时 |

**总计**: 4.5小时（约0.5天）

---

### 8.3 阶段3: 合并加密文件

| 任务 | 工时 | 累计 |
|------|------|------|
| TASK-301 | 2小时 | 2小时 |
| TASK-302 | 0.25小时 | 2.25小时 |
| TASK-303 | 0.25小时 | 2.5小时 |
| TASK-304 | 0.25小时 | 2.75小时 |
| TASK-305 | 0.25小时 | 3小时 |
| TASK-306 | 2小时 | 5小时 |

**总计**: 5小时（约0.5天）

---

### 8.4 阶段4: 统一配置管理（可选）

| 任务 | 工时 | 累计 |
|------|------|------|
| TASK-401 | 2小时 | 2小时 |
| TASK-402 | 2小时 | 4小时 |
| TASK-403 | 1小时 | 5小时 |

**总计**: 5小时（约0.5天）

---

### 8.5 风险缓解任务

| 任务 | 工时 | 累计 |
|------|------|------|
| TASK-701 | 1小时 | 1小时 |
| TASK-702 | 2小时 | 3小时 |
| TASK-703 | 2小时 | 5小时 |

**总计**: 5小时（约0.5天）

---

### 8.6 总工时估算

**必须完成的任务**（阶段1-3）:
- 阶段1: 7小时
- 阶段2: 4.5小时
- 阶段3: 5小时
- 风险缓解: 5小时
- **小计**: 21.5小时（约3天）

**可选任务**（阶段4）:
- 阶段4: 5小时（约0.5天）

**总计**: 26.5小时（约3.5天）

---

## 9. 任务优先级总结

### 9.1 P0 任务（关键，必须完成）

1. TASK-101: 修复 `upload_to_active_storage_async` 函数
2. TASK-102: 修复 `process_upload_task` 函数
3. TASK-205: 验证跨模式附件显示
4. TASK-701: 配置解密失败降级处理
5. TASK-703: 历史数据兼容性测试

### 9.2 P1 任务（重要）

1. TASK-103: 添加配置解密单元测试
2. TASK-201: 创建统一的 `getUrlType()` 函数
3. TASK-202: 在 `useChat.ts` 中使用 `getUrlType()`
4. TASK-203: 在 `ImageGenView.tsx` 中使用 `getUrlType()`
5. TASK-204: 在 `ImageEditView.tsx` 中使用 `getUrlType()`
6. TASK-301: 合并函数到 `core/encryption.py`
7. TASK-302: 更新 `upload_worker_pool.py` 的导入
8. TASK-303: 更新 `upload_tasks.py` 的导入
9. TASK-304: 更新 `storage_manager.py` 的导入
10. TASK-305: 删除 `utils/encryption.py`
11. TASK-306: 添加加密文件合并测试
12. TASK-702: `is_encrypted()` 行为变化测试

### 9.3 P2 任务（次要，可选）

1. TASK-401: 重构 `upload_to_active_storage_async` 使用 `StorageManager`
2. TASK-402: 重构 `process_upload_task` 使用 `StorageManager`
3. TASK-403: 添加代码审查检查清单

---

**文档版本**: 1.0  
**创建日期**: 2026-01-19  
**最后更新**: 2026-01-19
