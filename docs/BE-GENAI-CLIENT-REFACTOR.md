# BE-GENAI-CLIENT-REFACTOR

## GenAI SDK Client 包装层架构修复计划

> 状态：待执行
> 优先级：高（影响可维护性和 SDK 升级安全性）
> 约束：仅重构内部架构，不改变任何外部 API 行为
> 最后更新：2026-03-24

---

## 1. 问题总述

当前后端在官方 `google.genai.Client` 之上堆叠了多层包装，导致：
- 包装层被大面积绕过（21 处 `getattr(x, "_genai_client", x)` 或直接访问 `_genai_client`）
- 存在 4 条语义重叠的 Client 获取路径
- 部分模块重新实现了 SDK 内部 API 调用（依赖私有方法 `client.request()`）
- 新开发者需要理解全部层次才能做出正确选择

---

## 2. 现状架构分析

### 2.1 当前分层

```
调用者（10+ 个 service）
    │
    ├─ 路径 A: get_client_pool().get_client()          ← 大多数 vertexai/ 服务
    ├─ 路径 B: OfficialSDKAdapter._get_client()        ← GoogleService chat/generate
    ├─ 路径 C: SDKInitializer.ensure_initialized()     ← ChatHandler 等
    └─ 路径 D: genai_agent/client.get_genai_client()   ← genai_agent 子模块
            │
            ▼
    GeminiClientPool（单例连接池）
        ├─ vertexai=False → google.genai.Client（原生）
        └─ vertexai=True  → agent/client.py Client（包装器）
                                │
                                ├─ agent/models.py Models     ← 重新实现 generate_content，
                                │                                调用 client.request()（私有方法）
                                ├─ agent/interactions.py      ← 包装 interactions API
                                └─ _genai_client               ← 底层 google.genai.Client
```

### 2.2 各层文件清单与职责

| 文件 | 类/函数 | 职责 | 行数 |
|------|---------|------|------|
| `agent/client.py` | `Client` | 包装 `genai.Client`，加 vertexai.init()、credential 解析、HttpOptions 转换 | 408 |
| `agent/models.py` | `Models` / `AsyncModels` | **重新实现** generate_content，调用 `client.request()` 私有 API | 604 |
| `agent/interactions.py` | `InteractionsResource` / `AsyncInteractionsResource` | 包装 interactions API | 376 |
| `agent/types.py` | 各种 dataclass | 重新定义 SDK 类型（Content, Part, GenerateContentConfig 等） | 333 |
| `client_pool.py` | `GeminiClientPool` | 单例连接池，线程安全缓存 | ~200 |
| `common/official_sdk_adapter.py` | `OfficialSDKAdapter` | 消息格式转换 + 从池获取 client | 411 |
| `common/sdk_initializer.py` | `SDKInitializer` | 懒加载 + 从池获取 client | 123 |
| `genai_agent/client.py` | `get_genai_client()` | 薄代理，转发到 pool | 60 |

### 2.3 问题详细分析

#### 问题 A：包装层被大面积绕过（21 处）

以下位置通过 `getattr(x, "_genai_client", x)` 或 `hasattr` + 直接访问 `_genai_client` 来绕过包装层：

```
vertexai/vertex_edit_base.py:127         ← getattr hack
vertexai/video_generation_service.py:118 ← getattr hack
vertexai/video_understanding_service.py:84 ← getattr hack
vertexai/imagen_vertex_ai.py:130         ← getattr hack
vertexai/tryon_service.py:90             ← getattr hack
vertexai/expand_service.py:215-219       ← hasattr + _genai_client (2处)
vertexai/segmentation_service.py:213-217 ← hasattr + _genai_client (2处)
geminiapi/video_generation_service.py:93 ← getattr hack
geminiapi/video_understanding_service.py:71 ← getattr hack
coordinators/video_generation_coordinator.py:178 ← getattr hack
common/sdk_initializer.py:51,77,89,113   ← 内部 _genai_client 属性 (4处)
genai_agent/service.py:9,55,108          ← get_genai_client 调用 (3处)
```

**影响**：
- 依赖 `_genai_client` 私有属性名，SDK 内部重构即断裂
- 包装层的 `Models`、`InteractionsResource` 对这些调用者完全无用
- 代码意图不清晰：看到 `pool.get_client()` 以为用的是包装器，实际用的是裸 client

#### 问题 B：agent/models.py 重新实现了 SDK 内部调用

`agent/models.py` 的 `Models.generate_content()` 并非委托给 `genai.Client.models.generate_content()`，
而是**自己构建 HTTP 请求**：

