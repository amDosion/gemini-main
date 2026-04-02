# MCP 服务模块

基于官方 MCP SDK 的完整实现，支持与 Gemini、OpenAI 等 AI 模型集成。

## 📁 架构设计

```
backend/app/services/
└── mcp/                    # 🔧 MCP 服务模块
    ├── mcp_manager.py      # 🎯 管理层（会话池、配置管理）
    ├── __init__.py         # 模块导出
    ├── types.py            # 类型定义
    ├── schema_utils.py     # Schema 转换和过滤
    ├── client.py           # MCP 客户端（官方 SDK）
    ├── adapter.py          # 工具适配器
    ├── examples.py         # 使用示例
    └── README.md           # 本文档
```

### 分层职责

| 层级 | 模块 | 职责 |
|------|------|------|
| **管理层** | `mcp_manager.py` | 会话池管理、配置管理、生命周期管理 |
| **服务层** | `mcp/client.py` | MCP 连接、工具列表、工具调用 |
| **适配层** | `mcp/adapter.py` | 工具格式转换（Gemini/OpenAI） |
| **工具层** | `mcp/schema_utils.py` | Schema 过滤和验证 |

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install mcp
```

### 2. 基本用法

```python
from app.services.mcp.mcp_manager import MCPManager
from app.services.mcp import MCPServerConfig, MCPServerType

# 创建管理器
manager = MCPManager()

# 配置服务器
config = MCPServerConfig(
    server_type=MCPServerType.STDIO,
    command="node",
    args=["weather-server.js"]
)

# 使用会话
async with manager.session("weather", config) as client:
    # 列出工具
    tools = await client.list_tools()
    print(f"可用工具: {[t.name for t in tools]}")

    # 调用工具
    result = await client.call_tool(
        tool_name="get_weather",
        arguments={"location": "Beijing"}
    )

    if result.success:
        print(f"天气信息: {result.result}")
```

---

## 📚 核心组件

### MCPClient（服务层）

直接使用官方 MCP SDK，负责底层通信。

```python
from app.services.mcp import MCPClient, MCPServerConfig, MCPServerType

config = MCPServerConfig(
    server_type=MCPServerType.STDIO,
    command="python",
    args=["server.py"],
    timeout=30.0
)

async with MCPClient(config) as client:
    tools = await client.list_tools()
    result = await client.call_tool("tool_name", {"arg": "value"})
```

**特性：**
- ✅ 基于官方 MCP SDK
- ✅ 支持 stdio 协议（进程通信）
- ✅ 自动连接管理
- ✅ 异步上下文管理器
- ✅ 工具缓存

---

### MCPManager（管理层）

高层 API，提供会话池和配置管理。

```python
from app.services.mcp.mcp_manager import MCPManager, get_mcp_manager

# 方式 1：创建新实例
manager = MCPManager()

# 方式 2：使用全局单例
manager = get_mcp_manager()

# 创建会话
await manager.create_session("my-session", config)

# 获取工具
tools = await manager.list_tools("my-session")

# 调用工具
result = await manager.call_tool(
    session_id="my-session",
    tool_name="get_weather",
    arguments={"location": "Shanghai"}
)

# 关闭会话
await manager.close_session("my-session")
```

**特性：**
- ✅ 会话池管理（自动复用）
- ✅ 配置管理
- ✅ 工具格式转换
- ✅ 批量操作
- ✅ 上下文管理器

---

### 工具适配器

将 MCP 工具转换为不同 AI 模型的格式。

```python
from app.services.mcp import GeminiToolAdapter, OpenAIToolAdapter

# Gemini 格式
adapter = GeminiToolAdapter(client)
await adapter.load_tools()
gemini_tools = adapter.to_gemini_tools()

# OpenAI 格式
adapter = OpenAIToolAdapter(client)
await adapter.load_tools()
openai_tools = adapter.to_openai_tools()

# 使用管理器直接获取
gemini_tools = await manager.get_gemini_tools("session-id")
openai_tools = await manager.get_openai_tools("session-id")
```

---

## 🔧 高级功能

### Schema 过滤

自动过滤不支持的 JSON Schema 字段。

```python
from app.services.mcp import filter_supported_schema

mcp_schema = {
    "type": "object",
    "properties": {"name": {"type": "string"}},
    "unknown_field": "will be removed"  # 不支持的字段
}

filtered = filter_supported_schema(mcp_schema)
# filtered 不包含 "unknown_field"
```

### 会话池

自动管理多个 MCP 会话。

```python
manager = MCPManager()

# 创建多个会话
await manager.create_session("weather", weather_config)
await manager.create_session("calculator", calc_config)

# 列出所有会话
sessions = manager.list_sessions()  # ["weather", "calculator"]

# 分别使用
weather_tools = await manager.list_tools("weather")
calc_result = await manager.call_tool("calculator", "add", {"a": 1, "b": 2})

