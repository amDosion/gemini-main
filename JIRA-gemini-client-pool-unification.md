# JIRA: Gemini / Vertex AI Client Pool 统一治理

## 类型
Tech Debt / Reliability / Runtime Architecture

## 状态
Ready for Implementation

## 背景
项目已经存在统一连接池 `GeminiClientPool`，用于缓存和复用 `google.genai.Client`，并区分 Gemini Developer API 与 Vertex AI 两条认证路径。但当前代码中仍有部分服务直接 `genai.Client(...)`，同时也有一些服务自己保存 `_client`。需要梳理并统一：主运行链路必须走统一池；确实需要一次性验证的配置接口可以保留直接 client，但要明确边界和生命周期。

这项工作与近期 `image-chat-edit` 错误有关：Chat Edit 应该走 Gemini API，但因为路由参数被 Vertex 配置污染，前端传入的 `gemini-3.1-flash-image-preview` 被送到了 Vertex publisher model 路径，出现 `Publisher Model ... was not found`。该问题的直接根因是路由串路，不是连接池本身；但连接池治理可以降低后续 API 路径混乱风险。

## 当前事实
- 统一池存在于 `backend/app/services/gemini/client_pool.py`。
- `GeminiClientPool` 是单例，内部缓存 `google.genai.Client`。
- 缓存 key 由 `api_key / vertexai / project / location / credentials / http_options` 组成。
- 主 Gemini / Vertex 生成编辑链路多数已经走池。
- 仓库当前仍有若干直接 `genai.Client(...)` 调用点。

## 证据链

### 统一池实现
- `backend/app/services/gemini/client_pool.py`
  - `GeminiClientPool.__new__()` 实现进程内单例。
  - `get_client()` 统一创建 Gemini API 和 Vertex AI client。
  - `vertexai=False` 时显式传 `google_genai.Client(vertexai=False, api_key=...)`。
  - `vertexai=True` 时传 `google_genai.Client(vertexai=True, project=..., location=..., credentials=...)`。
  - `_generate_cache_key()` 按 API key / credentials / project / location / http options 做缓存隔离。
  - `close_all() / list_clients() / get_stats()` 已存在，但目前没有统一运维入口暴露。

### 已走统一池的主要链路
- `backend/app/services/gemini/common/chat_handler.py`
- `backend/app/services/gemini/common/file_handler.py`
- `backend/app/services/gemini/common/token_handler.py`
- `backend/app/services/gemini/common/pdf_extractor.py`
- `backend/app/services/gemini/geminiapi/imagen_gemini_api.py`
- `backend/app/services/gemini/geminiapi/conversational_image_edit_service.py`
- `backend/app/services/gemini/geminiapi/recontext_image_service.py`
- `backend/app/services/gemini/geminiapi/video_generation_service.py`
- `backend/app/services/gemini/vertexai/vertex_edit_base.py`
- `backend/app/services/gemini/vertexai/expand_service.py`
- `backend/app/services/gemini/vertexai/segmentation_service.py`
- `backend/app/services/gemini/vertexai/tryon_service.py`
- `backend/app/services/gemini/vertexai/video_generation_service.py`
- `backend/app/services/gemini/google_service.py`

### 需要治理的直接 client 创建点
- `backend/app/services/gemini/agent/client.py`
  - 当前直接 `genai.Client(**client_kwargs)`。
  - 如果 Agent runtime 仍是生产链路，应改为 `get_client_pool().get_client(...)`。
- `backend/app/routers/models/vertex_ai_config.py`
  - `/verify-vertex-ai` 当前直接 `genai.Client(...)`。
  - 这是验证用户尚未保存凭证的接口，可以保留直接 client，但需要明确为一次性验证路径，并在可能时关闭 client。
- `backend/app/routers/system/file_search.py`
  - 两处直接 `genai.Client(api_key=api_key)`。
  - 应改为统一池，使用 Bearer API key 作为池 key。
- `backend/app/services/common/embedding_service.py`
  - `get_embedding()` 每次调用直接 `genai.Client(api_key=api_key)`。
  - 这是最明显的重复创建点，应优先改为统一池。
- `backend/app/services/gemini/geminiapi/main.py`
  - 独立 FastAPI app startup 中直接创建 `genai.Client(...)`。
  - 需要确认是否仍挂载到主服务；若是运行链路，改池；若是 standalone demo，标注或迁入 deprecated。

## 问题陈述
当前代码没有形成“所有运行时 Gemini / Vertex API 请求必须通过统一池”的强约束。直接创建 client 会带来：
- 连接复用不一致。
- timeout / retry / HTTP options 不一致。
- Gemini API 与 Vertex AI 路由边界更容易串。
- 难以观测当前活跃 client 数、cache hit rate 和实际 API 模式。
- 凭证切换后可能出现服务各自缓存状态不一致。

## 用户故事
1. 作为后端维护者，我希望所有运行时 Gemini / Vertex API 请求统一通过 `GeminiClientPool`，避免服务各自创建 SDK client。
2. 作为调试者，我希望能快速确认当前请求使用的是 Gemini API 还是 Vertex AI，以及命中的是哪个 pool key。
3. 作为用户，我希望 Chat Edit 固定走 Gemini API，Mask / Background / Expand / Vertex Video 固定走 Vertex AI，不因全局配置互相污染。
4. 作为系统管理员，我希望配置验证接口可以验证临时凭证，但不会污染长期运行的 client pool。