```python
# agent/models.py
response = self._api_client.request('post', path, request_dict, http_options)
```

`client.request()` 是 `google.genai.Client` 的**内部/私有方法**，不属于公开 API。

**风险**：
- `google-genai` SDK 升级后该方法签名可能变更（无兼容性保证）
- 自行实现的 Vertex/MLDev 路径转换逻辑可能与官方 SDK 出现偏差
- `agent/types.py` 中重新定义的 `GenerateContentResponse` 等类型与官方类型不完全一致

#### 问题 C：4 条 Client 获取路径语义重叠

| 路径 | 入口 | 最终目标 | 额外逻辑 |
|------|------|----------|----------|
| A | `get_client_pool().get_client()` | pool 缓存 | 无 |
| B | `OfficialSDKAdapter(...)._get_client()` | pool 缓存 | 消息格式转换 |
| C | `SDKInitializer().ensure_initialized()` → `.client` | pool 缓存 | 懒加载标记 |
| D | `get_genai_client(api_key)` | pool 缓存 | 仅日志 |

四条路径最终都到同一个 `GeminiClientPool`，但入口不同导致：
- 新开发者不确定该用哪个
- 已有代码中用法不统一，无法 grep 出一致的调用模式

#### 问题 D：OfficialSDKAdapter 单一调用者

`OfficialSDKAdapter` 仅被 `google_service.py` 使用，且其核心逻辑只有：
1. 从池获取 client
2. 转换消息格式（`_convert_messages_to_contents`）
3. 调用 `client.models.generate_content`
4. 转换响应格式（`_convert_response_to_dict`）

对于单一调用者，独立 Adapter 类增加了间接层但没有复用价值。

#### 问题 E：前端 `@google/genai` 声明但未使用

`package.json` 中声明了 `"@google/genai": "^1.32.0"`，但前端 `frontend/**/*.{ts,tsx}` 中
**无任何 import 引用**。属于幽灵依赖，增加 `node_modules` 体积和供应链攻击面。

---

## 3. 修复方案

### 阶段 1：消除 `_genai_client` 绕过（低风险，高收益）

**目标**：让 `GeminiClientPool.get_client()` 在 Vertex AI 模式下也直接返回 `google.genai.Client`（而非 `agent/client.py` 包装器），与 Gemini API 模式行为一致。

**改动清单**：

1. **修改 `client_pool.py`**（核心变更）
   - `vertexai=True` 分支：将 `vertexai.init()` + credential 解析逻辑从 `agent/client.py` 搬入池内
   - 直接创建 `google_genai.Client(vertexai=True, project=..., location=..., credentials=...)`
   - 不再使用 `VertexAIClient` 包装器
   - 返回类型统一为 `google.genai.Client`

2. **删除 12 处 `getattr(x, "_genai_client", x)` hack**
   - 涉及文件见上文 §2.3 问题 A 列表
   - 由于池已直接返回原生 client，这些 getattr 不再需要
   - 每处改为直接使用 `pool.get_client()` 返回值

3. **验证方式**
   - 全局搜索 `_genai_client` 确认零引用（`agent/client.py` 自身除外，该文件后续阶段删除）
   - 对 Vertex AI 服务逐一验证：edit_image、generate_video、virtual_tryon、segmentation、expand

**风险评估**：低。这些服务已经在绕过包装层用原生 client，本阶段只是让"绕过"变为"正道"。

---

### 阶段 2：收敛 Client 获取路径为 1 条（中风险）

**目标**：统一为 `get_client_pool().get_client()` 一条路径。

**改动清单**：

1. **内联并删除 `genai_agent/client.py`**
   - `get_genai_client()` 只是 `pool.get_client()` 的薄代理
   - 将 3 个调用点（`genai_agent/service.py:9,55,108`）改为直接调 pool
   - `clear_client_pool()` 迁移至 `client_pool.py` 或删除（确认使用情况）

2. **内联并删除 `common/sdk_initializer.py`**（123 行）
   - `SDKInitializer` 的懒加载语义由调用者自行管理（池本身已是懒创建）
   - 将 `ChatHandler` 等使用者改为直接调 pool
   - `ensure_initialized()` 的参数校验逻辑移入调用者或池内

3. **内联 `OfficialSDKAdapter` 到 `google_service.py`**（411 行）
   - 将 `_convert_messages_to_contents()`、`_build_generation_config()`、`_convert_response_to_dict()` 三个方法移为 `GoogleService` 的私有方法
   - 删除 `common/official_sdk_adapter.py`
   - `GoogleService.__init__` 中去掉 adapter 创建

