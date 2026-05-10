# JIRA: Gemini Client Pool — Production Hardening

## 类型
Tech Debt / Reliability / Security / Performance / Production-Readiness

## 状态
Ready for Implementation

## 前置工作（已完成）
本工单是 [`JIRA-gemini-client-pool-unification.md`](./JIRA-gemini-client-pool-unification.md) 的**直接后续**。前置工作已在 `refactor/gemini-pool-unification` 分支上以 8 个 commit 落地：

| Commit | 主题 | JIRA 对应行 |
|---|---|---|
| `1bc61c5` | embedding_service + file_search 走 pool | line 80-81 |
| `55827b2` | [过渡，已被 39a31a7 撤回] 标 deprecated | — |
| `6c3abbe` | HttpOptions 抽到 services/gemini/http_options.py | 副产品 |
| `75b158a` | get_vertex_ai_credentials_from_db 抽到 services/gemini/credentials.py | 副产品 |
| `39a31a7` | agent 包装层底层走 GeminiClientPool（核心） | line 84 |
| `61e1113` | /verify-vertex-ai 加 try/finally close | line 88-91 |
| `ea18320` | geminiapi/main.py 标 STANDALONE | line 85-87 |
| `d64d128` | 统一池治理测试（含静态 AST 扫描） | line 154-158 |

**前置 JIRA 验收标准（line 117-126）落地情况**：第 1-6 项与第 9 项已通过 `test_gemini_client_pool_usage.py` 5 个测试 + 90 个相关测试验证为绿；第 7-8 项是非目标（image-chat-edit / image-mask-edit 行为）不动。

## 背景
前置 PR 完成后，由 5 个独立 reviewer agent（code-reviewer / security-reviewer / performance-optimizer / silent-failure-hunter / type-design-analyzer + architect）做生产就绪复审，得到如下汇总判定：

| Reviewer | Verdict |
|---|---|
| code-reviewer | WARNING — 精准但有缺口 |
| security-reviewer | **NO-GO** — 1 CRITICAL + 4 HIGH |
| performance-optimizer | **NO-GO** — 3 FAIL（OOM / 资源泄漏 / 锁瓶颈） |
| silent-failure-hunter | **NO-GO** — 4 HIGH（凭证 silent fallback / bare except / import swallow / 错误归因） |
| type-design-analyzer | WEAK — 5 design-bug（不在本次硬上线范围） |
| architect | Not Ready — 6 项必做 + 7 项建议 |

本工单的目标是把上述发现转成可追踪的、按优先级排序的、与"统一连接池"主题相关的修复项目，让分支真正达到上线就绪。

## 当前事实
- `refactor/gemini-pool-unification` 分支领先 origin/master 45 commit，未推送、未走 PR review
- `GeminiClientPool` 单例已统一所有运行链路 SDK client 创建源；包装类（`agent.Client`）底层亦走池
- 90/90 backend 测试绿
- 但池**无 size 上限**、**无 eviction**、**shutdown 未释放**——长进程 OOM 风险确定性存在
- 凭证加载链 `credentials.py` 在 `JSONDecodeError` 时静默 fallback 到 ADC，对错误身份发起请求
- `/verify-vertex-ai`、`embedding_service`、`file_search` 等多处存在静默错误吞噬
- 核心配置项 `GEMINI_TIMEOUT / GEMINI_RETRY_*` 无文档，未进 `.env.example`
- pool stats / hit_rate 实现存在但**无任何路由暴露**给运维

## 证据链

### 5 reviewer 输出位置（每位 reviewer 独立审查同一份 working tree）

代码审查具体 file:line 引用，按 reviewer 输出原文如下。

