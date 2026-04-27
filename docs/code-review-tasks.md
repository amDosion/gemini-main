# Gemini-Main 代码审查修复任务清单

> 基于 `docs/code-review-report.md` 生成
> 生成日期：2026-04-12
> 执行框架：Everything Claude Code (ECC)

---

## 任务总览

| # | 优先级 | 类别 | 任务 | 状态 | 影响文件数 |
|---|--------|------|------|------|:---:|
| T1 | CRITICAL | 复用 | 统一 `decrypt_api_key` 到 `encryption.py` | ✅ DONE | 5 |
| T2 | CRITICAL | 复用 | 删除 `models.py` 重复的 `get_provider_credentials` | ✅ DONE | 2 |
| T3 | HIGH | 复用 | `jwt_utils.py` 复用 `encryption.py` 加解密 | ✅ DONE | 2 |
| T4 | HIGH | 复用 | 统一凭证目录路径常量 | ✅ DONE | 3 |
| T5 | HIGH | ��用 | 删除未使用的 `DataMasker` | ✅ DONE | 2 |
| T6 | HIGH | 效率 | 修复 Session 保存 N+1 查询 | ✅ DONE | 1 |
| T7 | HIGH | 效��� | 缓存 Case Conversion 中间件路由映射 | ✅ DONE | 1 |
| T8 | HIGH | 质量 | 统一 `Attachment` 模型定义 | ✅ DONE | 4 |
| T9 | MEDIUM | 复用 | 大小写转换函数去重 | ✅ DONE | 1 |
| T10 | MEDIUM | 复用 | 错误分类逻辑统一 | ✅ DONE | 3 |
| T11 | MEDIUM | 效率 | 启动任务并行化 | ✅ DONE | 1 |
| T12 | MEDIUM | 质量 | 清理不必要的 emoji 注释 | ✅ DONE | 3+ |

---

## 详细任务描述

### T1: 统一 `decrypt_api_key` 到 `encryption.py` [CRITICAL]

**目标**：在 `core/encryption.py` ���新增 `decrypt_api_key(api_key: str, silent: bool = False) -> str`，删除 4 处重复实现。

**修改文件**：
1. `backend/app/core/encryption.py` — 新增 `decrypt_api_key()` 函数
2. `backend/app/core/credential_manager.py:51` — 删除本地 `_decrypt_api_key`，改为 `from .encryption import decrypt_api_key`
3. `backend/app/routers/user/profiles.py:47` — 同上
4. `backend/app/routers/models/models.py:627` — 同上
5. `backend/app/services/llm/credentials_resolver.py:60` — 同上

**验证**：
```bash
cd backend && .venv/bin/python -c "from app.core.encryption import decrypt_api_key; print('OK')"
.venv/bin/python -m pytest tests/ -q
```

---

### T2: 删除 `models.py` 重复的 `get_provider_credentials` [CRITICAL]

**目标**：删除 `routers/models/models.py` 中重复的 `get_provider_credentials` 函数，改为从 `core.credential_manager` 导入。

**修改文件**：
1. `backend/app/routers/models/models.py:597` — 删除函数定义，添加导入
2. `backend/app/core/credential_manager.py` — 确认公共 API 完整

**验证**：
```bash
grep -n "def get_provider_credentials" backend/app/routers/models/models.py  # 应无结果
grep -n "from.*credential_manager import.*get_provider_credentials" backend/app/routers/models/models.py  # 应有导入
```

---

### T3: `jwt_utils.py` 复用 `encryption.py` 加解密 [HIGH]

**目标**：删除 `JWTSecretManager._encrypt_secret` 和 `_decrypt_secret`，改用 `encryption.py` 的 `encrypt_data()` / `decrypt_data()`��

**修改文件**：
1. `backend/app/core/jwt_utils.py:84-122` — 删除两个方法，用 `encrypt_data` / `decrypt_data` 替代
2. `backend/app/core/encryption.py` — 确认接口兼容

**注意**：确保密钥来源一致（`get_encryption_key()` 返回的 master key）。

---

### T4: 统一凭证目录路径常量 [HIGH]