4. **更新 `__init__.py` 导出**
   - `backend/app/services/gemini/__init__.py` 中移除对已删除模块的导出

**改动后的获取路径**：

```
所有调用者 → get_client_pool().get_client(api_key=..., vertexai=..., ...)
              │
              └─ 返回 google.genai.Client（无论哪种模式）
```

**风险评估**：中。涉及较多文件的 import 路径变更，需逐一确认。

---

### 阶段 3：处理 `agent/` 目录的重新实现（高风险，需分步）

**目标**：去除 `agent/models.py`、`agent/interactions.py`、`agent/types.py` 中对 SDK 私有 API 的依赖。

**注意**：`agent/` 目录下还有大量 ADK (Agent Development Kit) 相关文件（adk_*.py、agent_*.py、workflows/ 等），这些**不在本次重构范围内**。本阶段仅涉及 SDK 包装层文件：`client.py`、`models.py`、`interactions.py`、`types.py`、`common.py`。

**分析**：`agent/` 目录下的 SDK 包装模块是从 Google 官方 SDK 源码 fork 出来的（文件头有 Google LLC 版权声明），对 SDK 内部的 `client.request()` / `client.request_streamed()` 有深度依赖。

**子步骤**：

#### 3a. 评估 `agent/models.py` 的必要性（604 行）

需要回答：**为什么不直接用 `genai.Client.models.generate_content()`？**

可能的原因（需验证）：
- 自定义的请求/响应转换逻辑（`_GenerateContentParameters_to_vertex` 等）
- 自定义的类型系统（`agent/types.py` 中的 dataclass）
- 某些功能在当时的 SDK 版本中不可用，需要自行实现

**验证方法**：
- 对比 `agent/types.py` 中的类型定义与 `google.genai.types` 的差异
- 对比 `agent/models.py` 的 generate_content 与 `genai.Client.models.generate_content` 的参数/返回值差异
- 确认当前 SDK 版本（`>=1.55.0`）是否已覆盖所有需要的功能

#### 3b. 迁移 `agent/interactions.py`（376 行）

`InteractionsResource` 和 `AsyncInteractionsResource` 包装了 Interactions API（Deep Research 等）。

**需验证**：
- 官方 `genai.Client` 是否已有 `.interactions` 属性
- 如果有，确认 `interactions_manager.py` 能否直接使用官方接口

**预期结果**：
- 如果官方 SDK 已完全覆盖 → 删除 `agent/interactions.py`，改用 `client.interactions`
- 如果有差异 → 保留最小包装，仅覆盖差异部分

#### 3c. 清理 `agent/types.py`（333 行）

`agent/types.py` 重新定义了 `Content`、`Part`、`GenerateContentConfig`、`GenerateContentResponse` 等类型。

**改动方向**：
- 逐步将各调用点的 `from ..agent.types import X` 替换为 `from google.genai.types import X`
- 对于官方 SDK 中不存在的自定义类型（如 `HttpOptions`、`HttpRetryOptions`），保留在一个精简的 `types.py` 中
- 删除与官方 SDK 重复的类型定义

**风险评估**：高。`agent/types.py` 被大量文件引用，类型签名可能与官方 SDK 有细微差异（字段名、可选性等），需逐个比对。建议按模块分批迁移。

---

### 阶段 4：清理前端幽灵依赖（无风险）

**改动**：
- 从 `package.json` 中移除 `"@google/genai": "^1.32.0"`
- 运行 `npm install` 更新 lock 文件
- 确认无编译错误

---

## 4. 执行顺序与依赖关系

```
阶段 4（前端清理）─── 可独立执行，无依赖
          │
阶段 1（消除 getattr hack）
          │
          ▼
阶段 2（收敛获取路径）
          │
          ▼
阶段 3a（评估 agent/models.py）
          │
     ┌────┴────┐
     ▼         ▼
阶段 3b     阶段 3c
(interactions) (types)
```

**建议**：每个阶段独立提交，通过测试后再进入下一阶段。

---

## 5. 每阶段涉及文件清单

### 阶段 1 涉及文件（~12 个）