#### code-reviewer 关键发现
- `agent/models.py` 内 `Models / AsyncModels` 仍调用 `self._api_client.request(...)`、`self._api_client._verify_response(...)`、`self._api_client.async_request(...)` —— 这些方法在当前 `google-genai` 公共 API 上不存在（仅 `_api_client.py:1595, 1611, 1640, 2156` 私有 API 有）。意味着 wrapper.models.* 一旦被调用就 AttributeError。但仍在 `agent/__init__.py:__all__` export
- `agent/client.py:23-26` `import asyncio, json` + `from typing import ... Tuple` 全文未使用
- `JIRA 第 154 行` 建议的 `test_embedding_service_uses_client_pool` / `test_file_search_uses_client_pool_for_api_key` 两个 mock-based 测试缺失（当前仅有静态 AST 扫描间接覆盖）
- 55827b2（被 39a31a7 撤回的过渡补丁）仍在 git history，reviewer 看到 add→remove 对会困惑

#### security-reviewer 关键发现
- **CRITICAL**：`backend/credentials/gemini-495713-6b46d6f1fc80.json` 在磁盘上含真实 RSA-2048 私钥 → **本工单 Out of Scope（用户后期手动删除并轮换）**
- **HIGH**：`credentials.py:103-106` 把 decrypted service-account JSON 前 100 字符写入 `logger.debug` —— 前 100 字符里包含 `{"type": "service_account", "project_id": "<...>"`，可能含 `private_key_id`
- **HIGH**：`file_search.py:91, 92, 196, 203` Bearer token 解析 `authorization.split(' ')[1]`：`"Bearer "`（空 key）通过 startswith 检查但 yield `api_key=""`，被 pool `if not api_key: raise ValueError` 截获后变成 500 而非 401，且错误消息回显架构细节
- **HIGH**：`vertex_ai_config.py:274-290, 332-341`（pre-existing，非本 PR 引入）`edit_mode=True` 把解密后的 service account JSON 经 `vertex_ai_credentials_json` 字段返回前端
- **MEDIUM**：`client_pool.py:457` `repr(credentials)` fallback 不稳定 cache key（默认 `<ClassName object at 0xADDR>` 进程重启即变）；未来 `google-auth` 给 Credentials 加自定义 `__repr__` 可能泄漏 token state
- **MEDIUM**：`client_pool.py:452-470` cache key 用 `service_account_email` 指纹 → 用户轮换 SA 私钥（同 email 新 key）后旧 client 仍命中
- **MEDIUM**：`file_search.py:184-188, 219-221` `detail=f"File upload failed: {str(e)}"` 把 SDK 异常原文回给前端
- **MEDIUM**：`client_pool.py:195` `'api_key_prefix': api_key[:8]` —— Google AI key `AIzaSyXX` 前 8 字符同源项目共享，熵从 256 → ~168 bit
- **LOW**：`credentials.py:127-133` 外层 except 只 `WARNING` 而不 `ERROR`
- **LOW**：`vertex_ai_config.py:980-987` finally close 失败仅 `logger.debug` + `# pragma: no cover`

#### performance-optimizer 关键发现
- **FAIL**：`client_pool.py:_clients: Dict` 纯增不减，无 LRU、无 size 上限、无 TTL。实测每个 `google.genai.Client` ≈ **2.4 MB RSS**（含 httpx + httpcore connection pool），1K 用户独立 api_key → 2.3 GB，10K → 23 GB，OOM 确定
- **FAIL**：`backend/app/core/shutdown_tasks.py` 关 browser / worker_pool / redis_pool 三件，**未调** `get_client_pool().close_all()` —— graceful shutdown 时 client 资源不确定性释放
- **FAIL**：`google.genai.Client.close()` 实测 RSS 不回落（Python arena 不归还 OS），且与上一条叠加
- **WARN**：`client_pool.py:124-219` `get_client()` 持 `self._lock` 的整个期间执行 `google_genai.Client(...)`（实测 ≈ 83 ms），10 并发冷启动 cache miss 串行化最末一个等 ~830 ms
- **WARN**：`client_pool.py:_global_pool` + `__new__` 双层 DCL 冗余
- **WARN**：`agent/code_executor.py:266`、`memory_bank_service.py:318` 仍调 `vertexai.init(project=..., location=...)` —— 进程级状态污染未清理（前置 PR 只删了 `client_pool.py` 自己的 `vertexai.init`）

