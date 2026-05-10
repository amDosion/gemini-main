"""
Agent Engine Services - Agent Engine 高级功能服务模块

包含：
- Memory Bank 服务
- Code Execution 服务
- A2A Protocol 服务
- Live API 服务
- Multi-Agent Systems 兼容服务（Google runtime 专属）
  - Orchestrator: 智能体编排器（Google runtime 兼容 helper）
  - SmartTaskDecomposer: 智能任务分解器（使用 LLM 分解任务）
  - AgentMatcher: 代理匹配器（能力匹配、负载均衡）
- ADK 集成服务
- Official Google GenAI SDK Compatibility Layer (从 official/ 目录合并)

说明：
- 本子包仍导出若干 legacy Google runtime orchestration helpers 以保持兼容。
- provider-neutral 的 Multi-Agent 主入口应使用
  `POST /api/modes/{provider}/multi-agent`。
"""

PROVIDER_NEUTRAL_MULTI_AGENT_ENTRYPOINT = "/api/modes/{provider}/multi-agent"
LEGACY_GOOGLE_RUNTIME_ROUTE = "/api/multi-agent/orchestrate"
LEGACY_GOOGLE_RUNTIME_SYMBOLS = (
    "Orchestrator",
    "CoordinatorAgent",
    "SequentialAgent",
    "ParallelAgent",
)

# Agent Engine Services
from .memory_bank_service import BaseMemoryService, InMemoryMemoryService, VertexAiMemoryBankService
from .memory_manager import MemoryManager
from .code_executor import BaseCodeExecutor, BuiltInCodeExecutor, AgentEngineSandboxCodeExecutor
from .sandbox_manager import SandboxManager
from .a2a_protocol import A2AProtocolHandler
from .agent_card import AgentCardManager
from .agent_executor import AgentExecutor
from .live_api import LiveAPIHandler
from .orchestrator import Orchestrator
from .agent_registry import AgentRegistryService
from .task_decomposer import SmartTaskDecomposer, SubTask
from .agent_matcher import AgentMatcher, AgentLoad
from .execution_graph import ExecutionGraph
from .tool_registry import ToolRegistry, Tool, ToolExecutor, BuiltinToolExecutor, MCPToolExecutor
from .agent_with_tools import AgentWithTools, ToolCall, ToolCallResult
from .base_agent_executor import BaseAgentExecutor
from .coordinator_agent import CoordinatorAgent, Intent
from .sequential_agent import SequentialAgent, SequentialStep
from .parallel_agent import ParallelAgent, ParallelTask
from .workflows.image_edit_workflow import ImageEditWorkflow
from .workflows.excel_analysis_workflow import ExcelAnalysisWorkflow
from .adk_runner import ADKRunner
from .adk_agent import ADKAgent
from .interactions_service import VertexAiInteractionsService

# Vertex AI 凭证加载工具（保留：interactions_manager.py 等 4 处真在用）
from .client import get_vertex_ai_credentials_from_db
from . import types  # 仅为兼容：agent.types.HttpOptions 是真在用的（5 处）

# 注意：Client / AsyncClient / Models / AsyncModels 已弃用，
# 不再从 agent.__init__ 重新导出。如确需访问，必须显式：
#     from app.services.gemini.agent.client import Client
# 并会在实例化时触发 DeprecationWarning。
# 推荐改用统一池：
#     from app.services.gemini.client_pool import get_client_pool
#     client = get_client_pool().get_client(api_key=..., vertexai=False)
__all__ = [
    "PROVIDER_NEUTRAL_MULTI_AGENT_ENTRYPOINT",
    "LEGACY_GOOGLE_RUNTIME_ROUTE",
    "LEGACY_GOOGLE_RUNTIME_SYMBOLS",
    # Agent Engine Services
    "BaseMemoryService",
    "InMemoryMemoryService",
    "VertexAiMemoryBankService",
    "MemoryManager",
    "BaseCodeExecutor",
    "BuiltInCodeExecutor",
    "AgentEngineSandboxCodeExecutor",
    "SandboxManager",
    "A2AProtocolHandler",
    "AgentCardManager",
    "AgentExecutor",
    "LiveAPIHandler",
    "Orchestrator",  # Google runtime compatibility orchestrator
    "AgentRegistryService",
    "SmartTaskDecomposer",  # 智能任务分解器
    "SubTask",  # 子任务数据类
    "AgentMatcher",  # 代理匹配器
    "AgentLoad",  # 代理负载信息
    "ExecutionGraph",  # 执行图（DAG）管理
    "ToolRegistry",  # 工具注册表
    "Tool",  # 工具基类
    "ToolExecutor",  # 工具执行器接口
    "BuiltinToolExecutor",  # 内置工具执行器
    "MCPToolExecutor",  # MCP 工具执行器
    "AgentWithTools",  # 带工具的代理
    "ToolCall",  # 工具调用请求
    "ToolCallResult",  # 工具调用结果
    "BaseAgentExecutor",  # 共享的智能体执行逻辑
    "CoordinatorAgent",  # Google runtime 协调代理（Coordinator/Dispatcher Pattern）
    "Intent",  # 意图分析结果
    "SequentialAgent",  # Google runtime 顺序代理（Sequential Pipeline Pattern）
    "SequentialStep",  # 顺序执行步骤
    "ParallelAgent",  # Google runtime 并行代理（Parallel Fan-Out/Gather Pattern）
    "ParallelTask",  # 并行任务
    "ImageEditWorkflow",  # 图像编辑工作流
    "ExcelAnalysisWorkflow",  # Excel 分析工作流
    "ADKRunner",
    "ADKAgent",
    "VertexAiInteractionsService",
    # Vertex AI credentials helper（真实 4 处调用：interactions_manager.py）
    "get_vertex_ai_credentials_from_db",
    # agent.types：HttpOptions / HttpOptionsDict / HttpRetryOptions 仍被
    # client_pool / google_service / coordinators / interactions_manager 等 5 处使用
    "types",
    # 已撤回（实例化时触发 DeprecationWarning）：
    # - Client / AsyncClient（包装 google.genai.Client，应改走 client_pool.get_client_pool()）
    # - Models / AsyncModels（其内部 self._api_client.request(...) 调用对当前 google-genai 版本已 broken）
    # - InteractionsResource / AsyncInteractionsResource（早已被原生 client.aio.interactions 取代）
]