# 关闭所有
await manager.close_all()
```

---

## 🎯 与 AI 模型集成

### Gemini 集成

```python
import google.generativeai as genai

manager = MCPManager()
await manager.create_session("tools", config)

# 获取 Gemini 工具
gemini_tools = await manager.get_gemini_tools("tools")

# 配置模型
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    tools=gemini_tools
)

# 使用
response = model.generate_content("What's the weather in Beijing?")

# 处理函数调用
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = await manager.call_tool(
            session_id="tools",
            tool_name=part.function_call.name,
            arguments=dict(part.function_call.args)
        )
```

### OpenAI 集成

```python
import openai

manager = MCPManager()
await manager.create_session("tools", config)

# 获取 OpenAI 工具
openai_tools = await manager.get_openai_tools("tools")

# 使用
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Calculate 1+1"}],
    tools=openai_tools
)

# 处理工具调用
for tool_call in response.choices[0].message.tool_calls:
    result = await manager.call_tool(
        session_id="tools",
        tool_name=tool_call.function.name,
        arguments=json.loads(tool_call.function.arguments)
    )
```

---

## 📖 完整示例

参见 [`examples.py`](./examples.py)，包含：

1. 基本用法
2. MCPManager 使用
3. Gemini 集成
4. OpenAI 集成
5. 会话池管理
6. 上下文管理器

运行示例：

```bash
cd backend
python -m app.services.mcp.examples
```

---

## 🔍 API 参考

### MCPServerConfig

```python
@dataclass
class MCPServerConfig:
    server_type: MCPServerType  # STDIO | SSE | HTTP | STREAMABLE_HTTP
    command: Optional[str]      # stdio: 命令
    args: Optional[List[str]]   # stdio: 参数
    env: Optional[Dict]         # stdio: 环境变量
    url: Optional[str]          # sse/http: URL
    timeout: float = 30.0       # 超时（秒）
```

### MCPClient

```python
class MCPClient:
    async def connect() -> None
    async def list_tools() -> List[MCPTool]
    async def call_tool(tool_name: str, arguments: Dict) -> MCPToolResult
    async def close() -> None

    # 属性
    is_connected: bool
    tools: Optional[List[MCPTool]]
```

### MCPManager

```python
class MCPManager:
    async def create_session(session_id: str, config: MCPServerConfig) -> MCPClient
    async def get_session(session_id: str) -> Optional[MCPClient]
    async def close_session(session_id: str) -> None
    async def close_all() -> None

    async def list_tools(session_id: str) -> List[MCPTool]
    async def call_tool(session_id: str, tool_name: str, arguments: Dict) -> MCPToolResult

    async def get_gemini_tools(session_id: str) -> List[Dict]
    async def get_openai_tools(session_id: str) -> List[Dict]
    async def get_tools_by_format(session_id: str, format_type: str) -> List[Dict]

    def list_sessions() -> List[str]

    # 上下文管理器
    async with session(session_id: str, config: MCPServerConfig)
```

---

## 🆚 与旧版对比

| 功能 | 旧版 `mcp_client.py` | 新版 `mcp/` |
|------|---------------------|------------|
| **协议** | ❌ HTTP（自定义） | ✅ stdio/SSE（官方） |
| **SDK** | ❌ httpx | ✅ 官方 MCP SDK |
| **工具列表** | ❌ 无 | ✅ `list_tools()` |
| **会话管理** | ❌ 无 | ✅ 会话池 |
| **格式转换** | ❌ 无 | ✅ Gemini/OpenAI |
| **Schema 过滤** | ❌ 无 | ✅ 自动过滤 |
| **架构** | ❌ 单文件 | ✅ 分层设计 |

---

## 📝 注意事项

1. **MCP SDK 要求 Python 3.10+**
   ```bash
   python --version  # 确保 >= 3.10
   ```

2. **stdio 模式需要 Node.js/Python 环境**
   ```bash
   node --version
   python --version
   ```

3. **会话复用**
   - 相同 `session_id` 会复用连接
   - 建议使用上下文管理器自动清理

4. **错误处理**
   ```python
   try:
       result = await manager.call_tool(...)
       if not result.success:
           print(f"Error: {result.error}")
   except ValueError as e:
       print(f"Session not found: {e}")
   ```

---

## 🔗 参考资源

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Google Gemini MCP 集成](https://github.com/google/generative-ai-python)
- [项目协作文档](../../../../.kiro/steering/mcp-usage-guide.md)

---

## 🤝 贡献

如需添加新功能或修复 Bug，请参考：
- 架构设计遵循 `storage/` 模块的分层模式
- 代码风格遵循项目规范
- 添加单元测试

---

**版本**: 2.0
**更新时间**: 2026-01-11
**作者**: Claude Code + 用户协作
