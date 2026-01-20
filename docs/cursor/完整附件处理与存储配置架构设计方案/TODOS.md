# 完整附件处理与存储配置架构 - 完整TODOS清单

> **项目名称**: 完整附件处理与存储配置架构优化
> **版本**: v1.0
> **创建日期**: 2026-01-19
> **状态**: 待实施

---

## 📋 目录

1. [TODOS总览](#1-todos总览)
2. [阶段1: 修复后端配置解密问题](#2-阶段1-修复后端配置解密问题)
3. [阶段2: 优化前端跨模式附件显示](#3-阶段2-优化前端跨模式附件显示)
4. [阶段3: 合并加密文件](#4-阶段3-合并加密文件)
5. [阶段4: 统一配置管理（可选）](#5-阶段4-统一配置管理可选)
6. [多Agent实施计划](#6-多agent实施计划)
7. [验收检查清单](#7-验收检查清单)

---

## 1. TODOS总览

### 1.1 任务统计

| 阶段 | P0任务 | P1任务 | P2任务 | 总任务数 | 总工时 |
|------|--------|--------|--------|---------|--------|
| 阶段1: 后端配置解密修复 | 2 | 1 | 0 | 3 | 7小时 |
| 阶段2: 前端跨模式显示优化 | 1 | 4 | 0 | 5 | 4.5小时 |
| 阶段3: 合并加密文件 | 0 | 6 | 0 | 6 | 5小时 |
| 阶段4: 统一配置管理（可选） | 0 | 0 | 3 | 3 | 5小时 |
| 风险缓解任务 | 2 | 1 | 0 | 3 | 5小时 |
| **总计** | **5** | **12** | **3** | **20** | **26.5小时** |

### 1.2 里程碑

| 里程碑 | 时间 | 交付物 | 验收标准 |
|-------|------|--------|---------|
| **M1: 后端配置解密修复完成** | 第1周末 | `storage.py` 两个函数已修复 | 单元测试通过，加密配置上传成功 |
| **M2: 前端跨模式显示优化完成** | 第2周末 | URL类型判断统一，跨模式附件显示正常 | 集成测试通过，所有场景验证通过 |
| **M3: 加密文件合并完成** | 第2周末 | `utils/encryption.py` 已合并到 `core/encryption.py` | 所有导入已更新，功能测试通过 |
| **M4: 统一配置管理完成（可选）** | 第3周末 | `storage.py` 使用 `StorageManager` | 代码审查通过，文档完整 |

---

## 2. 阶段1: 修复后端配置解密问题

### ✅ TASK-101: 修复 `upload_to_active_storage_async` 函数

**优先级**: P0（关键）  
**负责人**: 后端开发Agent  
**工时**: 2小时  
**依赖**: 无  
**状态**: ⏳ 待开始

---

#### 📝 任务描述

修复 `backend/app/routers/storage/storage.py` 中的 `upload_to_active_storage_async()` 函数，添加配置解密逻辑，确保加密的存储配置能正常使用。

---

#### 🔍 自问自答（验证理解）

**Q1: 为什么需要修复这个函数？**
- **A**: 当前函数直接传递 `config.config`（可能是加密的）给 `StorageService.upload_file()`，导致加密配置无法正常使用，上传失败。

**Q2: 修复的核心逻辑是什么？**
- **A**: 在调用 `StorageService.upload_file()` 之前，使用 `decrypt_config()` 解密配置，并添加错误处理和降级逻辑。

**Q3: 如何处理历史数据（未加密配置）？**
- **A**: 使用 try-except 块捕获解密失败，如果解密失败，降级使用原配置（可能是历史数据，未加密）。

**Q4: 如何确保修复不会破坏现有功能？**
- **A**: 添加单元测试，测试加密配置和未加密配置两种场景，确保向后兼容。

---

#### 🎯 论证（验证方案正确性）

**论证1: 方案可行性**
- ✅ `decrypt_config()` 函数已存在且经过验证
- ✅ 其他文件（`upload_worker_pool.py`、`storage_manager.py`）已使用相同方案
- ✅ 降级逻辑确保向后兼容

**论证2: 方案安全性**
- ✅ 解密失败时不会暴露敏感信息
- ✅ 日志记录解密过程，便于排查问题
- ✅ 支持未加密的历史数据，不会导致功能失败

**论证3: 方案一致性**
- ✅ 与其他文件的解密逻辑保持一致
- ✅ 使用统一的 `decrypt_config()` 函数
- ✅ 错误处理方式与其他文件一致

---

#### 📋 详细步骤

1. **定位问题函数**
   - [ ] 打开文件: `backend/app/routers/storage/storage.py`
   - [ ] 定位函数: `upload_to_active_storage_async()` (line 263-315)
   - [ ] 确认函数签名和参数

2. **添加解密逻辑**
   - [ ] 在函数开始处导入: `from ...core.encryption import decrypt_config`
   - [ ] 在获取 `config` 后，添加解密逻辑:
     ```python
     # ✅ 解密配置
     try:
         decrypted_config = decrypt_config(config.config)
         logger.debug(f"[Storage] 已解密存储配置: {config.id} (provider={config.provider})")
     except Exception as e:
         logger.error(f"[Storage] 解密存储配置失败: {e}")
         logger.warning(f"[Storage] 使用未解密的配置（可能是历史数据）: {config.id}")
         decrypted_config = config.config  # 降级：使用原配置
     ```
   - [ ] 修改 `StorageService.upload_file()` 调用，使用 `decrypted_config` 而不是 `config.config`

3. **添加单元测试**
   - [ ] 创建测试文件: `tests/test_storage_decrypt.py`
   - [ ] 测试加密配置场景:
     ```python
     def test_upload_with_encrypted_config():
         # 创建加密配置
         encrypted_config = encrypt_config({
             "accessKeyId": "test-key",
             "accessKeySecret": "test-secret"
         })
         # 测试上传功能
         ...
     ```
   - [ ] 测试未加密配置场景（向后兼容）

4. **代码审查**
   - [ ] 检查代码风格和规范
   - [ ] 检查错误处理是否完整
   - [ ] 检查日志记录是否充分

---

#### ✅ 验收标准

**功能验收**:
- [ ] 代码修改完成，无语法错误
- [ ] 单元测试通过（加密配置场景）
- [ ] 单元测试通过（未加密配置场景）
- [ ] 使用加密的存储配置测试上传功能，上传成功
- [ ] 使用未加密的存储配置测试上传功能，上传成功（向后兼容）

**代码质量验收**:
- [ ] 代码符合项目规范（PEP 8）
- [ ] 函数有完整的文档字符串
- [ ] 错误处理完整（try-except 块）
- [ ] 日志记录充分（debug、error、warning）

**测试验收**:
- [ ] 单元测试覆盖率 > 90%
- [ ] 所有测试用例通过
- [ ] 测试代码可读性强，易于维护

**集成验收**:
- [ ] 与现有代码集成无冲突
- [ ] 不影响其他功能
- [ ] 性能无明显下降（解密操作 < 10ms）

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **后端开发Agent**: 负责代码修改和单元测试
2. **测试Agent**: 负责集成测试和性能测试
3. **代码审查Agent**: 负责代码审查和规范检查

**协作流程**:
```
后端开发Agent
    ↓ (提交代码)
代码审查Agent
    ↓ (审查通过)
测试Agent
    ↓ (测试通过)
验收完成
```

**并行任务**:
- 后端开发Agent 和 测试Agent 可以并行工作（测试Agent 准备测试用例）

---

### ✅ TASK-102: 修复 `process_upload_task` 函数

**优先级**: P0（关键）  
**负责人**: 后端开发Agent  
**工时**: 2小时  
**依赖**: 无  
**状态**: ✅ 已完成

---

#### 📝 任务描述

修复 `backend/app/routers/storage/storage.py` 中的 `process_upload_task()` 函数，添加配置解密逻辑，确保加密的存储配置能正常使用。

---

#### 🔍 自问自答（验证理解）

**Q1: 这个函数与 TASK-101 的区别是什么？**
- **A**: `process_upload_task()` 是后台任务处理函数，处理已创建的上传任务，而 `upload_to_active_storage_async()` 是异步上传函数。

**Q2: 修复逻辑是否相同？**
- **A**: 是的，都需要在调用 `StorageService.upload_file()` 之前解密配置，并添加错误处理和降级逻辑。

**Q3: 如何获取用户ID？**
- **A**: 从 `task.session_id` 查询 `ChatSession`，获取 `user_id`，用于 `StorageManager`（如果使用）。

---

#### 🎯 论证（验证方案正确性）

**论证1: 方案可行性**
- ✅ 与 TASK-101 使用相同的解密方案
- ✅ 其他文件已使用相同方案，已验证可行

**论证2: 方案一致性**
- ✅ 与 TASK-101 的解密逻辑保持一致
- ✅ 错误处理方式一致

---

#### 📋 详细步骤

1. **定位问题函数**
   - [ ] 打开文件: `backend/app/routers/storage/storage.py`
   - [ ] 定位函数: `process_upload_task()` (line 383-520)
   - [ ] 确认函数签名和参数

2. **添加解密逻辑**
   - [ ] 在函数开始处导入: `from ...core.encryption import decrypt_config`
   - [ ] 在获取 `config` 后，添加解密逻辑（与 TASK-101 相同）
   - [ ] 修改 `StorageService.upload_file()` 调用，使用 `decrypted_config`

3. **添加单元测试**
   - [ ] 在 `tests/test_storage_decrypt.py` 中添加测试用例
   - [ ] 测试加密配置场景
   - [ ] 测试未加密配置场景（向后兼容）

4. **代码审查**
   - [ ] 检查代码风格和规范
   - [ ] 检查错误处理是否完整
   - [ ] 检查日志记录是否充分

---

#### ✅ 验收标准

**功能验收**:
- [ ] 代码修改完成，无语法错误
- [ ] 单元测试通过（加密配置场景）
- [ ] 单元测试通过（未加密配置场景）
- [ ] 使用加密的存储配置测试上传功能，上传成功
- [ ] 使用未加密的存储配置测试上传功能，上传成功（向后兼容）

**代码质量验收**:
- [ ] 代码符合项目规范（PEP 8）
- [ ] 函数有完整的文档字符串
- [ ] 错误处理完整（try-except 块）
- [ ] 日志记录充分（debug、error、warning）

**测试验收**:
- [ ] 单元测试覆盖率 > 90%
- [ ] 所有测试用例通过

**集成验收**:
- [ ] 与现有代码集成无冲突
- [ ] 不影响其他功能

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **后端开发Agent**: 负责代码修改和单元测试
2. **测试Agent**: 负责集成测试
3. **代码审查Agent**: 负责代码审查

**协作流程**:
```
后端开发Agent
    ↓ (提交代码)
代码审查Agent
    ↓ (审查通过)
测试Agent
    ↓ (测试通过)
验收完成
```

---

### ✅ TASK-103: 添加配置解密单元测试

**优先级**: P1（重要）  
**负责人**: 测试Agent  
**工时**: 3小时  
**依赖**: TASK-101, TASK-102  
**状态**: ✅ 已完成

---

#### 📝 任务描述

为 TASK-101 和 TASK-102 添加完整的单元测试，覆盖加密配置和未加密配置两种场景。

---

#### 🔍 自问自答（验证理解）

**Q1: 需要测试哪些场景？**
- **A**: 
  1. 加密配置场景：使用加密的存储配置，验证解密和上传成功
  2. 未加密配置场景：使用未加密的存储配置，验证降级逻辑和上传成功
  3. 解密失败场景：模拟解密失败，验证降级逻辑

**Q2: 如何模拟加密配置？**
- **A**: 使用 `encrypt_config()` 函数创建加密配置，保存到测试数据库。

**Q3: 如何验证解密成功？**
- **A**: 验证上传成功（如果配置未解密，上传会失败），并检查日志中是否有解密成功的记录。

---

#### 🎯 论证（验证方案正确性）

**论证1: 测试覆盖度**
- ✅ 覆盖加密配置场景（主要场景）
- ✅ 覆盖未加密配置场景（向后兼容）
- ✅ 覆盖解密失败场景（错误处理）

**论证2: 测试可靠性**
- ✅ 使用真实的加密/解密函数
- ✅ 使用测试数据库，不影响生产数据
- ✅ 测试用例独立，可重复执行

---

#### 📋 详细步骤

1. **创建测试文件**
   - [ ] 创建文件: `tests/test_storage_decrypt.py`
   - [ ] 导入必要的模块和函数

2. **编写测试用例**
   - [ ] 测试加密配置场景:
     ```python
     def test_upload_with_encrypted_config():
         # 1. 创建加密的存储配置
         encrypted_config = encrypt_config({
             "accessKeyId": "test-key",
             "accessKeySecret": "test-secret",
             "domain": "https://example.com"
         })
         
         # 2. 保存到数据库
         config = StorageConfig(...)
         db.add(config)
         db.commit()
         
         # 3. 调用 upload_to_active_storage_async
         result = await upload_to_active_storage_async(...)
         
         # 4. 验证是否成功
         assert result["success"] == True
     ```
   - [ ] 测试未加密配置场景（向后兼容）
   - [ ] 测试解密失败场景（错误处理）

3. **运行测试**
   - [ ] 运行所有测试用例
   - [ ] 检查测试覆盖率
   - [ ] 修复失败的测试用例

4. **代码审查**
   - [ ] 检查测试用例是否完整
   - [ ] 检查测试代码可读性
   - [ ] 检查测试覆盖率是否达标

---

#### ✅ 验收标准

**测试覆盖度验收**:
- [ ] 测试覆盖率 > 90%
- [ ] 覆盖加密配置场景
- [ ] 覆盖未加密配置场景
- [ ] 覆盖解密失败场景

**测试质量验收**:
- [ ] 所有测试用例通过
- [ ] 测试代码可读性强，易于维护
- [ ] 测试用例独立，可重复执行

**测试性能验收**:
- [ ] 测试执行时间 < 30秒
- [ ] 测试不影响其他测试

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **测试Agent**: 负责编写测试用例和运行测试
2. **后端开发Agent**: 负责修复测试中发现的问题
3. **代码审查Agent**: 负责审查测试代码质量

**协作流程**:
```
测试Agent
    ↓ (编写测试用例)
测试Agent
    ↓ (运行测试)
后端开发Agent (如果有问题)
    ↓ (修复问题)
测试Agent
    ↓ (验证修复)
代码审查Agent
    ↓ (审查通过)
验收完成
```

---

## 3. 阶段2: 优化前端跨模式附件显示

### ✅ TASK-201: 创建统一的 `getUrlType()` 函数

**优先级**: P1（重要）  
**负责人**: 前端开发Agent  
**工时**: 1小时  
**依赖**: 无  
**状态**: ✅ 已完成

---

#### 📝 任务描述

在 `frontend/hooks/handlers/attachmentUtils.ts` 中创建统一的 `getUrlType()` 函数，用于判断URL类型，支持所有URL类型（包括 `/api/temp-images/`）。

---

#### 🔍 自问自答（验证理解）

**Q1: 为什么需要统一的URL类型判断函数？**
- **A**: 当前代码中有多处URL类型判断逻辑，容易产生不一致，统一函数可以确保所有地方使用相同的判断逻辑。

**Q2: 需要支持哪些URL类型？**
- **A**: 
  1. Base64 Data URL (`data:image/png;base64,...`)
  2. Blob URL (`blob:http://localhost:xxx`)
  3. 临时代理URL (`/api/temp-images/{id}`)
  4. HTTP/HTTPS URL (`http://...` 或 `https://...`)
  5. 空URL (`''` 或 `undefined`)

**Q3: 如何区分云存储URL和HTTP临时URL？**
- **A**: 根据 `uploadStatus` 参数判断，如果 `uploadStatus === 'completed'`，则为云存储URL，否则为HTTP临时URL。

---

#### 🎯 论证（验证方案正确性）

**论证1: 方案必要性**
- ✅ 当前代码中有多处URL类型判断逻辑，容易产生不一致
- ✅ 统一函数可以确保所有地方使用相同的判断逻辑
- ✅ 便于维护和扩展

**论证2: 方案正确性**
- ✅ 支持所有已知的URL类型
- ✅ 判断逻辑清晰，易于理解
- ✅ 向后兼容，不影响现有功能

---

#### 📋 详细步骤

1. **创建函数**
   - [ ] 打开文件: `frontend/hooks/handlers/attachmentUtils.ts`
   - [ ] 创建函数: `getUrlType(url: string | undefined, uploadStatus?: string): string`
   - [ ] 实现逻辑:
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

2. **导出函数**
   - [ ] 确保函数被正确导出
   - [ ] 检查TypeScript类型定义

3. **添加单元测试（可选）**
   - [ ] 测试所有URL类型
   - [ ] 测试边界情况（空URL、undefined）

---

#### ✅ 验收标准

**功能验收**:
- [ ] 函数创建完成，无语法错误
- [ ] 所有URL类型都能正确识别
- [ ] `/api/temp-images/` 格式被正确识别为"临时代理URL"
- [ ] 空URL和undefined被正确识别为"空URL"

**代码质量验收**:
- [ ] 代码符合项目规范（ESLint）
- [ ] 函数有完整的TypeScript类型定义
- [ ] 函数有完整的JSDoc注释

**测试验收**:
- [ ] 单元测试通过（如果添加了测试）
- [ ] 手动测试所有URL类型

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **前端开发Agent**: 负责创建函数和实现逻辑
2. **测试Agent**: 负责手动测试和验证
3. **代码审查Agent**: 负责代码审查

**协作流程**:
```
前端开发Agent
    ↓ (创建函数)
测试Agent
    ↓ (手动测试)
代码审查Agent
    ↓ (审查通过)
验收完成
```

---

### ✅ TASK-202: 在 `useChat.ts` 中使用 `getUrlType()`

**优先级**: P1（重要）  
**负责人**: 前端开发Agent  
**工时**: 30分钟  
**依赖**: TASK-201  
**状态**: ✅ 已完成

---

#### 📝 任务描述

在 `frontend/hooks/useChat.ts` 中使用统一的 `getUrlType()` 函数，替换现有的URL类型判断逻辑。

---

#### 🔍 自问自答（验证理解）

**Q1: 需要替换哪些代码？**
- **A**: 替换 `useChat.ts` 中现有的URL类型判断逻辑（line 191-195）。

**Q2: 如何确保替换后功能不变？**
- **A**: 对比替换前后的逻辑，确保判断结果一致，并添加日志验证。

---

#### 🎯 论证（验证方案正确性）

**论证1: 方案必要性**
- ✅ 统一使用 `getUrlType()` 函数，确保判断逻辑一致
- ✅ 便于维护和扩展

**论证2: 方案正确性**
- ✅ 替换后的逻辑与原有逻辑等价
- ✅ 不影响现有功能

---

#### 📋 详细步骤

1. **导入函数**
   - [ ] 打开文件: `frontend/hooks/useChat.ts`
   - [ ] 导入函数: `import { getUrlType } from './handlers/attachmentUtils';`

2. **替换现有逻辑**
   - [ ] 定位现有URL类型判断逻辑（line 191-195）
   - [ ] 替换为 `getUrlType()` 调用
   - [ ] 确保参数传递正确

3. **验证**
   - [ ] 检查日志确认URL类型正确识别
   - [ ] 手动测试各种URL类型

---

#### ✅ 验收标准

**功能验收**:
- [ ] 代码修改完成，无语法错误
- [ ] 日志中显示正确的URL类型
- [ ] `/api/temp-images/` 格式被正确识别
- [ ] 所有URL类型都能正确识别

**代码质量验收**:
- [ ] 代码符合项目规范（ESLint）
- [ ] 代码简洁，易于维护

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **前端开发Agent**: 负责代码修改
2. **测试Agent**: 负责验证和测试

**协作流程**:
```
前端开发Agent
    ↓ (修改代码)
测试Agent
    ↓ (验证测试)
验收完成
```

---

### ✅ TASK-203: 在 `ImageGenView.tsx` 中使用 `getUrlType()`

**优先级**: P1（重要）  
**负责人**: 前端开发Agent  
**工时**: 30分钟  
**依赖**: TASK-201  
**状态**: ✅ 已完成

---

#### 📝 任务描述

在 `frontend/components/views/ImageGenView.tsx` 中使用统一的 `getUrlType()` 函数，替换现有的URL类型判断逻辑。

---

#### 📋 详细步骤

1. **导入函数**
   - [ ] 打开文件: `frontend/components/views/ImageGenView.tsx`
   - [ ] 导入函数: `import { getUrlType } from '../../hooks/handlers/attachmentUtils';`

2. **替换现有逻辑**
   - [ ] 定位现有URL类型判断逻辑（line 75-79）
   - [ ] 替换为 `getUrlType()` 调用

3. **验证**
   - [ ] 检查日志确认URL类型正确识别

---

#### ✅ 验收标准

**功能验收**:
- [ ] 代码修改完成，无语法错误
- [ ] 日志中显示正确的URL类型

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **前端开发Agent**: 负责代码修改
2. **测试Agent**: 负责验证

---

### ✅ TASK-204: 在 `ImageEditView.tsx` 中使用 `getUrlType()`

**优先级**: P1（重要）  
**负责人**: 前端开发Agent  
**工时**: 30分钟  
**依赖**: TASK-201  
**状态**: ✅ 已完成

---

#### 📝 任务描述

在 `frontend/components/views/ImageEditView.tsx` 中使用统一的 `getUrlType()` 函数，替换现有的URL类型判断逻辑。

---

#### 📋 详细步骤

1. **导入函数**
   - [ ] 打开文件: `frontend/components/views/ImageEditView.tsx`
   - [ ] 导入函数: `import { getUrlType } from '../../hooks/handlers/attachmentUtils';`

2. **替换现有逻辑**
   - [ ] 定位现有URL类型判断逻辑
   - [ ] 替换为 `getUrlType()` 调用

3. **验证**
   - [ ] 检查日志确认URL类型正确识别

---

#### ✅ 验收标准

**功能验收**:
- [ ] 代码修改完成，无语法错误
- [ ] 日志中显示正确的URL类型

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **前端开发Agent**: 负责代码修改
2. **测试Agent**: 负责验证

---

### ✅ TASK-205: 验证跨模式附件显示

**优先级**: P0（关键）  
**负责人**: 测试Agent  
**工时**: 2小时  
**依赖**: TASK-201, TASK-202, TASK-203, TASK-204  
**状态**: ⏳ 待开始

---

#### 📝 任务描述

验证跨模式切换时附件栏能正常显示附件，覆盖所有场景（临时URL + 上传中、临时URL + 上传失败、云URL + 上传完成、云URL + 上传中）。

---

#### 🔍 自问自答（验证理解）

**Q1: 需要验证哪些场景？**
- **A**: 
  1. 临时URL + 上传中（`uploadStatus: 'pending'`）
  2. 临时URL + 上传失败（`uploadStatus: 'failed'`）
  3. 云URL + 上传完成（`uploadStatus: 'completed'`）
  4. 云URL + 上传中（`uploadStatus: 'pending'`，但已查询到云URL）

**Q2: 如何验证附件栏显示？**
- **A**: 在 `gen` 模式生成图片后，点击编辑按钮，验证附件栏能立即显示附件。

**Q3: 如何模拟不同上传状态？**
- **A**: 在测试环境中，手动设置 `uploadStatus`，或等待上传完成/失败。

---

#### 🎯 论证（验证方案正确性）

**论证1: 测试覆盖度**
- ✅ 覆盖所有上传状态（pending、failed、completed）
- ✅ 覆盖所有URL类型（临时URL、云URL）
- ✅ 覆盖跨模式切换场景

**论证2: 测试可靠性**
- ✅ 使用真实的前端环境
- ✅ 验证用户可见的行为（附件栏显示）

---

#### 📋 详细步骤

1. **准备测试环境**
   - [ ] 启动前端开发服务器
   - [ ] 启动后端开发服务器
   - [ ] 准备测试数据

2. **测试场景1: 临时URL + 上传中**
   - [ ] 在 `gen` 模式生成图片（`uploadStatus: 'pending'`）
   - [ ] 点击编辑按钮
   - [ ] 验证附件栏能立即显示
   - [ ] 截图记录

3. **测试场景2: 临时URL + 上传失败**
   - [ ] 模拟上传失败（设置 `uploadStatus: 'failed'`）
   - [ ] 点击编辑按钮
   - [ ] 验证附件栏能立即显示
   - [ ] 截图记录

4. **测试场景3: 云URL + 上传完成**
   - [ ] 等待上传完成（`uploadStatus: 'completed'`）
   - [ ] 点击编辑按钮
   - [ ] 验证附件栏能立即显示
   - [ ] 截图记录

5. **测试场景4: 云URL + 上传中**
   - [ ] 在 `gen` 模式生成图片（`uploadStatus: 'pending'`，但已查询到云URL）
   - [ ] 点击编辑按钮
   - [ ] 验证附件栏能立即显示
   - [ ] 截图记录

6. **记录测试结果**
   - [ ] 记录所有测试场景的结果
   - [ ] 记录发现的问题
   - [ ] 创建测试报告

---

#### ✅ 验收标准

**功能验收**:
- [ ] 所有测试场景通过
- [ ] 附件栏在所有场景下都能正常显示
- [ ] 日志中显示正确的URL类型和附件信息

**测试质量验收**:
- [ ] 测试报告完整
- [ ] 所有场景都有截图记录
- [ ] 发现的问题已记录

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **测试Agent**: 负责执行测试和记录结果
2. **前端开发Agent**: 负责修复测试中发现的问题
3. **后端开发Agent**: 负责修复后端相关问题

**协作流程**:
```
测试Agent
    ↓ (执行测试)
测试Agent
    ↓ (发现问题)
前端开发Agent / 后端开发Agent
    ↓ (修复问题)
测试Agent
    ↓ (验证修复)
验收完成
```

---

## 4. 阶段3: 合并加密文件

### ✅ TASK-301: 合并函数到 `core/encryption.py`

**优先级**: P1（重要）  
**负责人**: 后端开发Agent  
**工时**: 2小时  
**依赖**: 无  
**状态**: ✅ 已完成

---

#### 📝 任务描述

将 `utils/encryption.py` 中的函数合并到 `core/encryption.py`，统一加密功能入口。

---

#### 🔍 自问自答（验证理解）

**Q1: 需要合并哪些函数？**
- **A**: 
  1. `SENSITIVE_FIELDS` 常量
  2. `encrypt_config()` 函数
  3. `decrypt_config()` 函数
  4. `mask_sensitive_fields()` 函数

**Q2: 如何处理 `is_encrypted()` 函数？**
- **A**: 使用 `core/encryption.py` 中的实现（通过实际解密尝试），而不是 `utils/encryption.py` 中的格式检查实现。

**Q3: 如何确保合并后功能正常？**
- **A**: 运行单元测试，确保所有功能正常。

---

#### 🎯 论证（验证方案正确性）

**论证1: 方案可行性**
- ✅ 影响范围小（仅3个文件使用 `utils.encryption`）
- ✅ 没有循环导入问题
- ✅ 函数签名兼容

**论证2: 方案正确性**
- ✅ 统一 `is_encrypted()` 实现，使用更准确的实现
- ✅ 向后兼容，不影响现有功能

---

#### 📋 详细步骤

1. **读取 `utils/encryption.py` 的内容**
   - [ ] 打开文件: `backend/app/utils/encryption.py`
   - [ ] 获取 `SENSITIVE_FIELDS` 常量
   - [ ] 获取 `encrypt_config()` 函数
   - [ ] 获取 `decrypt_config()` 函数
   - [ ] 获取 `mask_sensitive_fields()` 函数

2. **添加到 `core/encryption.py`**
   - [ ] 打开文件: `backend/app/core/encryption.py`
   - [ ] 在文件末尾添加配置字典加密/解密部分
   - [ ] 更新文档字符串

3. **修改 `is_encrypted()` 的调用**
   - [ ] 在 `encrypt_config()` 和 `decrypt_config()` 中，使用 `core/encryption.py` 中的 `is_encrypted()` 实现

4. **移除 `_get_encryption_key()` 函数**
   - [ ] 直接使用 `core/encryption.py` 中的 `get_encryption_key()` 和 `_get_encryption_key_bytes()`

5. **运行测试**
   - [ ] 运行单元测试，确保功能正常

---

#### ✅ 验收标准

**功能验收**:
- [ ] 所有函数已合并到 `core/encryption.py`
- [ ] 文档字符串已更新
- [ ] 单元测试通过

**代码质量验收**:
- [ ] 代码符合项目规范（PEP 8）
- [ ] 函数有完整的文档字符串
- [ ] 代码结构清晰，易于维护

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **后端开发Agent**: 负责合并函数和修改代码
2. **测试Agent**: 负责运行测试和验证
3. **代码审查Agent**: 负责代码审查

**协作流程**:
```
后端开发Agent
    ↓ (合并函数)
测试Agent
    ↓ (运行测试)
代码审查Agent
    ↓ (审查通过)
验收完成
```

---

### ✅ TASK-302: 更新 `upload_worker_pool.py` 的导入

**优先级**: P1（重要）  
**负责人**: 后端开发Agent  
**工时**: 15分钟  
**依赖**: TASK-301  
**状态**: ✅ 已完成

---

#### 📝 任务描述

更新 `backend/app/services/common/upload_worker_pool.py` 中的导入语句，从 `utils.encryption` 改为 `core.encryption`。

---

#### 📋 详细步骤

1. **修改导入语句**
   - [ ] 打开文件: `backend/app/services/common/upload_worker_pool.py`
   - [ ] 定位导入语句（Line 25）
   - [ ] 修改: `from ...utils.encryption import decrypt_config` → `from ...core.encryption import decrypt_config`

2. **验证**
   - [ ] 运行测试确保功能正常

---

#### ✅ 验收标准

**功能验收**:
- [ ] 导入路径已更新
- [ ] 功能测试通过

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **后端开发Agent**: 负责修改导入语句
2. **测试Agent**: 负责验证

---

### ✅ TASK-303: 更新 `upload_tasks.py` 的导入

**优先级**: P1（重要）  
**负责人**: 后端开发Agent  
**工时**: 15分钟  
**依赖**: TASK-301  
**状态**: ✅ 已完成

---

#### 📝 任务描述

更新 `backend/app/tasks/upload_tasks.py` 中的导入语句，从 `utils.encryption` 改为 `core.encryption`。

---

#### 📋 详细步骤

1. **修改导入语句**
   - [ ] 打开文件: `backend/app/tasks/upload_tasks.py`
   - [ ] 定位导入语句（Line 70）
   - [ ] 修改: `from app.utils.encryption import decrypt_config` → `from app.core.encryption import decrypt_config`

2. **验证**
   - [ ] 运行测试确保功能正常

---

#### ✅ 验收标准

**功能验收**:
- [ ] 导入路径已更新
- [ ] 功能测试通过

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **后端开发Agent**: 负责修改导入语句
2. **测试Agent**: 负责验证

---

### ✅ TASK-304: 更新 `storage_manager.py` 的导入

**优先级**: P1（重要）  
**负责人**: 后端开发Agent  
**工时**: 15分钟  
**依赖**: TASK-301  
**状态**: ✅ 已完成

---

#### 📝 任务描述

更新 `backend/app/services/storage/storage_manager.py` 中的导入语句，从 `utils.encryption` 改为 `core.encryption`。

---

#### 📋 详细步骤

1. **修改导入语句**
   - [ ] 打开文件: `backend/app/services/storage/storage_manager.py`
   - [ ] 定位导入语句（Line 19）
   - [ ] 修改: `from ...utils.encryption import encrypt_config, decrypt_config, mask_sensitive_fields` → `from ...core.encryption import encrypt_config, decrypt_config, mask_sensitive_fields`

2. **验证**
   - [ ] 运行测试确保功能正常

---

#### ✅ 验收标准

**功能验收**:
- [ ] 导入路径已更新
- [ ] 功能测试通过

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **后端开发Agent**: 负责修改导入语句
2. **测试Agent**: 负责验证

---

### ✅ TASK-305: 删除 `utils/encryption.py`

**优先级**: P1（重要）  
**负责人**: 后端开发Agent  
**工时**: 15分钟  
**依赖**: TASK-301, TASK-302, TASK-303, TASK-304  
**状态**: ✅ 已完成

---

#### 📝 任务描述

确认所有导入已更新后，删除 `backend/app/utils/encryption.py` 文件。

---

#### 🔍 自问自答（验证理解）

**Q1: 删除前需要确认什么？**
- **A**: 确认所有使用 `utils.encryption` 的文件都已更新为 `core.encryption`。

**Q2: 如何确认没有遗漏？**
- **A**: 使用全局搜索，查找所有 `utils.encryption` 的引用。

---

#### 📋 详细步骤

1. **确认所有导入已更新**
   - [ ] 使用全局搜索查找所有 `utils.encryption` 的引用
   - [ ] 确认都已更新为 `core.encryption`

2. **删除文件**
   - [ ] 删除 `backend/app/utils/encryption.py`

3. **运行完整测试套件**
   - [ ] 运行所有测试，确保没有导入错误

---

#### ✅ 验收标准

**功能验收**:
- [ ] 文件已删除
- [ ] 所有测试通过
- [ ] 没有导入错误

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **后端开发Agent**: 负责删除文件
2. **测试Agent**: 负责运行测试和验证

---

### ✅ TASK-306: 添加加密文件合并测试

**优先级**: P1（重要）  
**负责人**: 测试Agent  
**状态**: ✅ 已完成（测试已通过）  
**工时**: 2小时  
**依赖**: TASK-301, TASK-302, TASK-303, TASK-304, TASK-305  
**状态**: ⏳ 待开始

---

#### 📝 任务描述

为加密文件合并添加完整的测试用例，覆盖存储配置加密/解密、嵌套字典处理、历史数据兼容性、`is_encrypted()` 准确性等场景。

---

#### 📋 详细步骤

1. **创建测试文件**
   - [ ] 创建文件: `tests/test_encryption_merge.py`
   - [ ] 导入必要的模块和函数

2. **编写测试用例**
   - [ ] 测试存储配置加密/解密
   - [ ] 测试嵌套字典处理
   - [ ] 测试历史数据兼容性
   - [ ] 测试 `is_encrypted()` 准确性

3. **运行测试**
   - [ ] 运行所有测试用例
   - [ ] 检查测试覆盖率

---

#### ✅ 验收标准

**测试覆盖度验收**:
- [ ] 测试覆盖率 > 90%
- [ ] 覆盖所有关键场景

**测试质量验收**:
- [ ] 所有测试用例通过
- [ ] 测试代码可读性强

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **测试Agent**: 负责编写测试用例和运行测试
2. **后端开发Agent**: 负责修复测试中发现的问题

---

## 5. 阶段4: 统一配置管理（可选）

### ✅ TASK-401: 重构 `upload_to_active_storage_async` 使用 `StorageManager`

**优先级**: P2（次要，可选）  
**负责人**: 后端开发Agent  
**工时**: 2小时  
**依赖**: TASK-101  
**状态**: ✅ 已完成

---

#### 📝 任务描述

重构 `upload_to_active_storage_async` 函数，使用 `StorageManager` 而不是直接查询数据库，实现统一配置管理。

---

#### 📋 详细步骤

1. **修改函数实现**
   - [ ] 使用 `StorageManager` 替代直接查询数据库
   - [ ] 调用 `manager.upload_file()` 方法

2. **添加单元测试**
   - [ ] 测试使用 `StorageManager` 的上传功能

3. **验证**
   - [ ] 运行测试确保功能正常

---

#### ✅ 验收标准

**功能验收**:
- [ ] 代码重构完成
- [ ] 单元测试通过
- [ ] 功能测试通过

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **后端开发Agent**: 负责重构代码
2. **测试Agent**: 负责测试和验证

---

### ✅ TASK-402: 重构 `process_upload_task` 使用 `StorageManager`

**优先级**: P2（次要，可选）  
**负责人**: 后端开发Agent  
**工时**: 2小时  
**依赖**: TASK-102  
**状态**: ✅ 已完成

---

#### 📝 任务描述

重构 `process_upload_task` 函数，使用 `StorageManager` 而不是直接查询数据库，实现统一配置管理。

---

#### 📋 详细步骤

1. **修改函数实现**
   - [ ] 使用 `StorageManager` 替代直接查询数据库
   - [ ] 调用 `manager.upload_file()` 方法

2. **添加单元测试**
   - [ ] 测试使用 `StorageManager` 的任务处理功能

3. **验证**
   - [ ] 运行测试确保功能正常

---

#### ✅ 验收标准

**功能验收**:
- [ ] 代码重构完成
- [ ] 单元测试通过
- [ ] 功能测试通过

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **后端开发Agent**: 负责重构代码
2. **测试Agent**: 负责测试和验证

---

### ✅ TASK-403: 添加代码审查检查清单

**优先级**: P2（次要，可选）  
**负责人**: 代码审查Agent  
**工时**: 1小时  
**依赖**: TASK-401, TASK-402  
**状态**: ✅ 已完成

---

#### 📝 任务描述

创建代码审查检查清单文档，确保所有新代码都遵循统一的配置管理原则。

---

#### 📋 详细步骤

1. **创建检查清单文档**
   - [ ] 存储配置使用检查
   - [ ] 附件显示检查
   - [ ] 认证处理检查

2. **添加到代码审查流程**
   - [ ] 确保所有新代码都通过检查清单

---

#### ✅ 验收标准

**文档验收**:
- [ ] 检查清单文档创建完成
- [ ] 代码审查流程已更新

---

#### 🤖 多Agent实施计划

**Agent分工**:
1. **代码审查Agent**: 负责创建检查清单
2. **后端开发Agent**: 负责配合更新流程

---

## 6. 多Agent实施计划

### 6.1 Agent角色定义

| Agent角色 | 职责 | 负责的任务 |
|----------|------|-----------|
| **后端开发Agent** | 后端代码开发、修改、重构 | TASK-101, TASK-102, TASK-301, TASK-302, TASK-303, TASK-304, TASK-305, TASK-401, TASK-402 |
| **前端开发Agent** | 前端代码开发、修改 | TASK-201, TASK-202, TASK-203, TASK-204 |
| **测试Agent** | 测试用例编写、测试执行、验证 | TASK-103, TASK-205, TASK-306 |
| **代码审查Agent** | 代码审查、规范检查 | TASK-403, 所有任务的代码审查 |

### 6.2 协作流程

```
阶段1: 后端配置解密修复
  后端开发Agent (TASK-101, TASK-102)
    ↓
  测试Agent (TASK-103)
    ↓
  代码审查Agent (审查)
    ↓
  验收完成

阶段2: 前端跨模式附件显示优化
  前端开发Agent (TASK-201, TASK-202, TASK-203, TASK-204)
    ↓
  测试Agent (TASK-205)
    ↓
  代码审查Agent (审查)
    ↓
  验收完成

阶段3: 合并加密文件
  后端开发Agent (TASK-301, TASK-302, TASK-303, TASK-304, TASK-305)
    ↓
  测试Agent (TASK-306)
    ↓
  代码审查Agent (审查)
    ↓
  验收完成

阶段4: 统一配置管理（可选）
  后端开发Agent (TASK-401, TASK-402)
    ↓
  代码审查Agent (TASK-403)
    ↓
  验收完成
```

### 6.3 并行任务

**可以并行执行的任务**:
- TASK-101 和 TASK-102（两个函数修复，互不依赖）
- TASK-201, TASK-202, TASK-203, TASK-204（都依赖 TASK-201，但可以并行修改不同文件）
- TASK-302, TASK-303, TASK-304（都依赖 TASK-301，但可以并行修改不同文件）

**必须串行执行的任务**:
- TASK-103 必须在 TASK-101 和 TASK-102 完成后执行
- TASK-205 必须在 TASK-201, TASK-202, TASK-203, TASK-204 完成后执行
- TASK-305 必须在 TASK-301, TASK-302, TASK-303, TASK-304 完成后执行

---

## 7. 验收检查清单

### 7.1 阶段1验收检查清单

**功能验收**:
- [ ] TASK-101: `upload_to_active_storage_async` 函数已修复
- [ ] TASK-102: `process_upload_task` 函数已修复
- [ ] TASK-103: 单元测试已添加并通过

**代码质量验收**:
- [ ] 所有代码符合项目规范
- [ ] 所有函数有完整的文档字符串
- [ ] 错误处理完整
- [ ] 日志记录充分

**测试验收**:
- [ ] 单元测试覆盖率 > 90%
- [ ] 所有测试用例通过
- [ ] 集成测试通过

---

### 7.2 阶段2验收检查清单

**功能验收**:
- [ ] TASK-201: `getUrlType()` 函数已创建
- [ ] TASK-202: `useChat.ts` 已使用 `getUrlType()`
- [ ] TASK-203: `ImageGenView.tsx` 已使用 `getUrlType()`
- [ ] TASK-204: `ImageEditView.tsx` 已使用 `getUrlType()`
- [ ] TASK-205: 跨模式附件显示验证通过

**代码质量验收**:
- [ ] 所有代码符合项目规范
- [ ] 所有函数有完整的TypeScript类型定义
- [ ] 代码简洁，易于维护

**测试验收**:
- [ ] 所有测试场景通过
- [ ] 测试报告完整

---

### 7.3 阶段3验收检查清单

**功能验收**:
- [ ] TASK-301: 函数已合并到 `core/encryption.py`
- [ ] TASK-302: `upload_worker_pool.py` 导入已更新
- [ ] TASK-303: `upload_tasks.py` 导入已更新
- [ ] TASK-304: `storage_manager.py` 导入已更新
- [ ] TASK-305: `utils/encryption.py` 已删除
- [ ] TASK-306: 测试已添加并通过

**代码质量验收**:
- [ ] 所有代码符合项目规范
- [ ] 所有函数有完整的文档字符串
- [ ] 代码结构清晰

**测试验收**:
- [ ] 测试覆盖率 > 90%
- [ ] 所有测试用例通过

---

### 7.4 阶段4验收检查清单（可选）

**功能验收**:
- [ ] TASK-401: `upload_to_active_storage_async` 已重构
- [ ] TASK-402: `process_upload_task` 已重构
- [ ] TASK-403: 代码审查检查清单已创建

**代码质量验收**:
- [ ] 所有代码符合项目规范
- [ ] 代码审查检查清单已更新

---

### 7.5 整体验收检查清单

**功能验收**:
- [ ] 所有P0任务完成
- [ ] 所有P1任务完成
- [ ] 所有功能测试通过

**代码质量验收**:
- [ ] 代码审查通过
- [ ] 代码规范检查通过
- [ ] 文档完整

**测试验收**:
- [ ] 单元测试覆盖率 > 90%
- [ ] 集成测试通过
- [ ] 性能测试通过

**交付验收**:
- [ ] 所有文档已更新
- [ ] 代码已提交到版本控制系统
- [ ] 部署文档已更新

---

**文档版本**: 1.0  
**创建日期**: 2026-01-19  
**最后更新**: 2026-01-19