#### silent-failure-hunter 关键发现
- **HIGH**：`credentials.py:98-113` `json.JSONDecodeError` 仅记 `ERROR` 然后继续，`credentials = None` 一路返回 `(project, location, None)`；4 个 `interactions_manager.py` 调用方都按 `if db_credentials: ...` 模式，`None` 会**静默切换到 ADC 模式**——用户配的 service account 与实际跑的身份不一致
- **HIGH**：`vertex_ai_config.py:554, 560` 两处 bare `except:`（catches `BaseException`），无任何 logger，`description` 字段静默 fallback 到 `f'Google AI model: {model_id}'`
- **HIGH**：`embedding_service.py:14-17` `except Exception` 在 module-level import 失败时 swallow `ImportError`/`SyntaxError`/circular import 真实 traceback；运行时 30s 后第一次调用 `get_embedding` 才报"GeminiClientPool is required"，最大化 MTTD
- **HIGH**：`file_search.py:103-114` `client.file_search_stores.get(...)` 的 `except Exception` 把所有错（auth 失败 / quota / network / permission denied）当作 "store not found"，跳到 `.create()` 也失败后 outer except 报 "File upload failed: <create error>"——根因消失
- **MEDIUM**：`client_pool.py:302-306` `_to_genai_http_options` 在 `not GOOGLE_GENAI_AVAILABLE` 时 silently return None，timeout/retry 静默丢失
- **MEDIUM**：`client_pool.py:244-271` `_read_env_int / _read_env_float / _read_env_bool` 解析失败 silently 返回 default，operator 设 `GEMINI_TIMEOUT=0` 实际拿到 30000 不可见
- **MEDIUM**：`agent/client.py:65-71, 186-204` `close()` no-op + `__enter__/__exit__` 仍存在 → context-manager 契约假象
- **MEDIUM**：`vertex_ai_config.py:984-987` finally close `logger.debug` + `# pragma: no cover`，连接泄漏永久不可见
- **MEDIUM**：`file_search.py:176-181` 临时文件清理失败 `logger.warning` 但没记录 `temp_file_path`，磁盘满预兆不可定位

#### architect (ship-readiness) 关键发现
- **RED**：`pool.get_stats() / list_clients()` 实现存在但**无路由暴露**；`/health` payload（`backend/app/routers/system/health.py:184-192`）无 `gemini_pool` 字段
- **RED**：无 OTel/Prometheus instrumentation，`gemini_client_pool_hit_rate / active_clients / total_requests` 三个核心 metric 都没接出
- **RED**：`backend/.env.example` 未提及 `GEMINI_TIMEOUT / GEMINI_RETRY_*` 6 个环境变量
- **RED**：`shutdown_tasks.py` 未关闭 pool（与 perf FAIL #3 重合）
- **RED**：staging 验证计划缺失 —— JIRA 第 161、164 行明确提到长任务（视频生成）timeout/retry 行为变化风险
- **RED**：`backend/app/services/gemini/docs/README.md:60, 76` 仍在描述 `common/sdk_initializer.py / common/official_sdk_adapter.py` 是活路径，与当前 `_deprecated/` 状态不符
- **YELLOW**：JIRA-gemini-client-pool-unification.md 仍 "Ready for Implementation"，未 close-out，未回填 commit hash，未勾验收 9 项
- **YELLOW**：CI（`.github/workflows/ci.yml:113`）会跑 `tests/test_gemini_client_pool_usage.py` 但没独立 step，gate 信号弱
- **YELLOW**：master HEAD `db1153a` 含 WIP commit `4fd0c64`（4761 行 image-edit/video-gen 改动）—— 本分支基于其上，PR review 时两路改动耦合
- **YELLOW**：单例 pool per-worker，多 worker uvicorn 部署语义未在文档说明