| 文件 | 操作 |
|------|------|
| `gemini/client_pool.py` | 修改：Vertex AI 分支直接创建原生 Client |
| `gemini/vertexai/vertex_edit_base.py` | 修改：去掉 getattr hack |
| `gemini/vertexai/video_generation_service.py` | 修改：去掉 getattr hack |
| `gemini/vertexai/video_understanding_service.py` | 修改：去掉 getattr hack |
| `gemini/vertexai/imagen_vertex_ai.py` | 修改：去掉 getattr hack |
| `gemini/vertexai/tryon_service.py` | 修改：去掉 getattr hack |
| `gemini/vertexai/expand_service.py` | 修改：去掉 getattr hack (2处 hasattr) |
| `gemini/vertexai/segmentation_service.py` | 修改：去掉 getattr hack (2处 hasattr) |
| `gemini/geminiapi/video_generation_service.py` | 修改：去掉 getattr hack |
| `gemini/geminiapi/video_understanding_service.py` | 修改：去掉 getattr hack |
| `gemini/coordinators/video_generation_coordinator.py` | 修改：去掉 getattr hack |

### 阶段 2 涉及文件（~8 个）

| 文件 | 操作 |
|------|------|
| `gemini/genai_agent/client.py` (60行) | 删除 |
| `gemini/genai_agent/service.py` | 修改：改为直接调 pool |
| `gemini/common/sdk_initializer.py` (123行) | 删除 |
| `gemini/common/chat_handler.py` | 修改：去掉 SDKInitializer 依赖 |
| `gemini/common/official_sdk_adapter.py` (411行) | 删除 |
| `gemini/google_service.py` | 修改：内联 adapter 逻辑 |
| `gemini/__init__.py` | 修改：更新导出 |
| `common/interactions_manager.py` | 审查：确认不受影响 |

### 阶段 3 涉及文件（待评估后确定）

| 文件 | 操作 |
|------|------|
| `gemini/agent/client.py` (408行) | 待定：可能删除或大幅简化 |
| `gemini/agent/models.py` (604行) | 待定：可能删除，改用官方 SDK |
| `gemini/agent/interactions.py` (376行) | 待定：可能删除，改用官方 SDK |
| `gemini/agent/types.py` (333行) | 待定：保留不重复部分，删除其余 |
| `gemini/agent/common.py` | 待定：随 models.py 一起处理 |
| 所有 `from ..agent.types import` 的文件 | 修改：改为 `from google.genai.types import` |

**注意**：`agent/` 目录下的 ADK 相关文件（adk_*.py、agent_*.py、workflows/ 等）不在本次重构范围内。

### 阶段 4 涉及文件（1 个）

| 文件 | 操作 |
|------|------|
| `package.json` | 修改：移除 `@google/genai` |

---

## 6. 验证计划

### 每阶段通用验证

```bash
# 后端启动验证
cd backend && .venv/bin/python3 -c "from app.services.gemini.google_service import GoogleService; print('OK')"

# 后端 lint
cd backend && .venv/bin/python3 -m ruff check app/services/gemini/
```

### 阶段 1 专项验证

```bash
# 确认无残留 _genai_client 绕过
grep -rn "_genai_client" backend/app/services/gemini/ \
  --include="*.py" \
  | grep -v "agent/client.py" | grep -v "__pycache__"
# 期望结果：0 行

# 确认 Vertex AI 服务可正常获取 client
python3 -c "
from backend.app.services.gemini.client_pool import get_client_pool
pool = get_client_pool()
client = pool.get_client(api_key='test', vertexai=False)
print(type(client))  # 应为 google.genai.Client
"
```

### 阶段 2 专项验证

```bash
# 确认无残留的旧路径引用
grep -rn "SDKInitializer\|OfficialSDKAdapter\|get_genai_client" \
  backend/app/services/ --include="*.py" | grep -v "__pycache__"
# 期望结果：0 行
```

### 阶段 3 专项验证

```bash
# 对比官方 SDK 类型
python3 -c "
from google.genai import types
print(dir(types))
# 对比 agent/types.py 中定义的类型是否全部可用
"

# 确认 interactions API 可用性
python3 -c "
from google import genai
client = genai.Client(api_key='test')
print(hasattr(client, 'interactions'))
"
```

---

## 7. 回滚策略

每个阶段独立 commit，出现问题可 `git revert` 单个阶段。

- 阶段 1 回滚：恢复 getattr hack + client_pool.py 的 VertexAIClient 分支
- 阶段 2 回滚：恢复被删除的 3 个文件 + import 路径
- 阶段 3 回滚：恢复 agent/ 目录下的 SDK 包装文件 + import 路径
- 阶段 4 回滚：恢复 package.json 的 `@google/genai` 条目

---

## 8. 预期最终架构

```
调用者（所有 service）
    │
    └─ get_client_pool().get_client(api_key=..., vertexai=..., ...)
            │
            ▼
    GeminiClientPool（单例连接池）
        ├─ vertexai=False → google.genai.Client(api_key=...)
        └─ vertexai=True  → google.genai.Client(vertexai=True, project=..., ...)
                                │
                                ├─ .models.generate_content()     ← 官方 API
                                ├─ .models.generate_content_stream() ← 官方 API
                                └─ .interactions.create()          ← 官方 API
```

