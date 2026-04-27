# Phase 3 + Phase 4 详细实施计划

> 基于 4 个并行分析 Agent 的研究成果
> 生成日期：2026-04-12

---

## Phase 3（HIGH 优先级，互相独立可并行）

### T6: 修复 Session 保存 N+1 查询

**文件**: `backend/app/routers/user/sessions.py` (191-468 行)

**问题**: `create_or_update_session` 函数中有 3 处循环内 DB 查询：

| 行号 | 查询 | 触发次数 |
|------|------|---------|
| 331 | `db.query(MessageIndex).filter(...).first()` | N（消息数）|
| 352 | `db.query(table_class).get(msg_id)` | N（消息数）|
| 422 | `db.query(MessageAttachment).filter(...).first()` | N×M（消息×附件）|

**性能影响**: 50 条消息 + 5 附件 = 350 次查询 → 优化后 3 次

**实施步骤**:

1. **批量预加载 MessageIndex**（在循环前，约第 316 行）
   ```python
   new_message_ids = {msg["id"] for msg in new_messages}
   existing_indexes = db.query(MessageIndex).filter(
       MessageIndex.id.in_(list(new_message_ids)),
       MessageIndex.user_id == user_id
   ).all()
   existing_indexes_map = {idx.id: idx for idx in existing_indexes}
   ```
   循环内 `index = existing_indexes_map.get(msg_id)` 替代 `.filter().first()`

2. **按 table_name 分组批量加载模式表**（在循环前）
   ```python
   from collections import defaultdict
   table_message_ids: Dict[str, set] = defaultdict(set)
   for msg in new_messages:
       table_name = get_table_name_for_mode(msg.get("mode", "chat"))
       table_message_ids[table_name].add(msg["id"])

   messages_by_table: Dict[str, Dict[str, Any]] = {}
   for table_name, ids in table_message_ids.items():
       table_class = get_message_table_class_by_name(table_name)
       rows = db.query(table_class).filter(table_class.id.in_(list(ids))).all()
       messages_by_table[table_name] = {m.id: m for m in rows}
   ```
   循环内 `message = messages_by_table.get(table_name, {}).get(msg_id)` 替代 `.get(id)`

3. **批量预加载附件**（在循环前）
   ```python
   all_att_ids = []
   for msg in new_messages:
       for att in msg.get("attachments", []):
           if att.get("id"):
               all_att_ids.append(att["id"])

   existing_atts = db.query(MessageAttachment).filter(
       MessageAttachment.id.in_(all_att_ids),
       MessageAttachment.user_id == user_id
   ).all()
   att_map = {(a.message_id, a.id): a for a in existing_atts}
   ```
   嵌套循环内 `attachment = att_map.get((msg_id, att_id))` 替代 `.filter().first()`

**参考**: `init_service.py:146-191` 已有批量模式实现

**风险**: 低 — 同事务内操作，SQLAlchemy Session 自动跟踪

**验证**:
```bash
# 功能测试：创建/更新会话
curl -X POST http://localhost:21574/api/sessions -H "Authorization: Bearer <token>" -d '...'
# 日志中不应有大量重复 SELECT 语句
```

---

### T7: 缓存 Case Conversion 中间件路由映射

**文件**: `backend/app/middleware/case_conversion_middleware.py`

**问题**: `_resolve_case_options()` (91-110 行) 每次请求遍历所有路由做匹配，O(n)

**实施步骤**:

1. **在中间件类中添加缓存属性**（`__init__` 方法）
   ```python
   def __init__(self, app: ASGIApp):
       self.app = app
       self._route_options_cache: Dict[str, CaseConversionOptions] = {}
       self._cache_built = False
   ```

2. **新增 `_build_route_cache` 方法**（启动时或首次请求时调用）
   ```python
   def _build_route_cache(self, app):
       """启动时一次性构建路由 → CaseConversionOptions 映射"""
       from starlette.routing import Match
       routes = getattr(getattr(app, "router", None), "routes", [])
       for route in routes:
           if hasattr(route, "endpoint") and hasattr(route, "path"):
               opts = getattr(route.endpoint, "_case_conversion_options", None)
               if opts:
                   self._route_options_cache[route.path] = opts
       self._cache_built = True
   ```

3. **修改 `_resolve_case_options`**
   ```python
   def _resolve_case_options(self, scope) -> Optional[CaseConversionOptions]:
       if not self._cache_built:
           self._build_route_cache(scope.get("app"))

       # 先尝试精确匹配
       path = scope.get("path", "")
       if path in self._route_options_cache:
           return self._route_options_cache[path]

       # 降级：遍历匹配（处理路径参数如 /api/users/{id}）
       # 仅在精确匹配失败时触发，且结果缓存
       ...原有逻辑，匹配后缓存到 self._route_options_cache[path]
   ```