#### type-design-analyzer 关键发现（不在本次 hardening 范围 —— defer）
- design-bug：`get_client(api_key, vertexai, project, location, credentials, http_options)` 平面 boolean 应换 sum type
- design-bug：`agent.Client` 与 raw `google.genai.Client` 双轨返回
- design-bug：`use_vertex` vs `vertexai` 命名分裂（handler 层用前者，pool 用后者）
- design-bug：`__enter__/__exit__` 与 no-op close 矛盾
- design-bug：`get_vertex_ai_credentials_from_db` 三 Optional tuple 不区分 4 种状态

## 问题陈述
前置 PR 把"运行链路统一连接池"做对了，但生产环境运行需要的：
- 资源生命周期治理（OOM 防护、shutdown 释放）
- 凭证 / 错误处理的可追溯（不静默回退、不吞异常）
- 可观测性（metric、admin endpoint、log 级别）
- 配置文档化（env vars、模块 README）

这些都没补完，**直接 push 到 origin 等于把已知缺口推到生产**。本工单是把上面散点修齐的统一治理。

## 用户故事
1. 作为后端运维，我希望进程长跑后不会因 pool 无界增长 OOM；我希望 graceful shutdown 时 client 被确定性释放
2. 作为后端调试者，我希望凭证加载失败不会被静默 fallback 到 ADC（错身份跑业务）；我希望 import 错误在启动期暴露而非运行期
3. 作为安全审计者，我希望日志里没有 decrypted service-account JSON、没有完整 SDK 异常 detail 回前端、没有 8 字符 api_key 前缀
4. 作为业务调用方，我希望 `file_search` 上传 / list 出错时知道是哪一步出错（auth / quota / network / 不存在）
5. 作为 SRE，我希望能从 admin 端点查询 pool hit_rate / active_clients；我希望 `.env.example` 有 6 个 GEMINI_* 旋钮的默认值与建议
6. 作为 reviewer，我希望本 PR 的 8 commit 不再带 history 噪声（add→remove 对），可单独 revert

## 修复范围

### P0 — 安全（5 项）

1. `credentials.py:103-106` 删除 decrypted JSON 前 100 字符 `logger.debug` 行（不论日志级别都不该 emit 凭证内容）
2. `client_pool.py:195` `api_key_prefix = api_key[:8]` → `[:4]` 或改为 boolean `api_key_configured`；`list_clients()` 返回值同步修正
3. `client_pool.py:452-470` `repr(credentials)` fallback 改为 `raise ValueError("Cannot derive stable cache identity from credentials object — service_account_email required")`，失败 fail-fast 而非用不稳定 repr
4. `file_search.py:91-96, 196-205` Bearer token 严格解析：`split(' ', 1)` + `strip()` + 长度校验；空 / 异常格式返回 401（而非进入 try 让 pool raise 500）
5. `file_search.py:184-188, 219-221` 不再用 `detail=f"...{str(e)}"`；改为 logger.error(exc_info=True) + 通用 client-facing message（`"File operation failed. Please try again."`）

### P0 — 资源回收 / 内存（3 项）

6. `client_pool.py` 增加 `MAX_POOL_SIZE` 常量（默认 200，可被 `GEMINI_POOL_MAX_SIZE` env 覆盖）；`get_client()` 在创建前检查 `len(self._clients) >= MAX_POOL_SIZE` 时 raise `RuntimeError("GeminiClientPool size limit reached")`
7. `backend/app/core/shutdown_tasks.py` 在 `run_all_shutdown_tasks` 末尾追加 `get_client_pool().close_all()` 调用，与 redis_pool 平级
8. `backend/app/services/gemini/agent/code_executor.py:266`、`memory_bank_service.py:318` 移除 `vertexai.init(project=..., location=...)` 进程级状态污染调用，改为用本地 `google.genai.Client(vertexai=True, project=..., location=...)` 路径走 `get_client_pool()`（与前置 PR 删除 `client_pool.py` 自己的 `vertexai.init` 同向）

