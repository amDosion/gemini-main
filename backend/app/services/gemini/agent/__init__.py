"""
Agent Engine Services - Agent Engine 高级功能服务模块

包含：
- Memory Bank 服务
- Code Execution 服务
- A2A Protocol 服务
- Live API 服务
- Multi-Agent Systems 服务
  - Orchestrator: 智能体编排器（支持智能任务分解和代理匹配）
  - SmartTaskDecomposer: 智能任务分解器（使用 LLM 分解任务）
  - AgentMatcher: 代理匹配器（能力匹配、负载均衡）
- ADK 集成服务
- Official Google GenAI SDK Compatibility Layer (从 official/ 目录合并)
"""

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
from .coordinator_agent import CoordinatorAgent, Intent
from .sequential_agent import SequentialAgent, SequentialStep
from .parallel_agent import ParallelAgent, ParallelTask
from .workflows.image_edit_workflow import ImageEditWorkflow
from .workflows.excel_analysis_workflow import ExcelAnalysisWorkflow
from .adk_runner import ADKRunner
from .adk_agent import ADKAgent
from .interactions_service import VertexAiInteractionsService

# Official Google GenAI SDK Compatibility Layer (从 official/ 目录合并)
from .client import Client, AsyncClient, get_vertex_ai_credentials_from_db
from . import types
from .models import Models, AsyncModels
from .interactions import InteractionsResource, AsyncInteractionsResource

__all__ = [
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
    "Orchestrator",
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
    "CoordinatorAgent",  # 协调代理（Coordinator/Dispatcher Pattern）
    "Intent",  # 意图分析结果
    "SequentialAgent",  # 顺序代理（Sequential Pipeline Pattern）
    "SequentialStep",  # 顺序执行步骤
    "ParallelAgent",  # 并行代理（Parallel Fan-Out/Gather Pattern）
    "ParallelTask",  # 并行任务
    "ImageEditWorkflow",  # 图像编辑工作流
    "ExcelAnalysisWorkflow",  # Excel 分析工作流
    "ADKRunner",
    "ADKAgent",
    "VertexAiInteractionsService",
    # Official Google GenAI SDK Compatibility Layer
    "Client",
    "AsyncClient",
    "get_vertex_ai_credentials_from_db",  # 统一的 Vertex AI credentials 获取函数
    "types",
    "Models",
    "AsyncModels",
    "InteractionsResource",
    "AsyncInteractionsResource",
]