**风险**: 低 — 缓存不可变元数据，无一致性问题

**验证**:
```bash
# 请求应正常工作，且减少每请求 CPU 开销
curl -s http://localhost:21574/api/auth/config | python3 -m json.tool
```

---

### T8: 统一 Attachment 模型定义

**涉及文件**: 4 个定义文件 + 41 个引用文件

**三处定义字段差异**:

| 字段 | chat.py | modes.py | attachment_handler.py |
|------|:---:|:---:|:---:|
| id | 必需 | 可选 | 必需 |
| mime_type | 必需 | 可选 | 必需 |
| name | 必需 | 可选 | 必需 |
| url | 可选 | 可选 | 必需 |
| file_uri | 可选 | 可选 | - |
| base64_data | 可选 | 可选 | - |
| google_file_uri | 可选 | - | - |
| role | - | 可选 | - |
| size | - | - | 可选 |
| upload_status | - | - | 可选 |

**实施步骤**:

1. **创建统一模型** `backend/app/models/attachment.py`
   ```python
   from pydantic import BaseModel
   from typing import Optional

   class Attachment(BaseModel):
       """统一附件模型 — 所有字段可选以兼容不同路由的需求"""
       id: Optional[str] = None
       mime_type: Optional[str] = None
       name: Optional[str] = None
       url: Optional[str] = None
       temp_url: Optional[str] = None
       file_uri: Optional[str] = None
       base64_data: Optional[str] = None
       google_file_uri: Optional[str] = None
       role: Optional[str] = None
       size: Optional[int] = None
       upload_status: Optional[str] = None

   class ChatAttachment(Attachment):
       """Chat 路由使用 — id/mime_type/name 必需"""
       id: str
       mime_type: str
       name: str
   ```

2. **逐步替换**（按风险从低到高）
   - Phase A: `attachment_handler.py` 改用 `Attachment`（删除 dataclass）
   - Phase B: `modes.py` 改为 `from ...models.attachment import Attachment`
   - Phase C: `chat.py` 改为 `from ...models.attachment import ChatAttachment as Attachment`

3. **验证每步**: 确保对应路由正常接受请求

**风险**: 中 — 41 个文件引用，需逐步替换并验证。建议分 3 个子步骤，每步验证。

---

## Phase 4（MEDIUM 优先级，互相独立可并行）

### T9: 大小写转换函数去重

**文件**: `backend/app/core/provider_param_whitelist.py` (17-30 行)

**问题**: `_snake_to_camel` / `_camel_to_snake` 与 `utils/case_converter.py` 功能重复

**差异**: whitelist 版本缺少前导下划线处理，但其调用场景不涉及前导下划线字段

**实施步骤**:
1. 在 `provider_param_whitelist.py` 顶部添加导入：
   ```python
   from ..utils.case_converter import snake_to_camel, camel_to_snake
   ```
2. 删除第 17-30 行的两个本地函数定义
3. 将文件内所有 `_snake_to_camel(` 替换为 `snake_to_camel(`
4. 将文件内所有 `_camel_to_snake(` 替换为 `camel_to_snake(`

**验证**:
```bash
cd backend && .venv/bin/python -c "from app.core.provider_param_whitelist import validate_mode_options; print('OK')"
```

---

### T10: 错误分类逻辑统一

**涉及文件**: 3 个

**三处逻辑对比**:
- `error_handler.py`: 检测 `'429'`/`'quota'`/`'400'`/`'503'`
- `modes.py:262-275`: 检测 `"resource_exhausted"`/`"rate limit"`/`"quota"` → 返回 429
- `modes.py:1758-1769`: 同上，内联重复

**实施步骤**:
1. **增强 `error_handler.py`**，新增 `classify_provider_error_code(error_str: str) -> int`：
   ```python
   def classify_provider_error_code(error_str: str) -> int:
       """根据错误消息推断 HTTP 状态码"""
       lowered = str(error_str).lower()
       rate_limit_keywords = ["429", "resource_exhausted", "exceeded your current quota",
                              "rate limit", "quota", "too many requests"]
       if any(kw in lowered for kw in rate_limit_keywords):
           return 429
       if any(kw in lowered for kw in ["400", "invalid"]):
           return 400
       if any(kw in lowered for kw in ["503", "overloaded", "unavailable"]):
           return 503
       return 500
   ```
2. **modes.py:262-275** — 删除 `_resolve_video_generation_error_status_code`，改为：
   ```python
   from ...utils.error_handler import classify_provider_error_code
   status_code = classify_provider_error_code(str(e))
   ```
3. **modes.py:1758-1769** — 同样替换内联逻辑