### P0 — Silent Failure（4 项）

9. `credentials.py:98-113` `json.JSONDecodeError` 改为 fail-fast：内层 raise ValueError；调用方 `interactions_manager.py` 4 处把 ValueError 传播为 HTTP 500，不再静默 fallback ADC
10. `vertex_ai_config.py:554, 560` 替换两处 bare `except:` 为 `except Exception as e: logger.warning(f"...: {e}", exc_info=True)`
11. `embedding_service.py:14-17` 在 `except Exception as e:` 内 `logger.warning(f"Failed to import GeminiClientPool: {e}", exc_info=True)`，避免静默吞掉 import 错误
12. `file_search.py:103-114` 只 catch `google.api_core.exceptions.NotFound`（或 SDK 等价），其他异常传播；如确认 SDK 用别名异常则查 `google.genai.errors`

### P0 — 错误处理细节（3 项）

13. `vertex_ai_config.py:980-987` finally close 失败 `logger.debug` → `logger.warning`，移除 `# pragma: no cover`，加测试覆盖（mock close raise）
14. `client_pool.py:244-271` `_read_env_int / _read_env_float / _read_env_bool` 在 fallback default 之前 `logger.warning(f"[GeminiClientPool] Invalid value for {name}={raw!r}, using default={default}")`
15. `client_pool.py:302-306` `_to_genai_http_options` 在 `not GOOGLE_GENAI_AVAILABLE` 分支 raise RuntimeError 而非 silent return None；与 `get_client` 内部已有的 RuntimeError 检查统一

### P1 — 上线前必备（5 项）

16. `backend/.env.example` 补 6 个 GEMINI_* 环境变量及默认值与说明：`GEMINI_TIMEOUT`、`GEMINI_RETRY_ATTEMPTS`、`GEMINI_RETRY_INITIAL_DELAY`、`GEMINI_RETRY_MAX_DELAY`、`GEMINI_RETRY_EXP_BASE`、`GEMINI_RETRY_JITTER`；同时补 `GEMINI_POOL_MAX_SIZE`（P0 #6 引入）
17. 新增 admin endpoint `GET /api/system/admin/gemini-pool/stats`，返回 `pool.get_stats()`（已在 `client_pool.py:403-424` 实现）；用 `require_admin_user` guard
18. `/health` payload（`backend/app/routers/system/health.py:184-192`）增加 `gemini_pool` 字段：`{ initialized: bool, sdk_available: bool, active_clients: int }`
19. `backend/app/services/gemini/docs/README.md` 同步更新：移除/标注 `common/sdk_initializer.py`、`common/official_sdk_adapter.py` 已 deprecated 状态；增加 "How to use GeminiClientPool" 5 行示例 + "When to NOT use" 1 段
20. `backend/app/services/gemini/docs/README.md` 加多 worker 部署语义说明：`pool 是 per-worker 进程，hit_rate / active_clients 是单 worker 视角；告警阈值需乘 worker 数`

### P1 — 测试覆盖（3 项）

21. `tests/test_gemini_client_pool_usage.py` 新增 `test_embedding_service_uses_client_pool`：用 monkeypatch + 拦截 `pool.get_client` 调用，验证 `get_embedding(...)` 真的走池且参数 `vertexai=False`
22. `tests/test_gemini_client_pool_usage.py` 新增 `test_file_search_uses_client_pool_for_api_key`：同上对 `POST /api/file-search/upload` 用 TestClient + mock SDK
23. `tests/test_gemini_client_pool_usage.py` 新增 `test_pool_max_size_raises_when_exceeded`：连续 `get_client(api_key=f"k{i}")` 直到 `MAX_POOL_SIZE`，第 N+1 次 raise RuntimeError