**消除的 SDK 包装文件**（~2315 行）：
- `agent/client.py`（408 行）→ 删除，逻辑内联到 pool
- `agent/models.py`（604 行）→ 删除，使用官方 SDK
- `agent/interactions.py`（376 行）→ 删除或大幅简化
- `agent/types.py`（333 行）→ 仅保留官方 SDK 未覆盖的自定义类型
- `common/official_sdk_adapter.py`（411 行）→ 内联到 GoogleService
- `common/sdk_initializer.py`（123 行）→ 删除
- `genai_agent/client.py`（60 行）→ 删除

**净效果**：
- Client 获取路径：4 条 → 1 条
- 包装层数：4 层 → 1 层（池）
- 对 SDK 私有 API 的依赖：`client.request()` + `_genai_client` → 零
- 删除代码量：~2300 行

---

## 9. 跨 Provider 连接池分析

### 9.1 各 Provider 的 Client 管理方式

| Provider | client_type | SDK | 创建方式 | 是否有池 | 生命周期 |
|----------|-------------|-----|----------|----------|----------|
| **Google** | `google` | `google-genai` | `GeminiClientPool`（单例） | **有**（显式池） | 跨请求复用 |
| **OpenAI** | `openai` | `openai` (AsyncOpenAI) | `OpenAIService.__init__` 中直接 `new` | **无** | 跟随 Service 实例 |
| **DeepSeek** | `openai` | `openai` (AsyncOpenAI) | 同上（复用 OpenAIService） | **无** | 同上 |
| **Moonshot** | `openai` | `openai` (AsyncOpenAI) | 同上 | **无** | 同上 |
| **ZhiPu** | `openai` | `openai` (AsyncOpenAI) | 同上 | **无** | 同上 |
| **Doubao** | `openai` | `openai` (AsyncOpenAI) | 同上 | **无** | 同上 |
| **Hunyuan** | `openai` | `openai` (AsyncOpenAI) | 同上 | **无** | 同上 |
| **NVIDIA** | `openai` | `openai` (AsyncOpenAI) | 同上 | **无** | 同上 |
| **OpenRouter** | `openai` | `openai` (AsyncOpenAI) | 同上 | **无** | 同上 |
| **SiliconFlow** | `openai` | `openai` (AsyncOpenAI) | 同上 | **无** | 同上 |
| **Grok** | `grok` | `openai` (AsyncOpenAI) + `httpx` | `GrokService.__init__` 中创建 | **无** | 跟随 Service 实例 |
| **Tongyi/Qwen** | `dashscope` | DashScope + `openai` | 双客户端，Service 内直接创建 | **无** | 同上 |
| **Ollama** | `ollama` | `openai` + httpx | 双客户端，Handler 内直接创建 | **无** | 同上 |
| **Custom** | `openai` | `openai` (AsyncOpenAI) | 同上 | **无** | 同上 |
| **MCP** | — | 自定义 MCPClient | `MCPSessionPool`（实例级） | **有**（会话池） | 会话级复用 |

### 9.2 结论

**推荐方案：保持 `GeminiClientPool` 仅管理 Google 系 client。**

理由：
1. **Google 是唯一需要显式池化的 provider** — 创建成本高（credential 解析 + SDK 初始化）
2. **OpenAI 系 / Grok 的 client 创建成本极低** — `AsyncOpenAI(api_key=..., base_url=...)` 是轻量配置对象
3. **各 SDK 内部已有连接池** — `httpx.AsyncClient` 内置连接池，无需应用层重复
4. **统一池会导致类型安全丧失** — 返回 Any 类型，IDE 无法提供补全

> **核心洞察**：连接池的价值在于避免重复的高成本创建。当创建成本本身就很低时（OpenAI 系、Grok），池化是负优化。

---

## 10. Shutdown 资源泄漏问题

当前 `shutdown_tasks.py` 只关闭了 Redis 和 Browser，遗漏了：
- `GeminiClientPool` 中缓存的 `google.genai.Client`（持有 HTTP transport）
- `ProviderFactory._client_cache` 中缓存的所有 Service 实例
- `MCPSessionPool` 中的 MCP 会话
- 各 `AsyncOpenAI` / `httpx.AsyncClient` 实例

**建议**：在 shutdown 流程中添加：
```python
ProviderFactory.clear_cache()
get_client_pool().close_all()
```
