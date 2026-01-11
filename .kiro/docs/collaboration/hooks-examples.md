# Claude Agent Hooks 实战示例

本文档提供针对本项目（多模态 AI 应用框架）的 Claude Agent Hooks 实战示例。每个示例包含触发类型、目标模式和完整的 Hook 指令。

---

## 📚 目录

- [通用安全和质量检查](#通用安全和质量检查)
- [AI 提供商相关 Hooks](#ai-提供商相关-hooks)
- [前后端协同 Hooks](#前后端协同-hooks)
- [测试和文档 Hooks](#测试和文档-hooks)
- [MCP 集成示例](#mcp-集成示例)
- [项目特定工作流](#项目特定工作流)

---

## 通用安全和质量检查

### 1. 提交前安全扫描器

**用途**：防止敏感信息（API 密钥、令牌、凭证）被提交到版本控制系统。

**触发类型**：Agent Stop（提交前）

**目标文件**：所有文件

**Agent 指令**：

```markdown
审查即将提交的文件，检查潜在的安全问题：

1. **API 密钥和令牌检测**：
   - Google Cloud API 密钥（GOOGLE_API_KEY, GCP_SERVICE_ACCOUNT）
   - OpenAI API 密钥（OPENAI_API_KEY）
   - 阿里云密钥（DASHSCOPE_API_KEY, ALIBABA_CLOUD_ACCESS_KEY）
   - JWT Secret（JWT_SECRET_KEY）
   - 数据库凭证（DATABASE_URL with password）

2. **配置文件检查**：
   - `.env` 文件中的实际密钥值
   - `backend/app/core/config.py` 中的硬编码凭证
   - 前端服务中的 API 密钥（`frontend/services/providers/*`）

3. **敏感数据模式**：
   - 正则匹配：`(api[_-]?key|token|secret|password)\s*=\s*['"]\w{20,}['"]`
   - Base64 编码的凭证
   - 私钥文件（.pem, .key）

4. **内部信息泄露**：
   - 内网 IP 地址（192.168.x.x, 10.x.x.x）
   - 数据库连接字符串（含密码）
   - 内部服务 URL

**响应格式**：
- 如果发现问题：列出文件路径、行号和具体问题
- 建议：使用环境变量、密钥管理服务、加密存储
- 阻止提交并提供修复指导

**安全级别**：🔴 高危 - 必须修复后才能提交
```

**配置示例**：

```json
{
  "hooks": {
    "before_commit": [
      {
        "name": "security_scanner",
        "description": "Scan for security vulnerabilities before commit",
        "trigger": "agent_stop",
        "agent_prompt": "审查即将提交的文件，检查潜在的安全问题...",
        "enabled": true,
        "blocking": true
      }
    ]
  }
}
```

---

### 2. 代码质量门禁

**用途**：确保代码符合项目质量标准。

**触发类型**：File Save

**目标文件**：`backend/**/*.py`, `frontend/**/*.{ts,tsx}`

**Agent 指令**：

```markdown
对保存的文件执行质量检查：

**后端 Python 代码**：
1. 检查类型注解完整性（函数参数和返回值）
2. 验证文档字符串（Docstring）是否存在
3. 检查是否有未处理的异常
4. 扫描潜在的 SQL 注入风险（使用原始 SQL 的地方）
5. 验证日志记录是否适当（关键操作需要日志）

**前端 TypeScript 代码**：
1. 检查 React Hooks 使用规范
2. 验证 Props 类型定义完整性
3. 检查是否有未使用的导入
4. 扫描潜在的 XSS 风险（dangerouslySetInnerHTML）
5. 验证错误边界处理

**特定于本项目**：
- AI 提供商服务类必须实现 `BaseProviderService` 接口
- 新增 API 路由必须包含认证装饰器
- 图像处理功能必须验证文件大小和格式
- 流式响应必须正确处理错误和取消

如果发现问题，提供：
1. 问题描述和位置
2. 严重程度评估（高/中/低）
3. 修复建议和代码示例
```

---

## AI 提供商相关 Hooks

### 3. 提供商配置验证器

**用途**：确保新增 AI 提供商遵循项目架构模式。

**触发类型**：File Save

**目标文件**：`backend/app/services/**/*_service.py`, `frontend/services/providers/**/*.ts`

**Agent 指令**：

```markdown
验证 AI 提供商实现的正确性：

**后端服务检查**：
1. **接口实现验证**：
   - 必须继承自 `BaseProviderService`
   - 实现所有必需方法：
     * `get_available_models()`
     * `send_chat_message()`
     * `handle_streaming_response()`
     * `validate_api_key()`

2. **配置注册检查**：
   - 在 `ProviderConfig.CONFIGS` 中注册
   - 提供商 ID 遵循 kebab-case 命名
   - 包含必需字段：name, baseUrl, requiredEnvVars

3. **错误处理**：
   - 所有 API 调用包含 try-except
   - 网络错误、认证错误、速率限制分别处理
   - 返回统一的错误格式

**前端客户端检查**：
1. **接口实现**：
   - 实现 `AIProvider` 接口
   - 包含 `sendMessage()` 和 `streamMessage()` 方法
   - 正确处理附件上传

2. **类型安全**：
   - 所有 API 响应有类型定义
   - 使用泛型处理不同消息类型

3. **兼容性**：
   - 与 `UnifiedProviderClient` 集成
   - 在 `LLMFactory` 中注册

**检查点**：
- ✅ 接口完整性
- ✅ 错误处理覆盖
- ✅ 类型注解完整
- ✅ 配置注册正确
- ✅ 测试用例存在

如果验证失败，提供详细的修复指南。
```

**工作流集成**：

```json
{
  "custom_workflows": {
    "validate_new_provider": {
      "description": "验证新增 AI 提供商实现",
      "trigger": "manual",
      "steps": [
        {
          "name": "检查后端实现",
          "command": "cd backend && pytest tests/test_providers/test_${PROVIDER_NAME}.py -v"
        },
        {
          "name": "检查前端集成",
          "command": "npx tsc --noEmit frontend/services/providers/${PROVIDER_NAME}/*.ts"
        },
        {
          "name": "运行集成测试",
          "command": "cd backend && pytest tests/integration/test_${PROVIDER_NAME}_integration.py"
        }
      ]
    }
  }
}
```

---

### 4. 模型能力映射同步器

**用途**：当添加新模型时，自动更新模型能力映射。

**触发类型**：File Save

**目标文件**：`backend/app/services/provider_config.py`, `frontend/services/providers.ts`

**Agent 指令**：

```markdown
同步模型能力配置：

**触发条件**：`ProviderConfig` 或前端 `providers.ts` 文件被修改

**自动执行**：
1. **解析新增模型**：
   - 提取模型 ID、名称、能力列表
   - 识别模型类型（chat, image-gen, video-gen 等）

2. **更新能力映射**：
   - 在 `model_capabilities.py` 中添加能力定义
   - 更新前端 `controls/constants.ts` 中的模式过滤规则
   - 同步 `useModels` Hook 中的可见性逻辑

3. **生成测试用例**：
   - 创建模型能力查询测试
   - 添加模式过滤测试

4. **更新文档**：
   - 在 `README.md` 中添加模型列表
   - 更新 API 文档中的模型参数说明

**验证步骤**：
- 运行 `pytest tests/test_model_capabilities.py`
- 检查前端模型选择器是否正确显示
- 验证模式切换时的模型过滤

**输出**：
- 生成的测试文件路径
- 需要手动更新的文档列表
- 验证命令
```

---

## 前后端协同 Hooks

### 5. API 契约验证器

**用途**：确保前后端 API 定义一致。

**触发类型**：File Save

**目标文件**：`backend/app/routers/**/*.py`, `frontend/services/apiClient.ts`

**Agent 指令**：

```markdown
验证前后端 API 契约一致性：

**后端 API 变更检测**：
1. **提取路由定义**：
   - 解析 FastAPI 路由装饰器
   - 提取端点路径、HTTP 方法、请求/响应模型

2. **生成 TypeScript 类型**：
   - 从 Pydantic 模型生成 TS 接口
   - 创建 API 客户端方法签名

3. **检查破坏性变更**：
   - 必需字段变更
   - 端点路径重命名
   - 响应结构变化

**前端 API 调用检查**：
1. **扫描 API 调用**：
   - 查找 `apiClient.post()`, `apiClient.get()` 等调用
   - 提取端点路径和请求体

2. **验证类型匹配**：
   - 请求参数是否符合后端期望
   - 响应类型是否正确声明

3. **错误处理验证**：
   - 检查是否处理后端可能返回的错误码
   - 验证错误消息显示

**自动修复**：
- 生成缺失的 TypeScript 类型
- 更新过时的 API 调用
- 添加缺失的错误处理

**报告格式**：
```
🔍 API 契约验证报告

后端变更：
  ✅ POST /api/chat - 添加新参数 'temperature'
  ⚠️  GET /api/models - 响应格式变更
  ❌ DELETE /api/sessions/:id - 端点已删除

前端影响：
  📝 需要更新：frontend/hooks/useChat.ts:45
  📝 需要更新：frontend/services/apiClient.ts:120
  ⚠️  破坏性变更：frontend/components/ChatView.tsx:78

建议操作：
  1. 更新 frontend/types/types.ts 中的 ChatMessage 接口
  2. 在 useChat Hook 中添加 temperature 参数处理
  3. 移除对已删除端点的调用
```
```

---

### 6. 状态管理同步器

**用途**：确保前端状态与后端数据模型保持一致。

**触发类型**：File Save

**目标文件**：`backend/app/models/db_models.py`, `frontend/services/db.ts`

**Agent 指令**：

```markdown
同步前后端数据模型：

**后端数据库模型变更**：
1. **检测模型变化**：
   - 新增表或字段
   - 修改字段类型
   - 添加关系（ForeignKey, ManyToMany）

2. **生成前端类型**：
   - 从 SQLAlchemy 模型生成 TS 接口
   - 包含所有字段和类型映射
   - 生成可选字段（nullable=True）

3. **更新 IndexedDB Schema**：
   - 修改 `frontend/services/db.ts` 中的 Dexie 表定义
   - 添加新索引（基于后端索引）
   - 生成迁移脚本

**示例输出**：
```typescript
// 从 ConfigProfile 模型生成
export interface ConfigProfile {
  id: number;
  user_id: number;
  name: string;
  provider_id: string;
  api_key_encrypted: string;
  model_config?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

// 更新 Dexie 表定义
profiles: '++id, user_id, provider_id, created_at'
```

**验证步骤**：
- 运行数据库迁移：`alembic upgrade head`
- 检查前端 IndexedDB 版本号是否递增
- 运行前端数据访问测试

**警告检查**：
- ⚠️ 字段重命名可能导致数据丢失
- ⚠️ 类型变更需要数据迁移脚本
- ⚠️ 删除字段前确认无前端引用
```

---

## 测试和文档 Hooks

### 7. 测试覆盖率维护器

**用途**：当代码变更时，自动维护测试覆盖率。

**触发类型**：File Save

**目标文件**：`backend/app/**/*.py`, `frontend/**/*.{ts,tsx}` (排除 tests/)

**Agent 指令**：

```markdown
维护测试覆盖率：

**代码变更分析**：
1. **识别新增/修改的函数和方法**：
   - 后端：类方法、路由处理函数、服务函数
   - 前端：React 组件、Hooks、工具函数

2. **检查现有测试覆盖**：
   - 定位对应的测试文件
   - 分析测试用例是否覆盖新代码
   - 计算覆盖率变化

3. **生成缺失的测试**：
   - 基于函数签名生成测试骨架
   - 包含正常情况和边界情况
   - 添加错误处理测试

**后端测试生成**（Pytest）：
```python
# 为 backend/app/services/gemini/chat_handler.py 生成
def test_chat_handler_send_message_success():
    """测试成功发送聊天消息"""
    handler = ChatHandler(api_key="test_key")
    response = handler.send_message(
        messages=[{"role": "user", "content": "Hello"}],
        model="gemini-2.0-flash-exp"
    )
    assert response.status_code == 200
    assert "content" in response.json()

def test_chat_handler_send_message_invalid_api_key():
    """测试无效 API 密钥"""
    handler = ChatHandler(api_key="invalid")
    with pytest.raises(AuthenticationError):
        handler.send_message(...)

def test_chat_handler_send_message_rate_limit():
    """测试速率限制"""
    # 模拟速率限制场景
```

**前端测试生成**（Vitest）：
```typescript
// 为 frontend/hooks/useChat.ts 生成
describe('useChat Hook', () => {
  it('should send message successfully', async () => {
    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage('Hello');
    });
    expect(result.current.messages).toHaveLength(1);
  });

  it('should handle API errors', async () => {
    // 模拟 API 错误
    apiClient.post.mockRejectedValueOnce(new Error('Network error'));
    const { result } = renderHook(() => useChat());
    await expect(result.current.sendMessage('Hello'))
      .rejects.toThrow('Network error');
  });
});
```

**执行流程**：
1. 生成测试文件（如果不存在）
2. 运行新测试验证正确性
3. 更新覆盖率报告
4. 如果覆盖率下降超过 5%，发出警告

**输出报告**：
```
📊 测试覆盖率报告

变更文件：backend/app/services/gemini/chat_handler.py
├─ 新增函数：send_message_with_retry (0% 覆盖)
├─ 修改函数：send_message (85% → 78% 覆盖)
└─ 总体覆盖率：92% → 89% (-3%)

生成的测试：
✅ tests/test_chat_handler.py::test_send_message_with_retry_success
✅ tests/test_chat_handler.py::test_send_message_with_retry_max_attempts
✅ tests/test_chat_handler.py::test_send_message_with_retry_permanent_error

运行结果：3 passed, 0 failed

建议：
- 为 send_message 的新分支添加测试
- 考虑添加集成测试覆盖重试逻辑
```
```

---

### 8. API 文档自动生成器

**用途**：根据代码自动生成和更新 API 文档。

**触发类型**：Manual Trigger / File Save

**目标文件**：`backend/app/routers/**/*.py`

**Agent 指令**：

```markdown
生成 API 文档：

**文档生成范围**：
1. **端点信息**：
   - HTTP 方法和路径
   - 请求参数（路径、查询、请求体）
   - 响应格式和状态码
   - 认证要求

2. **请求/响应示例**：
   - 从 Pydantic 模型生成 JSON 示例
   - 包含成功和错误响应
   - 添加真实场景的 cURL 示例

3. **业务逻辑说明**：
   - 从函数文档字符串提取
   - 说明端点用途和使用场景
   - 列出前置条件和副作用

**输出格式**（Markdown）：

```markdown
# API 文档

## 聊天相关 API

### POST /api/chat

**描述**：发送聊天消息并获取 AI 响应

**认证**：Bearer Token（JWT）

**请求参数**：
- `session_id` (string, required): 会话 ID
- `message` (string, required): 用户消息内容
- `attachments` (array, optional): 附件列表
- `model` (string, optional): 指定使用的模型

**请求示例**：
\```bash
curl -X POST http://localhost:21574/api/chat \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "123e4567-e89b-12d3-a456-426614174000",
    "message": "解释量子计算的原理",
    "model": "gemini-2.0-flash-exp"
  }'
\```

**响应示例**（成功）：
\```json
{
  "message_id": "msg_abc123",
  "content": "量子计算是利用量子力学现象...",
  "model": "gemini-2.0-flash-exp",
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 120,
    "total_tokens": 135
  }
}
\```

**响应示例**（错误）：
\```json
{
  "error": "Invalid API key",
  "error_code": "AUTHENTICATION_ERROR",
  "status_code": 401
}
\```

**错误码**：
- `401`: 认证失败（API 密钥无效或缺失）
- `429`: 速率限制（请求过于频繁）
- `500`: 服务器内部错误

**相关端点**：
- `GET /api/chat/history` - 获取聊天历史
- `POST /api/chat/stream` - 流式聊天
```

**生成的文件**：
- `docs/api/chat.md` - 聊天 API 文档
- `docs/api/models.md` - 模型 API 文档
- `docs/api/storage.md` - 存储 API 文档
- `docs/API_REFERENCE.md` - 完整 API 参考

**集成 OpenAPI**：
- 更新 `openapi.json` Schema
- 生成 Swagger UI 配置
- 导出 Postman Collection

**验证步骤**：
- 运行示例请求验证正确性
- 检查 Swagger UI 显示
- 确保所有端点都已文档化
```

---

## MCP 集成示例

### 9. Figma 设计系统验证器

**用途**：使用 Figma MCP 验证前端组件是否符合设计规范。

**触发类型**：File Save

**目标文件**：`frontend/components/**/*.tsx`, `**/*.css`

**Agent 指令**：

```markdown
使用 Figma MCP 验证设计一致性：

**前提条件**：
- Figma MCP 已配置并启用
- 已设置 FIGMA_FILE_KEY 环境变量

**验证流程**：
1. **使用 MCP 获取设计系统**：
   - 调用 `figma.getFile(fileKey)` 获取设计文件
   - 提取组件库（Components）
   - 解析设计令牌（Design Tokens）

2. **分析修改的组件**：
   - 解析 React 组件的样式
   - 提取使用的颜色、字体、间距
   - 识别组件类型（按钮、卡片、表单等）

3. **对比设计规范**：
   - 颜色值是否匹配设计令牌
   - 字体大小和行高是否符合规范
   - 间距（padding, margin）是否使用标准值
   - 圆角、阴影等是否一致

4. **检查组件结构**：
   - Hero 区块结构
   - 导航元素布局
   - 按钮样式和状态
   - 表单元素一致性

**示例检查点**：
```typescript
// 检查按钮组件
// frontend/components/common/Button.tsx

设计规范（Figma）：
  Primary Button:
    - Background: #3B82F6 (blue-500)
    - Text: #FFFFFF
    - Padding: 12px 24px
    - Border Radius: 8px
    - Font: Inter 16px/24px

实际代码：
  className="bg-blue-600 text-white px-6 py-3 rounded-lg"

❌ 问题：
  - 背景色不匹配：#3B82F6 (设计) vs #2563EB (代码)
  - 圆角不匹配：8px (设计) vs 12px (代码)

建议修复：
  className="bg-blue-500 text-white px-6 py-3 rounded-lg"
  或使用 CSS 变量：
  className="btn-primary"  // 定义在 design-tokens.css
```

**验证报告**：
```
🎨 Figma 设计验证报告

组件：frontend/components/chat/InputArea.tsx

✅ 通过的检查：
  - 字体使用正确（Inter）
  - 输入框高度符合规范（40px）
  - 按钮间距正确（8px gap）

❌ 不符合设计的地方：
  1. 发送按钮颜色
     设计：#10B981 (green-500)
     代码：#059669 (green-600)
     位置：第 45 行

  2. 输入框边框颜色
     设计：#E5E7EB (gray-200)
     代码：#D1D5DB (gray-300)
     位置：第 32 行

⚠️ 警告：
  - 输入框圆角使用了自定义值（10px），设计系统中未定义

建议操作：
  1. 更新 Tailwind 配置以匹配设计令牌
  2. 创建 design-tokens.css 统一管理颜色值
  3. 与设计师确认圆角值是否需要添加到设计系统
```

**MCP 工具调用示例**：
```typescript
// Hook 中的 MCP 调用伪代码
const figmaFile = await mcp.figma.getFile(process.env.FIGMA_FILE_KEY);
const components = figmaFile.components;
const tokens = extractDesignTokens(components);

// 对比组件样式
const issues = compareStyles(componentCode, tokens);
```
```

---

### 10. 数据库同步 MCP Hook

**用途**：使用 SQLite MCP 从示例文件同步数据库。

**触发类型**：File Save

**目标文件**：`backend/data/sample_*.json`

**Agent 指令**：

```markdown
使用 SQLite MCP 同步示例数据：

**前提条件**：
- SQLite MCP 已配置
- 数据库连接已建立

**同步流程**：
1. **检测示例数据变更**：
   - 监控 `backend/data/` 目录下的 JSON 文件
   - 解析 JSON 结构和数据

2. **使用 MCP 执行数据库操作**：
   ```typescript
   // 伪代码
   const samples = JSON.parse(sampleFile);

   for (const record of samples) {
     await mcp.sqlite.execute(`
       INSERT OR REPLACE INTO ${table}
       (id, name, config, created_at)
       VALUES (?, ?, ?, ?)
     `, [record.id, record.name, JSON.stringify(record.config), new Date()]);
   }
   ```

3. **验证数据完整性**：
   - 检查外键约束
   - 验证必填字段
   - 确认数据类型匹配

4. **生成迁移报告**：
   - 新增记录数
   - 更新记录数
   - 删除记录数
   - 失败记录列表

**示例文件**：`backend/data/sample_personas.json`
```json
[
  {
    "id": "persona_assistant",
    "name": "通用助手",
    "system_prompt": "你是一个友好的 AI 助手...",
    "icon": "🤖",
    "created_at": "2026-01-01T00:00:00Z"
  }
]
```

**同步输出**：
```
📊 数据库同步报告

文件：backend/data/sample_personas.json
表：personas

操作结果：
  ✅ 新增：5 条记录
  ✅ 更新：2 条记录
  ⚠️  跳过：1 条记录（ID 冲突）
  ❌ 失败：0 条记录

详细日志：
  [INSERT] persona_assistant
  [INSERT] persona_coder
  [UPDATE] persona_creative (name changed)
  [SKIP]   persona_duplicate (ID already exists)

数据库状态：
  总记录数：15
  最后更新：2026-01-09 10:30:00
```
```

---

### 11. Jira 票据状态同步器

**用途**：使用 Jira MCP 在任务完成后自动更新票据状态。

**触发类型**：Agent Stop（提交后）

**目标文件**：Git commit message

**Agent 指令**：

```markdown
使用 Jira MCP 同步任务状态：

**触发条件**：提交消息包含 Jira 票据号（如 "feat: add feature [PROJ-123]"）

**同步流程**：
1. **提取票据信息**：
   - 从 commit message 解析 Jira 票据号
   - 支持格式：[PROJ-123], PROJ-123, #PROJ-123

2. **分析代码变更**：
   - 提取修改的文件列表
   - 识别变更类型（功能、修复、重构）
   - 计算代码行数变化

3. **使用 MCP 更新 Jira**：
   ```typescript
   // 伪代码
   const ticket = await mcp.jira.getIssue(ticketId);

   await mcp.jira.addComment(ticketId, {
     body: `
       代码已提交到 main 分支

       提交哈希：${commitHash}
       变更文件：${changedFiles.length} 个
       主要变更：
       - ${changesSummary}

       查看完整提交：${gitRepoUrl}/commit/${commitHash}
     `
   });

   // 如果所有子任务完成，自动转移状态
   if (allSubtasksCompleted) {
     await mcp.jira.transitionIssue(ticketId, 'Done');
   }
   ```

4. **验证工作流**：
   - 检查票据状态是否允许转移
   - 验证必填字段是否完整
   - 确认权限

**示例场景**：

```bash
# Commit message
git commit -m "feat: add Google Gemini 2.0 Flash support [INFRA-456]"

# Hook 自动执行：
1. 提取票据号：INFRA-456
2. 获取票据信息：
   - 标题："支持 Gemini 2.0 Flash 模型"
   - 当前状态：In Progress
   - 子任务：3/3 完成

3. 添加评论：
   "代码已提交到 main 分支

   提交哈希：fc9c2a4
   变更文件：8 个
   主要变更：
   - 添加 Gemini 2.0 Flash 模型配置
   - 更新模型能力映射
   - 添加相关测试用例

   查看完整提交：https://github.com/org/repo/commit/fc9c2a4"

4. 自动转移状态：In Progress → Code Review

5. 通知团队：
   - Slack 通知相关开发者
   - 发送邮件给 QA 团队
```

**输出报告**：
```
🎫 Jira 同步报告

票据：INFRA-456 - 支持 Gemini 2.0 Flash 模型

✅ 评论已添加
✅ 状态已更新：In Progress → Code Review
✅ 通知已发送：3 位团队成员

下一步：
- 等待 Code Review 完成
- QA 测试环境：https://staging.example.com
- 预计完成时间：2026-01-10
```
```

---

## 项目特定工作流

### 12. 图像生成端到端测试

**用途**：在修改图像生成相关代码时，自动运行端到端测试。

**触发类型**：File Save

**目标文件**：`backend/app/services/gemini/image_*.py`, `frontend/services/providers/google/media/image-*.ts`

**Agent 指令**：

```markdown
运行图像生成端到端测试：

**测试范围**：
1. **后端 API 测试**：
   - 测试各个图像生成端点（Imagen 3, Gemini 2.5 Flash）
   - 验证参数验证逻辑
   - 测试错误处理（无效参数、API 失败）

2. **前端集成测试**：
   - 模拟用户选择图像生成模式
   - 测试参数面板交互
   - 验证图像上传和预览
   - 测试结果显示和下载

3. **完整流程测试**：
   ```typescript
   // 伪代码
   test('完整的图像生成流程', async () => {
     // 1. 用户输入提示词
     await inputPrompt('a futuristic city at sunset');

     // 2. 选择模型
     await selectModel('imagen-3.0-generate-001');

     // 3. 设置参数
     await setParameter('aspectRatio', '16:9');
     await setParameter('numImages', 4);

     // 4. 提交生成请求
     await clickGenerate();

     // 5. 等待结果
     const images = await waitForImages({ timeout: 30000 });

     // 6. 验证结果
     expect(images).toHaveLength(4);
     expect(images[0]).toHaveProperty('url');
     expect(images[0].url).toMatch(/^https:\/\//);

     // 7. 测试下载功能
     await downloadImage(images[0]);
     expect(downloadedFile).toExist();
   });
   ```

4. **性能测试**：
   - 测试并发生成请求
   - 验证队列处理逻辑
   - 检查内存使用

**执行步骤**：
1. 启动测试环境（后端 + 前端）
2. 运行 Playwright 端到端测试
3. 收集测试结果和截图
4. 生成覆盖率报告

**测试报告**：
```
🎨 图像生成端到端测试报告

测试环境：
  后端：http://localhost:21574
  前端：http://localhost:21573

测试结果：
  ✅ Imagen 3 基础生成：通过（2.3s）
  ✅ Imagen 3 多图生成：通过（5.1s）
  ✅ Gemini Flash 图像生成：通过（1.8s）
  ✅ 参数验证：通过（0.5s）
  ❌ 并发生成测试：失败
    错误：超时（30s）
    位置：tests/e2e/image-gen.spec.ts:45
    原因：队列处理逻辑可能存在死锁

  ⚠️  错误处理测试：警告
    未捕获的错误：Network timeout
    建议：添加重试逻辑

性能指标：
  平均生成时间：2.4s
  并发处理能力：3 请求/秒
  内存使用：峰值 512MB

截图：
  - tests/screenshots/image-gen-success.png
  - tests/screenshots/image-gen-error.png

建议修复：
  1. 优化并发队列处理逻辑（worker pool）
  2. 添加网络错误重试机制
  3. 改进错误消息显示
```
```

---

### 13. AI 响应质量监控

**用途**：监控 AI 响应质量，自动检测和记录异常响应。

**触发类型**：Real-time Monitor（后台运行）

**目标文件**：N/A（监控运行时数据）

**Agent 指令**：

```markdown
监控 AI 响应质量：

**监控指标**：
1. **响应时间**：
   - 平均响应时间
   - P95, P99 响应时间
   - 超时次数

2. **响应质量**：
   - 空响应或截断响应
   - 格式错误（无效 JSON）
   - 重复内容检测
   - 语言不符（请求中文但返回英文）

3. **错误率**：
   - API 错误次数
   - 错误类型分布
   - 重试成功率

4. **成本追踪**：
   - Token 使用量
   - API 调用费用
   - 按提供商和模型分组

**异常检测规则**：
```python
# 伪代码
def detect_anomalies(response):
    issues = []

    # 1. 响应时间异常
    if response.duration > 30000:  # 30秒
        issues.append({
            'type': 'slow_response',
            'severity': 'warning',
            'message': f'响应时间过长：{response.duration}ms'
        })

    # 2. 空响应
    if not response.content or len(response.content) < 10:
        issues.append({
            'type': 'empty_response',
            'severity': 'error',
            'message': '响应内容为空或过短'
        })

    # 3. 格式错误
    if response.format == 'json' and not is_valid_json(response.content):
        issues.append({
            'type': 'invalid_format',
            'severity': 'error',
            'message': 'JSON 格式无效'
        })

    # 4. 语言不符
    detected_lang = detect_language(response.content)
    if detected_lang != response.expected_lang:
        issues.append({
            'type': 'language_mismatch',
            'severity': 'warning',
            'message': f'期望 {response.expected_lang}，实际 {detected_lang}'
        })

    # 5. 重复内容
    if is_repetitive(response.content):
        issues.append({
            'type': 'repetitive_content',
            'severity': 'warning',
            'message': '检测到重复内容'
        })

    return issues
```

**自动响应**：
- 记录异常到日志系统（Loki, Elasticsearch）
- 发送 Slack 通知（严重错误）
- 自动重试（特定错误类型）
- 切换到备用模型（多次失败后）

**监控仪表板数据**：
```json
{
  "timestamp": "2026-01-09T10:30:00Z",
  "provider": "google",
  "model": "gemini-2.0-flash-exp",
  "metrics": {
    "total_requests": 1250,
    "successful_requests": 1230,
    "failed_requests": 20,
    "avg_response_time_ms": 1850,
    "p95_response_time_ms": 4200,
    "p99_response_time_ms": 8500,
    "total_tokens": 1250000,
    "estimated_cost_usd": 0.625
  },
  "anomalies": [
    {
      "type": "slow_response",
      "count": 15,
      "severity": "warning"
    },
    {
      "type": "empty_response",
      "count": 3,
      "severity": "error"
    }
  ]
}
```

**告警规则**：
- 错误率 > 5%：发送 Slack 告警
- 平均响应时间 > 5s：发送邮件通知
- 成本超预算：发送短信告警
```

---

### 14. 国际化翻译同步器

**用途**：确保多语言文件保持同步。

**触发类型**：File Save

**目标文件**：`frontend/locales/*/common.json`

**Agent 指令**：

```markdown
同步国际化翻译：

**触发条件**：主语言文件（`en/common.json`）被修改

**同步流程**：
1. **识别变更的键**：
   - 新增的翻译键
   - 修改的翻译值
   - 删除的翻译键

2. **检查其他语言文件**：
   - 支持的语言：`zh-CN`, `zh-TW`, `ja`, `ko`, `es`, `fr`, `de`
   - 对于每个语言文件：
     * 标记缺失的键为 `"__NEEDS_TRANSLATION__"`
     * 标记修改的键为 `"__NEEDS_REVIEW__"`
     * 删除废弃的键

3. **生成翻译任务清单**：
   ```json
   // 示例：zh-CN/common.json
   {
     "welcome": "欢迎使用",
     "new_feature": "__NEEDS_TRANSLATION__", // 新增
     "updated_text": "更新的文本 __NEEDS_REVIEW__", // 需要审查
     // "deprecated_key" 已删除
   }
   ```

4. **创建翻译工作单**：
   ```markdown
   # 翻译任务清单 - 2026-01-09

   ## 中文（简体）zh-CN

   ### 需要翻译（3 个键）
   - `image_generation.new_model`
     EN: "Imagen 3.0 - Fast and high quality"
     ZH: [待翻译]

   - `settings.api_key_placeholder`
     EN: "Enter your API key"
     ZH: [待翻译]

   ### 需要审查（1 个键）
   - `chat.send_message`
     EN（旧）: "Send"
     EN（新）: "Send Message"
     ZH（当前）: "发送"
     建议：保持不变或改为"发送消息"

   ## 日文 ja

   ### 需要翻译（3 个键）
   [同上]
   ```

5. **可选：自动翻译**：
   - 使用 AI 提供翻译建议
   - 标记为"AI 翻译 - 需人工审查"
   - 记录翻译质量评分

**示例输出**：
```
🌍 国际化同步报告

主语言文件：frontend/locales/en/common.json

变更摘要：
  ✅ 新增：3 个键
  ✅ 修改：1 个键
  ✅ 删除：2 个键

影响的语言：
  📝 zh-CN: 3 个需要翻译，1 个需要审查
  📝 zh-TW: 3 个需要翻译，1 个需要审查
  📝 ja: 3 个需要翻译，1 个需要审查
  📝 ko: 3 个需要翻译，1 个需要审查

生成的文件：
  - docs/translations/todo-2026-01-09.md
  - frontend/locales/*/common.json（已更新标记）

AI 翻译建议：
  ✅ 已生成（confidence > 0.8）
  ⚠️  建议人工审查高优先级文本

下一步：
  1. 分配翻译任务给团队成员
  2. 审查 AI 生成的翻译
  3. 运行 i18n 测试：npm run test:i18n
```
```

---

## 使用 MCP 的最佳实践

### 配置 MCP 服务器

在 `.kiro/settings/mcp.json` 中配置：

```json
{
  "mcpServers": {
    "figma": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-figma"],
      "env": {
        "FIGMA_PERSONAL_ACCESS_TOKEN": "${FIGMA_TOKEN}"
      }
    },
    "sqlite": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sqlite"],
      "env": {
        "DB_PATH": "${WORKSPACE_ROOT}/backend/database.db"
      }
    },
    "jira": {
      "command": "npx",
      "args": ["-y", "mcp-server-jira"],
      "env": {
        "JIRA_HOST": "https://your-org.atlassian.net",
        "JIRA_EMAIL": "${JIRA_EMAIL}",
        "JIRA_API_TOKEN": "${JIRA_API_TOKEN}"
      }
    }
  }
}
```

### 自动批准设置

对于频繁使用的 MCP 工具，设置自动批准：

```json
{
  "autoApprove": {
    "sqlite": ["query", "execute"],
    "figma": ["getFile", "getComponents"]
  }
}
```

### MCP Hook 模板

```json
{
  "hooks": {
    "on_file_save": [
      {
        "name": "mcp_hook_example",
        "description": "使用 MCP 工具的 Hook 示例",
        "pattern": "**/*.tsx",
        "agent_prompt": "使用 Figma MCP 验证组件设计...",
        "mcp_tools": ["figma.getFile", "figma.getComponents"],
        "auto_approve_mcp": true,
        "enabled": true
      }
    ]
  }
}
```

---

## 总结

本文档提供了 14 个针对多模态 AI 应用框架的实战 Hook 示例，涵盖：

- ✅ **安全和质量**：代码扫描、质量门禁
- ✅ **AI 提供商**：配置验证、能力映射同步
- ✅ **前后端协同**：API 契约验证、状态同步
- ✅ **测试和文档**：自动测试生成、API 文档
- ✅ **MCP 集成**：Figma 设计验证、Jira 同步、数据库同步
- ✅ **项目特定**：图像生成测试、响应监控、国际化同步

### 快速开始

1. **选择相关 Hooks**：根据项目需求选择适用的 Hook
2. **添加到配置**：将 Hook 指令添加到 `.claude/hooks.json`
3. **配置 MCP**（如需要）：在 `.kiro/settings/mcp.json` 中配置 MCP 服务器
4. **测试 Hook**：修改目标文件，观察 Hook 行为
5. **优化和定制**：根据实际使用情况调整 Hook 参数

### 相关资源

- [Claude Hooks 配置指南](../HOOKS_GUIDE.md)
- [MCP 使用指南](./mcp-usage-guide.md)
- [项目协作流程](./claude-mcp-collaboration.md)

---

**版本**: 1.0.0
**更新日期**: 2026-01-09
**维护者**: Claude Code Team