### P1 — 文档与流程（4 项）

24. 在 [`JIRA-gemini-client-pool-unification.md`](./JIRA-gemini-client-pool-unification.md) 第 7 行状态从 "Ready for Implementation" 改为 "Done"；逐条勾验收（line 117-126 共 9 项），每条后追加 commit hash
25. PR description 必须含 staging 验证清单：(a) image-chat-edit 走 Gemini API 一次真实调用、(b) image-mask-edit / image-background-edit 走 Vertex 各一次、(c) video-gen 长任务（Veo 3 60s+）timeout 不丢——三类都要附 log 截图
26. CI（`.github/workflows/ci.yml`）增加独立 step `Run gemini-client-pool unification gate`，单独跑 `pytest tests/test_gemini_client_pool_usage.py -v`，失败时 grep signal 明显
27. `.github/workflows/pr-check.yml` 镜像同样的 gate，让"主链路新增 `genai.Client(...)`"在 PR check 阶段就 fail-fast

## 非目标
- **不删除** 5 个 `agent/{client,models,interactions,types,common}.py` 文件（前置 JIRA 第 84 行明确"保留包装层"，用户也已表明态度）
- **不重构** type-design-analyzer 提的 5 个 design-bug（sum type / 命名统一 / `__enter__/__exit__` 删除等）—— 单独工单
- **不接入** OTel/Prometheus 指标 —— 单独工程项目
- **不处理** master 上的 WIP commit `4fd0c64`（4761 行 image-edit/video-gen 改动）—— 是 master 自己的事
- **不处理** image-chat-edit / image-mask-edit / image-background-edit 路由层语义（前置 JIRA 已声明非目标，本次同样）
- **不重写** git history（不 squash 55827b2 的过渡补丁；commit message 已交代清楚）

## Out of Scope（用户明示后期处理）

- **`backend/credentials/gemini-495713-6b46d6f1fc80.json`**：磁盘上的真实 GCP service-account 私钥文件。security-reviewer 标 CRITICAL，**不在本工单代码改动范围**——用户后期会手动：
  1. 在 GCP IAM 轮换 / 撤销该 service account key
  2. `rm` 删除磁盘文件
  3. 改用 Secret Manager / 环境变量注入
- **`vertex_ai_config.py:274-290, 332-341` 的 `edit_mode=True` 回显 service-account JSON**（pre-existing，不是本次重构引入）—— security-reviewer 标 HIGH 但属于配置管理 UI 设计问题，单独工单跟踪

## 验收标准

### 强约束（必须全部满足）
- [ ] P0 全部 15 项落地，对应 commit hash 回填本文档
- [ ] `backend/tests/test_gemini_client_pool_usage.py` 至少含 8 个测试（5 个原有 + 3 个 P1 新增）；全部 PASS
- [ ] `pytest tests -q` 全绿（≥ 90 个 + 新增 = ≥ 93 个）
- [ ] 进程内 OOM 防护实证：手动构造 ≥ `MAX_POOL_SIZE` + 1 次 get_client 调用，验证第 N+1 次 RuntimeError
- [ ] graceful shutdown 实证：`SIGTERM` uvicorn 主进程后，log 中可见 `Gemini client pool closed` 行
- [ ] `GET /api/system/admin/gemini-pool/stats` 真实返回 `total_clients / active_clients / cache_hits / cache_misses / hit_rate`
- [ ] `/health` payload 含 `gemini_pool` 字段
- [ ] `backend/.env.example` grep 7 个 `GEMINI_` 变量全部存在并含注释
- [ ] `JIRA-gemini-client-pool-unification.md` 状态改 Done + 9 项验收逐条勾选 + commit hash 回填
- [ ] PR description 含三组 staging 验证证据（chat-edit / mask-edit / video-gen long-task）
- [ ] CI 跑过 `Run gemini-client-pool unification gate` 独立 step