**目标**：将 `Path(__file__).resolve().parents[2] / "credentials"` 抽取为共享常量。

**修改文件**：
1. `backend/app/core/path_utils.py` — 新增 `CREDENTIALS_DIR` 常量（或复用已有的 path_utils）
2. `backend/app/core/encryption.py:34` — 改用共享常量
3. `backend/app/core/jwt_utils.py:37` — 改用共享常量

---

### T5: 删除未使用的 `DataMasker` [HIGH]

**目标**：删除零引用的 `backend/app/utils/data_masker.py`。

**修改文件**：
1. `backend/app/utils/data_masker.py` — 删除文件
2. `backend/app/utils/__init__.py` — 如有导入则清理

**验证**：
```bash
grep -r "data_masker\|DataMasker" backend/app/ --include="*.py"  # 应无结果
```

---

### T6: 修�� Session 保存 N+1 查询 [HIGH]

**目标**：`create_or_update_session` 改为批量预加载消息，替代逐条查询。

**修改文件**：
1. `backend/app/routers/user/sessions.py:319-465`

**方案**：
- 预先 `SELECT` 所有该 session 的 `MessageIndex` 行，构建 `{msg_id: row}` 字典
- 预先批量加载 mode-table 行
- 将循环内的 `.get(msg_id)` 和 `.filter().first()` 替换为字典查找

---

### T7: 缓存 Case Conversion 中间件���由映射 [HIGH]

**目标**：将每次请求的线性路由扫描改为启动时缓存。

**修改文件**：
1. `backend/app/middleware/case_conversion_middleware.py:91-110`

**方案**：
- 在中间件 `__init__` 或首次请求时构建 `{path_pattern: CaseConversionOptions}` 缓存字典
- `_resolve_case_options` 改为字典查找

---

### T8: 统一 `Attachment` 模型定义 [HIGH]

**目标**：合并 3 处 `Attachment` 定义为单一 Pydantic 模型。

**修改��件**：
1. 新增或修改 `backend/app/models/attachment.py` — 统一模型
2. `backend/app/routers/core/chat.py:43` — 改为导入
3. `backend/app/routers/core/modes.py:51` — 改为导入
4. `backend/app/utils/attachment_handler.py:52` — 改为导入

---

### T9: 大小写转换函数去重 [MEDIUM]

**��改文件**：
1. `backend/app/core/provider_param_whitelist.py:17-30` — 删除本地 `_snake_to_camel` / `_camel_to_snake`，改从 `utils.case_converter` 导入

---

### T10: 错误分类逻辑统一 [MEDIUM]

**修改文件**：
1. `backend/app/utils/error_handler.py` — 增强为通用错误分类
2. `backend/app/routers/core/modes.py:262-275` — 复用 error_handler
3. `backend/app/routers/core/modes.py:1758-1768` — ���用 error_handler

---

### T11: 启动���务并行化 [MEDIUM]

**修改文件**：
1. `backend/app/core/startup_tasks.py:402-430` — 用 `asyncio.gather()` 将独立任务分组并行

---

### T12: 清理不必要的 emoji 注释 [MEDIUM]

**修改文件**：
1. `frontend/hooks/useImageHandlers.ts` — 删除 `// ✅` `// 🚀` 等纯描述性注释
2. `backend/app/core/credential_manager.py` — 删除重复的 `// ✅` 注释
3. 其他包含纯 "做了什么" 注释的文件

---

## 执行顺序

```
Phase 1 (Critical): T1 → T2 (依赖关系：T2 依赖 T1 的 encryption.py 变更)
Phase 2 (High):     T3 → T4 → T5 (encryption 相关，按依赖顺序)
Phase 3 (High):     T6 + T7 + T8 (互相独立，可��行)
Phase 4 (Medium):   T9 + T10 + T11 + T12 (互相独立，可并行)
```

## 验证计划

每个 Phase 完成后执行：
```bash
cd /mnt/user/appdata/gemini-main/backend
.venv/bin/python -m pytest tests/ -q           # 单元测试
.venv/bin/python -c "from app.main import app"  # 应用启动检查
```

---

*任务文档由 Claude Code 基于 code-review-report.md ���动生成。*