**验证**:
```bash
cd backend && .venv/bin/python -c "
from app.utils.error_handler import classify_provider_error_code
assert classify_provider_error_code('resource_exhausted') == 429
assert classify_provider_error_code('invalid request') == 400
assert classify_provider_error_code('unknown error') == 500
print('OK')
"
```

---

### T11: 启动任务并行化

**文件**: `backend/app/core/startup_tasks.py` (402-430 行)

**依赖分析**:

```
Group 1 (无依赖，并行):
  ├── setup_logger_configuration
  ├── initialize_encryption_keys
  ├── initialize_system_config
  ├── initialize_redis_pool
  └── validate_provider_configs

Group 2 (依赖 Group 1 的 DB 初始化):
  ├── migrate_user_admin_schema
  └── migrate_workflow_idempotency_schema

Group 3 (依赖 Group 2):
  ├── cleanup_expired_tokens
  └── reconcile_orphan_workflow_executions

Group 4 (依赖全部):
  └── start_worker_pool
```

**实施步骤**:
1. 将 `run_all_startup_tasks` 改为分组 gather：
   ```python
   async def run_all_startup_tasks():
       # Group 1: 无依赖，并行
       await asyncio.gather(
           setup_logger_configuration(),
           initialize_encryption_keys(),
           initialize_system_config(),
           initialize_redis_pool(),
           validate_provider_configs(),
       )

       # Group 2: DB 迁移（依赖初始化完成）
       await asyncio.gather(
           migrate_user_admin_schema(),
           migrate_workflow_idempotency_schema(),
       )

       # Group 3: 清理任务（依赖迁移完成）
       await asyncio.gather(
           cleanup_expired_tokens(),
           reconcile_orphan_workflow_executions(),
       )

       # Group 4: Worker 池（最后启动）
       await start_worker_pool()
   ```
2. 确保每个任务函数都是 `async def`（如果有同步的需用 `asyncio.to_thread` 包装）

**预期收益**: 启动时间减少 ~60-70%（从 10 串行变为 4 批并行）

**风险**: 低-中 — 需确认各任务的隐式依赖（如 logger 必须在其他任务记录日志前完成）

**缓解**: logger 放在 Group 1 最前面单独 await，其余并行：
```python
await setup_logger_configuration()  # 必须最先完成
await asyncio.gather(...)           # 其余 Group 1
```

**验证**:
```bash
# 重启服务，观察启动日志时间戳
# 各 [OK] 标记应更密集而非等间距
```

---

### T12: 清理 emoji 注释

**文件**: `frontend/hooks/useImageHandlers.ts`

**分类决策**:

| 注释 | 决策 | 原因 |
|------|------|------|
| `// ✅ 优先使用传入的 attachment 对象` | 删除 | 代码自解释 |
| `// ✅ 直接使用传入的 URL` | 删除 | 冗余 |
| `// ✅ 立即设置，不等待查询` | 删除 | 逻辑明确 |
| `// ✅ 只对 HTTP URL 查询` | 删除 | 条件显而易见 |
| `// 🚀 加速显示` | 删除 | 无实质信息 |
| `// ✅ 异步查询，但不阻塞显示` | **保留** (去 emoji) | 解释性能权衡 |
| `// 查询目的：获取永久云存储 URL` | **保留** (去 emoji) | 解释设计意图 |

**实施步骤**:
1. 删除约 14 处纯描述性 `// ✅` 和 `// 🚀` 注释
2. 保留 2-3 处解释 WHY 的注释，移除 emoji 前缀
3. 不涉及后端（后端 `// ✅` 已在 T1 中随代码删除清理）

**验证**: 文件仍能正常编译（Vite dev server 会自动热更新）

---

## 执行顺序总结

```
Phase 3 (并行):
  T6 (N+1 查询)  ─┐
  T7 (中间件缓存) ──┼── 全部完成后验证
  T8 (Attachment)  ─┘

Phase 4 (并行):
  T9  (大小写去重) ──┐
  T10 (错误分类)   ──┼── 全部完成后验证
  T11 (启动并行化) ──┤
  T12 (emoji 清理)  ─┘
```

## 风险矩阵

| 任务 | 风险 | 影响范围 | 回滚难度 |
|------|------|---------|---------|
| T6 | 低 | 1 文件 | 简单 git revert |
| T7 | 低 | 1 文件 | 简单 |
| T8 | **中** | 4 定义 + 41 引用 | 需分步回滚 |
| T9 | 低 | 1 文件 | 简单 |
| T10 | 低 | 3 文件 | 简单 |
| T11 | 低-中 | 1 文件 | 简单，但需重启验证 |
| T12 | 极低 | 1 文件 | 无风险 |

**建议**: T8 分 3 个子步骤实施，每步独立验证。其余任务可一步到位。