## 修复范围
- 把 `embedding_service.get_embedding()` 改为使用 `get_client_pool().get_client(api_key=..., vertexai=False)`。
- 把 `routers/system/file_search.py` 两处 `genai.Client(api_key=...)` 改为统一池。
- 评估并改造 `gemini/agent/client.py`：
  - 若该兼容层仍被运行时使用，则改为从池中获取 `google.genai.Client`。
  - 保留其 `AsyncClient / Models` 包装层，但底层 client 来自池。
- 梳理 `geminiapi/main.py`：
  - 若是 standalone / legacy app，增加注释和文档说明，不纳入主服务池治理。
  - 若主服务仍使用，改成 `get_client_pool()`。
- 对 `vertex_ai_config.py` 的 `/verify-vertex-ai` 做边界处理：
  - 可以保留直接 client，因为它验证“尚未保存”的凭证。
  - 需要补充注释：此路径不得作为业务生成路径复用。
  - 如 SDK 支持 close，则请求结束后关闭。
- 增加或完善测试，防止新增直接 `genai.Client(...)` 进入主运行链路。

## 非目标
- 不改变前端传入模型 ID 的语义。
- 不把 `image-chat-edit` 默认模型替换为其他模型。
- 不把所有模式强行切到 Vertex AI。
- 不移除 Vertex AI 专用模式。
- 不重构业务服务的整体职责边界。
- 不处理 `httpx.AsyncClient` 的普通文件下载连接池问题，除非它直接影响 Gemini SDK client。

## 目标路由边界
- Gemini API 路径：
  - `chat`
  - `image-chat-edit`
  - Gemini API image generation / native Gemini image edit
  - file search / embeddings if using API key
- Vertex AI 路径：
  - `image-mask-edit`
  - `image-background-edit`
  - `image-outpainting` / expand
  - `image-segmentation`
  - `virtual-try-on`
  - Vertex video generation / extension
  - Recontext/Product Recontext only when产品定义要求走 Vertex Gemini image，并且配置明确

## 验收标准
- 主运行链路中不再出现新增的直接 `genai.Client(...)`。
- `embedding_service.get_embedding()` 通过 `GeminiClientPool` 获取 client。
- `file_search.py` 通过 `GeminiClientPool` 获取 client。
- `agent/client.py` 若仍在运行链路，则底层 client 通过 `GeminiClientPool` 获取。
- `/verify-vertex-ai` 保留直接 client 时有明确注释和测试覆盖，证明它是一次性配置验证路径。
- `image-chat-edit` 在 Vertex AI 配置开启时仍传 `use_vertex=False` 到 conversational image service。
- 前端传入的 model ID 必须原样传到 Chat Edit 后端服务，不在后端替换。
- `image-mask-edit` / `image-background-edit` 仍拒绝 Gemini image 模型，必须走 Vertex Imagen edit 模型。
- 连接池统计可以在单元测试中证明相同配置复用同一 client，不同 Gemini API / Vertex 配置隔离。

## 建议实现步骤
1. 新增测试：`embedding_service` 使用池而不是直接创建 client。
2. 修改 `embedding_service.py`，引入 `get_client_pool()`。
3. 新增测试：`file_search` 使用池，并传入 Bearer token 作为 `api_key`。
4. 修改 `routers/system/file_search.py`。
5. 检查 `agent/client.py` 的调用来源。
6. 若 `agent/client.py` 是运行链路，增加测试并改造为池。
7. 对 `/verify-vertex-ai` 增加注释或测试，确认其直接 client 是有意的一次性验证。
8. 增加静态扫描测试：
   - 允许列表：`client_pool.py`、`vertex_ai_config.py`、legacy/standalone 文件。
   - 其他主运行链路禁止直接 `genai.Client(`。
9. 跑相关后端测试。

## 推荐测试命令
```bash
cd /mnt/user/appdata/gemini-main/backend
.venv/bin/python -m pytest tests/test_google_vertex_model_deprecations.py -q
.venv/bin/python -m pytest tests -q
```

如新增专门测试文件，建议命名：
```bash
backend/tests/test_gemini_client_pool_usage.py
```

## 建议新增测试点
- `test_embedding_service_uses_client_pool`
- `test_file_search_uses_client_pool_for_api_key`
- `test_agent_client_uses_client_pool_when_constructing_google_genai_client`
- `test_chat_edit_keeps_frontend_model_and_forces_gemini_api_pool`
- `test_direct_genai_client_creation_is_allowlisted_only`

## 风险
- `agent/client.py` 可能是兼容层，内部 `AsyncClient` / `Models` 包装依赖直接 client 构造顺序，改池时需要小心保持 public API。
- `vertex_ai_config.py` 验证接口使用用户临时 credentials，直接纳入全局池可能造成大量一次性 pool key 或凭证生命周期问题；建议暂不纳入长期池。
- 如果 pool key 使用 credentials 的 `repr()`，同一 service account 但不同 credentials 对象可能导致复用不稳定；当前实现优先使用 `service_account_email`，基本可接受。
- 修改连接池路径可能影响 timeout/retry 行为，需要对长任务如视频生成单独确认 `http_options` 没丢。

## 交接备注
当前已知的 chat-edit 串 Vertex 问题已通过路由修复处理：`image-chat-edit` 应强制 `use_vertex=False`，并保持前端传入 model 不变。切换 CLI 后不要再尝试把 `gemini-3.1-flash-image-preview` 替换成 `gemini-2.5-flash-image`，这不是本 Jira 的目标。