### 软约束（强烈建议）
- [ ] cache hit log 升 INFO 或 sampled INFO（每 N 次出一次）
- [ ] type-design 的 5 个 design-bug 单独 ticket 跟踪
- [ ] `agent/models.py` 的 broken `Models.generate_content` 在文件顶部加注释明确"与当前 SDK 私有 API 不兼容、待 Models 类下一轮重构"

## 建议实现步骤

按依赖顺序，每步独立 commit：

### Step 1：安全收口（P0 #1-#5）
- `credentials.py` 删除 100 字符 debug log
- `client_pool.py` `api_key_prefix` 改 4 字符 / 改 boolean
- `client_pool.py` `repr(credentials)` fallback fail-fast
- `file_search.py` Bearer 严格解析 + 401
- `file_search.py` 500 detail 不回显内部异常

### Step 2：资源回收（P0 #6-#8）
- `client_pool.py` 加 `MAX_POOL_SIZE` 检查
- `shutdown_tasks.py` 加 `pool.close_all()` 调用
- `code_executor.py` / `memory_bank_service.py` 移除 `vertexai.init`

### Step 3：Silent Failure 收口（P0 #9-#15）
- `credentials.py` JSONDecodeError fail-fast
- `vertex_ai_config.py` 替换 bare except
- `embedding_service.py` 顶部 import 加 log
- `file_search.py` store get 只 catch NotFound
- `vertex_ai_config.py` finally close DEBUG → WARNING + 移除 pragma
- `client_pool.py` env var 解析失败加 warning
- `client_pool.py` `_to_genai_http_options` GOOGLE_GENAI_AVAILABLE 失败 raise

### Step 4：可观测性 endpoint（P1 #17-#18）
- 新增 `/api/system/admin/gemini-pool/stats`
- `/health` payload 加 `gemini_pool`

### Step 5：配置文档化（P1 #16, #19, #20）
- `.env.example` 补 7 个 GEMINI_*
- `services/gemini/docs/README.md` 同步 + 加使用示例 + 加多 worker 说明

### Step 6：测试补齐（P1 #21-#23）
- `test_embedding_service_uses_client_pool`
- `test_file_search_uses_client_pool_for_api_key`
- `test_pool_max_size_raises_when_exceeded`

### Step 7：CI / JIRA close-out（P1 #24-#27）
- 前置 JIRA 改 Done + 回填 commit hash + 勾 9 项验收
- `.github/workflows/ci.yml` 加独立 gate step
- `.github/workflows/pr-check.yml` 镜像 gate

### Step 8：staging 验证 + PR
- 跑三组真实流量（chat-edit / mask-edit / video-gen long-task），截图 / log
- 写 PR description 附验证证据
- push origin + 开 PR

## 推荐测试命令

```bash
cd /mnt/user/appdata/gemini-main/backend

# 单元 + 静态扫描（已有）
.venv/bin/python -m pytest tests/test_gemini_client_pool_usage.py -v

# 全相关回归
.venv/bin/python -m pytest \
    tests/test_gemini_client_pool_usage.py \
    tests/test_google_vertex_model_deprecations.py \
    tests/test_google_video_generation_coordinator.py \
    tests/test_vertex_expand_service.py \
    tests/test_google_video_common.py \
    tests/test_modes_video_attachment_params.py \
    tests/test_workflow_video_generate_kwargs.py \
    -q

# 全 backend
.venv/bin/python -m pytest tests -q

# Pool size 防护实证（需在 fixture 内 monkeypatch MAX_POOL_SIZE=2）
.venv/bin/python -m pytest tests/test_gemini_client_pool_usage.py::test_pool_max_size_raises_when_exceeded -v

# Shutdown 资源释放实证
# 手动启动 uvicorn → curl 几次 endpoint 触发 client 创建 → SIGTERM → grep log "Gemini client pool closed"
GEMINI_LOG_LEVEL=INFO uvicorn app.main:app --port 8000 &
PID=$!
sleep 2
curl -X POST http://localhost:8000/api/file-search/upload -H "Authorization: Bearer test" --form file=@/tmp/test.txt
kill -TERM $PID
wait $PID
```

