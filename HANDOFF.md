# HANDOFF — Gemini Client Pool Unification + Production Hardening

> **截止日期**：2026-05-10
> **分支**：`refactor/gemini-pool-unification`（领先 origin/master 49 commit）
> **状态**：代码改动完成；staging 验证 + push 待后期执行

---

## 0. 项目硬规则（违反即拒绝合并）

适用所有人、所有 PR、所有 agent 操作。本节约束效力高于本文其他章节。

1. **禁止补丁式修改**。每次改动必须直击根因；不允许"先标 deprecated 后清理"、"加 backward-compat re-export 兼容"、"加 try/except 吞掉问题让构建过"这类拖延式做法。
2. **agent 禁止无用输出**。Agent 在每次工具调用之前的文字必须只包含：(a) 这一步要做什么、(b) 必要的事实声明（如 GateGuard facts）；不重复用户已知信息、不写宣言式总结、不写"现在我将…"句式。Token 用在改代码上。
3. **精准修复**。一次只解决一个明确的问题；改动文件数与目标问题强相关；不附带"顺手清理"的无关动作（除非属于本次 commit 的同一主题）。
4. **任何 bug 不分高/中/低都必须修**。reviewer agent 报告或人工评审里出现的 LOW / MEDIUM / HIGH 全部纳入清单逐条解决；要 defer 的必须明文写在工单 "Out of Scope" 节并说明原因。

违反这 4 条任一项的 PR 应直接 close + 重做，不接受"再补一个 commit 就好"的妥协。

---

本文档是这次**两阶段重构**的接手指南。新人阅读顺序：

1. 先看本文（5 分钟掌握全局）
2. 再看 [`backend/app/services/gemini/docs/README.md`](backend/app/services/gemini/docs/README.md) 的 "GeminiClientPool — 统一客户端池" 章节（5 分钟掌握用法）
3. 深入实现细节再看 [`JIRA-gemini-client-pool-unification.md`](JIRA-gemini-client-pool-unification.md) + [`JIRA-gemini-pool-production-hardening.md`](JIRA-gemini-pool-production-hardening.md)

---

## 一、本次工作做了什么

### 阶段 1：统一连接池（前置，已 Done）

8 个 commit（`1bc61c5` ~ `d64d128`），核心目标：**所有运行链路 SDK client 创建必须走 `GeminiClientPool` 单例**。

具体动作：
- `embedding_service.get_embedding()` + `routers/system/file_search.py` 改走 pool（**核心 P0**）
- `agent/Client / AsyncClient / Models / AsyncModels / Interactions` 包装层**保留**，但底层 `_genai_client` 来自 pool（不再自建 `genai.Client(...)`）
- `Client.close() / aclose()` 改 no-op（生命周期由 pool 管，避免 wrapper close 关掉池中共享 client）
- `HttpOptions / HttpRetryOptions / HttpOptionsDict` 抽到 `services/gemini/http_options.py`（不再绑死 `agent/types.py`）
- `get_vertex_ai_credentials_from_db` 抽到 `services/gemini/credentials.py`
- `/verify-vertex-ai` 加 try/finally + close + 注释（一次性凭证验证路径，不入池）
- `geminiapi/main.py` 顶部标 STANDALONE（独立 FastAPI app，不挂主 backend）
- 加 `tests/test_gemini_client_pool_usage.py` 含 5 个验收测试（含 AST 静态扫描禁止主链路新增 `genai.Client(`）

### 阶段 2：上线前 hardening（本次 Done）

8 个 commit（`9866846` ~ `6364b0c`），**P0 + P1 全部 27 项落地**：

