# Ollama API 功能总结

本文档总结了 Ollama API 文档中每个端点的功能、主要参数和用途。

## 📋 目录

1. [文本生成类 API](#文本生成类-api)
2. [模型管理类 API](#模型管理类-api)
3. [文件管理类 API](#文件管理类-api)
4. [信息查询类 API](#信息查询类-api)
5. [其他 API](#其他-api)

---

## 文本生成类 API

### 1. POST /api/generate - 生成补全

**功能**：根据给定的提示词（prompt）生成文本响应。这是一个流式端点，支持实时返回生成的内容。

**主要参数**：
- `model` (必需): 模型名称，格式为 `model:tag`
- `prompt`: 要生成响应的提示词
- `suffix`: 模型响应后的文本（用于代码补全等场景）
- `images`: Base64 编码的图片列表（用于多模态模型如 llava）
- `format`: 返回格式，可以是 `json` 或 JSON schema（支持结构化输出）
- `options`: 模型参数（temperature、seed、top_k 等）
- `system`: 系统消息（覆盖 Modelfile 中的定义）
- `template`: 提示词模板
- `stream`: 是否流式返回（默认 true）
- `raw`: 是否绕过模板系统（true 时不应用格式化）
- `keep_alive`: 模型在内存中保持的时间（默认 5m）
- `think`: 对于思考模型，是否在响应前思考

**特殊功能**：
- ✅ 支持流式和非流式响应
- ✅ 支持 JSON 模式和结构化输出
- ✅ 支持多模态输入（图片）
- ✅ 支持代码补全（suffix 参数）
- ✅ 支持可重现输出（seed 参数）
- ✅ 支持加载/卸载模型（空 prompt 时）

**返回信息**：
- 生成的文本内容
- 性能统计（token 数量、耗时等）
- 上下文信息（用于保持对话记忆）

---

### 2. POST /api/chat - 生成聊天补全

**功能**：在聊天对话中生成下一条消息。支持多轮对话、工具调用、结构化输出等功能。

**主要参数**：
- `model` (必需): 模型名称
- `messages`: 聊天消息列表，用于保持对话记忆
- `tools`: 工具列表（JSON 格式），支持函数调用
- `think`: 对于思考模型，是否在响应前思考
- `format`: 返回格式（json 或 JSON schema）
- `options`: 模型参数
- `stream`: 是否流式返回
- `keep_alive`: 模型在内存中保持的时间

**消息对象字段**：
- `role`: 角色（system、user、assistant、tool）
- `content`: 消息内容
- `thinking`: 思考过程（思考模型）
- `images`: 图片列表（多模态模型）
- `tool_calls`: 工具调用列表
- `tool_name`: 已执行的工具名称

**特殊功能**：
- ✅ 支持多轮对话历史
- ✅ 支持工具调用（Function Calling）
- ✅ 支持结构化输出
- ✅ 支持多模态输入（图片）
- ✅ 支持可重现输出
- ✅ 支持加载/卸载模型（空 messages 时）

**与 /api/generate 的区别**：
- `/api/chat` 更适合对话场景，支持消息历史
- `/api/generate` 更适合单次生成任务

---

## 模型管理类 API

### 3. POST /api/create - 创建模型

**功能**：创建新模型，可以从现有模型、Safetensors 目录或 GGUF 文件创建。

**主要参数**：
- `model`: 要创建的模型名称
- `from`: 源模型名称（从现有模型创建时）
- `files`: 文件字典（文件名到 SHA256 摘要的映射），用于从 GGUF 或 Safetensors 创建
- `adapters`: LORA 适配器文件字典
- `template`: 提示词模板
- `license`: 许可证信息
- `system`: 系统提示词
- `parameters`: 模型参数字典
- `messages`: 用于创建对话的消息列表
- `stream`: 是否流式返回
- `quantize`: 量化类型（q4_K_M、q4_K_S、q8_0 等）

**支持的创建方式**：
1. 从现有模型创建（通过 `from` 参数）
2. 从 GGUF 文件创建（通过 `files` 参数）
3. 从 Safetensors 目录创建（通过 `files` 参数）
4. 量化模型（通过 `quantize` 参数）

**返回**：流式状态更新，最终返回 `{"status":"success"}`

---

### 4. POST /api/copy - 复制模型

**功能**：复制一个模型，创建具有新名称的副本。

**主要参数**：
- `source`: 源模型名称
- `destination`: 目标模型名称

**返回**：200 OK（成功）或 404 Not Found（源模型不存在）

---

### 5. DELETE /api/delete - 删除模型

**功能**：删除模型及其数据。

**主要参数**：
- `model`: 要删除的模型名称

**返回**：200 OK（成功）或 404 Not Found（模型不存在）

---

### 6. POST /api/pull - 拉取模型

**功能**：从 Ollama 模型库下载模型。支持断点续传，多个请求共享下载进度。

**主要参数**：
- `model`: 要拉取的模型名称
- `insecure`: 是否允许不安全连接（仅开发环境使用）
- `stream`: 是否流式返回进度

**返回**：
- 流式模式：返回下载进度状态（pulling manifest、pulling digest、verifying、writing manifest、success）
- 非流式模式：单个 JSON 对象 `{"status":"success"}`

---

### 7. POST /api/push - 推送模型

**功能**：将模型上传到模型库。需要先在 ollama.ai 注册并添加公钥。

**主要参数**：
- `model`: 模型名称，格式为 `<namespace>/<model>:<tag>`
- `insecure`: 是否允许不安全连接（仅开发环境使用）
- `stream`: 是否流式返回进度

**返回**：
- 流式模式：返回上传进度状态（retrieving manifest、starting upload、pushing manifest、success）
- 非流式模式：单个 JSON 对象 `{"status":"success"}`

---

## 文件管理类 API

### 8. HEAD /api/blobs/:digest - 检查 Blob 是否存在

**功能**：检查文件 Blob（二进制大对象）是否存在于服务器上。用于创建模型前的验证。

**查询参数**：
- `digest`: Blob 的 SHA256 摘要

**返回**：
- 200 OK：Blob 存在
- 404 Not Found：Blob 不存在

---

### 9. POST /api/blobs/:digest - 推送 Blob

**功能**：将文件推送到 Ollama 服务器以创建 Blob。在从 GGUF 或 Safetensors 创建模型前需要先推送文件。

**查询参数**：
- `digest`: 文件的预期 SHA256 摘要

**请求体**：文件内容（二进制）

**返回**：
- 201 Created：Blob 创建成功
- 400 Bad Request：摘要不匹配

---

## 信息查询类 API

### 10. GET /api/tags - 列出本地模型

**功能**：列出本地可用的所有模型。

**返回**：JSON 对象，包含模型列表，每个模型包含：
- `name`: 模型名称
- `model`: 模型标识符
- `modified_at`: 修改时间
- `size`: 模型大小（字节）
- `digest`: 摘要
- `details`: 详细信息（格式、家族、参数量、量化级别等）

---

### 11. POST /api/show - 显示模型信息

**功能**：显示模型的详细信息，包括 Modelfile、模板、参数、许可证、系统提示词等。

**主要参数**：
- `model`: 要查询的模型名称
- `verbose`: 是否返回详细数据（true 时返回完整的 tokenizer 信息等）

**返回信息**：
- `modelfile`: Modelfile 内容
- `parameters`: 参数字符串
- `template`: 提示词模板
- `details`: 模型详情（格式、家族、参数量、量化级别）
- `model_info`: 模型架构信息（层数、注意力头数、词汇表大小等）
- `capabilities`: 模型能力（completion、vision 等）

---

### 12. GET /api/ps - 列出运行中的模型

**功能**：列出当前已加载到内存中的模型。

**返回**：JSON 对象，包含运行中的模型列表，每个模型包含：
- `name`: 模型名称
- `model`: 模型标识符
- `size`: 模型大小
- `digest`: 摘要
- `details`: 详细信息
- `expires_at`: 过期时间
- `size_vram`: VRAM 中的大小

---

### 13. POST /api/embed - 生成嵌入向量

**功能**：从模型生成文本的嵌入向量（embedding）。

**主要参数**：
- `model`: 用于生成嵌入向量的模型名称
- `input`: 要生成嵌入向量的文本或文本列表
- `truncate`: 是否截断超出上下文长度的输入（默认 true）
- `options`: 模型参数
- `keep_alive`: 模型在内存中保持的时间
- `dimensions`: 嵌入向量的维度数

**返回**：
- `model`: 使用的模型
- `embeddings`: 嵌入向量数组（每个输入对应一个向量）
- `total_duration`: 总耗时
- `load_duration`: 加载耗时
- `prompt_eval_count`: 提示词 token 数

**支持**：单个文本或文本列表批量生成

---

### 14. POST /api/embeddings - 生成嵌入向量（已废弃）

**功能**：生成嵌入向量（旧版 API，已被 `/api/embed` 取代）。

**主要参数**：
- `model`: 模型名称
- `prompt`: 要生成嵌入向量的文本
- `options`: 模型参数
- `keep_alive`: 模型在内存中保持的时间

**注意**：此端点已被 `/api/embed` 取代，建议使用新 API。

---

### 15. GET /api/version - 获取版本

**功能**：获取 Ollama 服务器版本号。

**返回**：JSON 对象，包含 `version` 字段（如 `"0.5.1"`）

---

## 其他 API

### 模型命名规范

模型名称遵循 `model:tag` 格式：
- `model` 可以包含可选的命名空间，如 `example/model`
- `tag` 用于标识特定版本，可选，默认为 `latest`
- 示例：`orca-mini:3b-q8_0`、`llama3:70b`

### 流式响应

以下端点支持流式响应（可通过 `stream: false` 禁用）：
- `/api/generate`
- `/api/chat`
- `/api/create`
- `/api/pull`
- `/api/push`

### 持续时间单位

所有持续时间都以**纳秒**为单位返回。

---

## 功能分类总结

### 🔤 文本生成
- `/api/generate` - 单次文本生成
- `/api/chat` - 对话式生成

### 📦 模型管理
- `/api/create` - 创建模型
- `/api/copy` - 复制模型
- `/api/delete` - 删除模型
- `/api/pull` - 下载模型
- `/api/push` - 上传模型

### 📁 文件管理
- `HEAD /api/blobs/:digest` - 检查文件
- `POST /api/blobs/:digest` - 上传文件

### 🔍 信息查询
- `/api/tags` - 列出本地模型
- `/api/show` - 模型详情
- `/api/ps` - 运行中的模型
- `/api/version` - 版本信息

### 🧮 向量生成
- `/api/embed` - 生成嵌入向量（推荐）
- `/api/embeddings` - 生成嵌入向量（已废弃）

---

## 使用建议

1. **对话场景**：使用 `/api/chat`，支持消息历史和工具调用
2. **单次生成**：使用 `/api/generate`，更轻量
3. **模型管理**：先 `pull` 下载，再 `show` 查看信息，需要时 `copy` 备份
4. **自定义模型**：先 `push` 文件到 blob，再 `create` 创建模型
5. **嵌入向量**：使用 `/api/embed`（新 API），支持批量处理

---

*最后更新：基于 Ollama API 文档 v0.5.1*