## 建议新增测试点

| 测试名 | 验证 | 优先级 |
|---|---|---|
| `test_pool_max_size_raises_when_exceeded` | P0 #6 | 必加 |
| `test_pool_close_all_called_on_shutdown` | P0 #7（用 lifespan / asgi-lifespan 跑 lifecycle event） | 必加 |
| `test_embedding_service_uses_client_pool` | P1 #21（mock pool.get_client + get_embedding 调用参数） | 必加 |
| `test_file_search_uses_client_pool_for_api_key` | P1 #22（TestClient + mock SDK）| 必加 |
| `test_credentials_json_decode_error_raises_not_silent_adc` | P0 #9 | 必加 |
| `test_file_search_store_get_propagates_non_notfound_errors` | P0 #12 | 必加 |
| `test_bearer_token_empty_returns_401_not_500` | P0 #4（覆盖 `"Bearer "`、`"Bearer  "`、`"Bearer "`） | 必加 |
| `test_gemini_pool_stats_endpoint_returns_metrics` | P1 #17 | 必加 |
| `test_health_payload_contains_gemini_pool` | P1 #18 | 必加 |
| `test_close_failure_logs_warning_not_debug` | P0 #13（mock client.close raise + caplog 验证 WARNING）| 加分项 |

## 风险

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| `MAX_POOL_SIZE=200` 在某些场景仍过大 / 过小 | M | M | 用 env var 覆盖；运行 1 周观测 hit_rate 后调整 |
| `credentials.py` JSONDecodeError 改 fail-fast 后，原本静默工作的部署崩了 | L | H | staging 跑 1 周；若崩立即定位是 DB 中加密格式 vs key 不匹配，是真实 bug |
| `file_search.py` 改严格 Bearer 解析后，旧 client 用 `Bearer  key` (双空格) 失效 | L | M | 加监控；告警后联系 client 升级 |
| `vertexai.init()` 移除后 `code_executor` 与 `memory_bank_service` 异常 | M | M | staging 跑前先用 `pytest -k code_executor or memory_bank` 验证；保留 ADC 路径作 fallback |
| `shutdown_tasks.py` 加 close_all 改动测不出来（lifespan 测试基础设施缺）| H | L | 至少跑一次手动 SIGTERM 验证；`asgi-lifespan` 有现成方案 |
| 修复堆叠在已有 8 commit 之上，单分支 commit 数 = 8 + ~12 ≈ 20 | M | L | 接受；上线前可选 squash 到 4-5 个语义 commit |

## 交接备注

1. **此工单是上线前 hard gate**——不做完不能 ship 到生产。
2. **优先级严格**：Step 1-3（P0）必须先做，Step 4-7（P1）随后，Step 8（staging + PR）最后。
3. **工作量估算**：Step 1-3 约 12 个文件改动，Step 4-7 约 8 个文件改动 + 测试，Step 8 是流程时间。预计 1.5-2 工作日。
4. **使用 agent teams**：本工单的源数据来自 5 个并行 reviewer agent。后续每完成一个 Step 建议再用 1 个 reviewer agent 做 spot-check（比如 Step 1 完成后用 security-reviewer 跑一遍）。
5. **commit message 必引用本工单**：每个 commit 头部带 `(closes JIRA-gemini-pool-production-hardening.md#P0-N)` 或 `(JIRA hardening Step X)`，可追溯。
6. **GCP private key 文件**（Out of Scope）：用户已确认后期处理。本工单代码改动**不依赖** 该文件被删除——但若该文件未删而 PR 已 merge，安全态势仍存在 CRITICAL 风险。建议在 PR description 显式提示 reviewer 注意 `backend/credentials/.gitkeep` 旁的实际文件。