| Step | Commit | 主题 | 关键改动 |
|---|---|---|---|
| Step 1 | `583fb69` | P0 安全收口 (#1-#5) | credentials log 删除、api_key_prefix → boolean、`repr()` fail-fast、Bearer 严格解析 → 401、500 detail 不回显 |
| Step 2 | `483b9bc` | P0 资源回收 (#6-#8) | **MAX_POOL_SIZE 防 OOM**、shutdown 关闭池、移除 `vertexai.init()` 进程级污染 |
| Step 3 | `1bf9c80` | P0 Silent Failure (#9-#15) | JSONDecodeError fail-fast（不再静默 fallback ADC）、bare except 替换、import error 加 log、store get 仅 catch NotFound、env var warning、http_options raise |
| Step 4 | `ff120e8` | P1 可观测性 (#17, #18) | `GET /api/system/admin/gemini-pool/stats` + `/health.gemini_pool` 字段 |
| Step 5 | `fde40dd` | P1 配置文档 (#16, #19, #20) | `.env.example` 补 7 个 GEMINI_*、模块 README 加使用示例与多 worker 说明 |
| Step 6 | `14eca53` | P1 测试补齐 (#21-#23) | embedding/file_search mock 测试 + max_size + 加分项共 +15 个测试 |
| Step 7 | `6364b0c` | P1 CI gate + JIRA close-out | ci.yml 独立 gate、pr-check.yml 镜像 gate、前置 JIRA 改 Done + 9 项验收勾选 |

---

## 二、关键文件清单（按重要性）

### 核心治理点（必须熟悉）

| 文件 | 作用 | 何时改它 |
|---|---|---|
| [`backend/app/services/gemini/client_pool.py`](backend/app/services/gemini/client_pool.py) | **GeminiClientPool 单例** —— 唯一合法的 raw `genai.Client` 创建源 | 调整 cache key 策略 / pool 上限 / HTTP defaults |
| [`backend/app/services/gemini/http_options.py`](backend/app/services/gemini/http_options.py) | HTTP 配置类型（`HttpOptions / HttpRetryOptions / HttpOptionsDict`） | 添加新 retry / timeout 字段 |
| [`backend/app/services/gemini/credentials.py`](backend/app/services/gemini/credentials.py) | Vertex AI service-account 凭证加载 | 改 DB 查询 / 解密链路 |
| [`backend/app/services/gemini/agent/client.py`](backend/app/services/gemini/agent/client.py) | Wrapper `Client / AsyncClient`（底层走 pool） | **不要新加自建 `genai.Client(...)`**——改了会被 CI gate 拦 |
| [`backend/tests/test_gemini_client_pool_usage.py`](backend/tests/test_gemini_client_pool_usage.py) | 治理验收 + AST 静态扫描 | 加新业务路径走池的回归测试 |

### 调用方（参考用法）

- `services/common/embedding_service.py:get_embedding` — pool 用法范例
- `routers/system/file_search.py` — Bearer + pool 用法范例
- `routers/models/vertex_ai_config.py:/verify-vertex-ai` — **保留** 直接 client 的合法白名单（一次性验证路径）
- `services/gemini/coordinators/video_generation_coordinator.py` — 业务侧用 pool 的范例

### 运维 endpoint

- `GET /health` —— 包含 `gemini_pool: { initialized, sdk_available, active_clients, max_size }`
- `GET /api/system/admin/gemini-pool/stats` —— 受 admin guard，含完整 `cache_hits / hit_rate / clients` 等

### 配置（`.env`）

| Env var | Default | 说明 |
|---|---|---|
| `GEMINI_POOL_MAX_SIZE` | 200 | 池上限，超出 raise RuntimeError 防 OOM |
| `GEMINI_TIMEOUT` | 30000 | 单次 HTTP 超时（毫秒） |
| `GEMINI_RETRY_ATTEMPTS` | 3 | 瞬时故障重试次数 |
| `GEMINI_RETRY_INITIAL_DELAY` | 1.0 | 首次重试间隔（秒） |
| `GEMINI_RETRY_MAX_DELAY` | 60.0 | 重试间隔上限（秒） |
| `GEMINI_RETRY_EXP_BASE` | 2.0 | 退避指数底数 |
| `GEMINI_RETRY_JITTER` | true | 抖动 |

完整说明见 [`backend/.env.example`](backend/.env.example) 中 "Gemini 连接池调优" 章节。

---

## 三、后期开发硬约束（违反会被 CI 拦）

### ❌ 不要做

```python
# 主运行链路绝对不能写
from google import genai
client = genai.Client(api_key=k)  # CI test_direct_genai_client_creation_is_allowlisted_only 会 fail
```

```python
# 不要 with 包装类（close 是 no-op，with 块退出不会释放）
from app.services.gemini.agent import Client
with Client(api_key=k) as c:  # 误导性契约
    ...
```

```python
# 不要在主链路 import 已 deprecated 的旧路径
from app.services.gemini.common.sdk_initializer import SDKInitializer  # 已迁至 _deprecated/
from app.services.gemini.common.official_sdk_adapter import OfficialSDKAdapter  # 已迁至 _deprecated/
```

### ✅ 应该这样做

```python
# Gemini API
from app.services.gemini.client_pool import get_client_pool

client = get_client_pool().get_client(api_key=user_api_key, vertexai=False)
response = client.models.generate_content(...)
```

```python
# Vertex AI（用 service-account credentials）
from app.services.gemini.client_pool import get_client_pool
from app.services.gemini.credentials import get_vertex_ai_credentials_from_db

project, location, creds = get_vertex_ai_credentials_from_db(user_id, db)
client = get_client_pool().get_client(
    vertexai=True,
    project=project,
    location=location,
    credentials=creds,
)
```

```python
# 自定义 timeout（视频生成等长任务）
from app.services.gemini.http_options import HttpOptions, HttpRetryOptions

client = get_client_pool().get_client(
    api_key=user_api_key,
    vertexai=False,
    http_options=HttpOptions(
        timeout=600000,  # 10 分钟
        retry_options=HttpRetryOptions(attempts=5, initial_delay=2.0),
    ),
)
```

### ⚠️ 白名单（仅这 3 处允许直接 `genai.Client(...)`）

1. `services/gemini/client_pool.py` — 池内部唯一合法的创建点
2. `routers/models/vertex_ai_config.py:/verify-vertex-ai` — 用户尚未保存的临时凭证一次性验证
3. `services/gemini/geminiapi/main.py` — STANDALONE 独立 FastAPI app

新增任何主链路代码用直接 `genai.Client(` 都会被 `tests/test_gemini_client_pool_usage.py:test_direct_genai_client_creation_is_allowlisted_only` AST 扫描拦截。

---

## 四、Step 8（待你做的事）

### 8.1 staging 验证（强约束，PR 必须附证据）

按 hardening JIRA P1 #25 要求的三组真实流量：

| 类型 | 路径 | 验证目标 |
|---|---|---|
| (a) image-chat-edit | 走 Gemini API | 实际跑通一次，前端传入 model ID 原样到达后端，无 Vertex publisher model 错误 |
| (b) image-mask-edit + image-background-edit | 走 Vertex AI | 各跑通一次，验证 Imagen edit 模型，拒绝 Gemini image |
| (c) video-gen 长任务 | Veo 3.1 60s+ | timeout 不丢，shutdown 时 pool 正常 close_all |

**现成工具**：
- `npm run e2e:agent` —— `scripts/e2e/agent_workflow_e2e.mjs`（agent workflow 真实流量）
- `npm run e2e:video:real` —— `scripts/e2e/google_video_ui_e2e.py`（**Veo 视频真实流量**，c 项可直接用）
- 手动 UI 操作 + `npm run dev` 启动开发环境跑 a/b 项

### 8.2 push origin 与 PR

```bash
git push origin refactor/gemini-pool-unification
gh pr create --title "feat(backend): GeminiClientPool 统一治理 + 上线前 hardening"
```

PR description 必须含：
1. JIRA 工单引用（前置 + hardening 两份）
2. staging 验证 3 组真实流量截图 / log
3. 关键变更摘要（按 JIRA hardening 的 7 个 Step 列）
4. 风险点（参见 hardening JIRA "风险" 表格 6 项）

### 8.3 GCP 私钥（已删除，但需 GCP 侧轮换）

`backend/credentials/gemini-495713-6b46d6f1fc80.json` 已 `rm` 删除（commit 之外操作）。**仍需在 GCP IAM 控制台**：
1. 撤销该 service account key（`6b46d6f1fc80...`）
2. 改用 Secret Manager 注入凭证；不要再放磁盘

---

## 五、已知的 follow-up（不属本次 PR）

按 hardening JIRA "非目标 / Out of Scope" 列出，需要单独 ticket：

1. **type-design 改造**（5 个 design-bug）：
   - `get_client(api_key, vertexai, project, location, credentials, http_options)` 平面 boolean → sum type / discriminated union
   - `agent.Client` vs raw `google.genai.Client` 双轨返回
   - `use_vertex` vs `vertexai` 命名分裂
   - `__enter__/__exit__` 与 no-op `close()` 的 context-manager 契约假象
   - `get_vertex_ai_credentials_from_db` 三 Optional tuple 不区分 4 种状态
2. **OTel/Prometheus 指标接入** —— `gemini_client_pool_hit_rate / active_clients / total_requests`
3. **`vertex_ai_config.py edit_mode` 回显凭证** —— pre-existing HIGH 安全问题，单独 ticket
4. **master WIP commit `4fd0c64` 处理** —— master 上有 4761 行 image-edit/video-gen 改动，需 rebase 排除或先合 PR
5. **`agent/models.py` broken `Models.generate_content`** —— 内部用 `_api_client.request(...)` 对当前 SDK 已 broken；保留 wrapper 接口但内部需重构
6. **多视角 agent 复审** —— 临门一脚再用 split-role 子代理（observability / consistency / redundancy）做最终把关

---

## 六、跑测试快速命令

```bash
# 单元 + 静态扫描（核心 gate）
cd backend && .venv/bin/python -m pytest tests/test_gemini_client_pool_usage.py -v

# 全相关回归
cd backend && .venv/bin/python -m pytest \
    tests/test_gemini_client_pool_usage.py \
    tests/test_google_vertex_model_deprecations.py \
    tests/test_google_video_generation_coordinator.py \
    tests/test_vertex_expand_service.py \
    -q

# 全 backend
cd backend && .venv/bin/python -m pytest tests -q

# Real Veo video E2E（c 项验证用）
backend/.venv/bin/python scripts/e2e/google_video_ui_e2e.py
```

---

## 七、相关文档地图

```
gemini-main/
├── HANDOFF.md                                    # 本文档（接手指南）
├── JIRA-gemini-client-pool-unification.md        # 阶段 1 工单（Done，含 commit 序列）
├── JIRA-gemini-pool-production-hardening.md      # 阶段 2 工单（Done，含 27 项验收）
├── docs/
│   ├── BE-GENAI-CLIENT-REFACTOR.md               # ⚠️ HISTORICAL（已加 banner）
│   ├── ANALYSIS_GENAI_SDK_INTEGRATION.md         # ⚠️ HISTORICAL（已加 banner）
│   ├── code-review-*.md                          # 与本主题无关
│   └── execplans/PRODUCTION-READINESS-AUDIT.md   # 与本主题无关
└── backend/app/services/gemini/docs/
    └── README.md                                  # 当前权威使用文档（含 GeminiClientPool 用法 + 多 worker 说明）
```

---

## 八、reviewer agent 输出归档（如需追溯审查依据）

本次 hardening 工单源自 5 个独立 reviewer agent 的并行复审输出（保存在 `tasks/` 临时目录，会话结束清除；JIRA hardening 文档第 35-115 行已**摘要**核心发现 + file:line 锚点）：

- **code-reviewer**: WARNING — 精准但有缺口（`agent/Models` broken / 测试缺口 / history squash 建议）
- **security-reviewer**: NO-GO → P0 #1-#5 解决（除 GCP 私钥文件 Out of Scope 已删）
- **performance-optimizer**: NO-GO → P0 #6-#8 解决（OOM 防护、shutdown、vertexai.init 移除）
- **silent-failure-hunter**: NO-GO → P0 #9-#15 解决（JSONDecodeError fail-fast 等 7 项）
- **type-design-analyzer**: WEAK → 5 个 design-bug 列入 Defer（见上文 follow-up #1）
- **architect (ship-readiness)**: Not Ready → P1 全部 12 项解决

工单完整证据链见 [`JIRA-gemini-pool-production-hardening.md`](JIRA-gemini-pool-production-hardening.md) 第 33-115 行 "证据链" 章节。
