# Multi-Agent System - 多智能体系统

## 概述

多智能体系统提供了智能任务分解、代理匹配和任务编排功能，支持复杂的多代理协作任务。

## 核心组件

### 1. ExecutionGraph（执行图）

执行图（DAG）管理器，负责：
- 拓扑排序
- 循环依赖检测
- 层级分组
- 依赖关系管理

**使用示例**：

```python
from app.services.gemini.agent import ExecutionGraph, SubTask

# 创建子任务（带依赖关系）
subtasks = [
    SubTask(id="task_a", description="任务A", dependencies=[]),
    SubTask(id="task_b", description="任务B", dependencies=["task_a"]),
    SubTask(id="task_c", description="任务C", dependencies=["task_b"])
]

# 创建执行图
graph = ExecutionGraph(subtasks)

# 获取执行层级（按拓扑排序）
levels = graph.get_execution_levels()
# levels[0] = [task_a]  # 第一层
# levels[1] = [task_b]  # 第二层
# levels[2] = [task_c]  # 第三层

# 检测循环依赖
if graph.has_cycle():
    print("检测到循环依赖！")

# 获取所有依赖（包括间接依赖）
all_deps = graph.get_all_dependencies("task_c")
# 返回: {"task_a", "task_b"}
```

### 2. Orchestrator（编排器）

智能体编排器，负责：
- 任务分解和分配
- 智能体选择策略
- 结果聚合
- 错误处理和重试

**使用示例**：

```python
from app.services.gemini.agent import Orchestrator
from app.services.gemini.google_service import GoogleService

# 创建 GoogleService（用于智能任务分解）
google_service = GoogleService(api_key="your_api_key")

# 创建编排器
orchestrator = Orchestrator(
    db=db_session,
    google_service=google_service,
    use_smart_decomposition=True  # 启用智能任务分解
)

# 执行编排
result = await orchestrator.orchestrate(
    user_id="user_123",
    task="分析数据并生成报告",
    agent_ids=None  # 自动选择代理
)
```

### 3. SmartTaskDecomposer（智能任务分解器）

使用 LLM 将复杂任务分解为可执行的子任务。

**功能**：
- 使用 LLM 分析任务并分解为子任务
- 识别子任务之间的依赖关系
- 检测循环依赖
- 为每个子任务建议合适的代理

**使用示例**：

```python
from app.services.gemini.agent import SmartTaskDecomposer
from app.services.gemini.google_service import GoogleService

google_service = GoogleService(api_key="your_api_key")
decomposer = SmartTaskDecomposer(google_service=google_service)

# 分解任务
subtasks = await decomposer.decompose_task(
    task="分析数据并生成报告",
    available_agents=[
        {"id": "agent_1", "name": "数据分析代理", "capabilities": ["分析"]},
        {"id": "agent_2", "name": "报告生成代理", "capabilities": ["生成"]}
    ],
    max_subtasks=10
)

# 每个子任务包含：
# - id: 子任务 ID
# - description: 任务描述
# - required_capabilities: 所需能力
# - suggested_agent_id: 建议的代理 ID
# - dependencies: 依赖的其他子任务 ID
# - priority: 优先级（1-10）
```

### 4. ToolRegistry（工具注册表）

工具注册表，管理所有可用工具：
- 内置工具（Google Search 等）
- MCP 工具（从 MCPManager 加载）
- 自定义工具

**使用示例**：

```python
from app.services.gemini.agent import ToolRegistry, Tool
from app.services.mcp_manager import get_mcp_manager

# 创建工具注册表
mcp_manager = get_mcp_manager()
registry = ToolRegistry(mcp_manager=mcp_manager)

# 加载 MCP 工具
await registry.load_mcp_tools("mcp_session_123")

# 注册自定义工具
custom_tool = Tool(
    name="custom_tool",
    description="自定义工具",
    parameters={"type": "object", "properties": {"arg": {"type": "string"}}}
)
registry.register(custom_tool)

# 执行工具
result = await registry.execute_tool("google_search", {"query": "test"})

# 转换为 Gemini 格式
gemini_tools = registry.to_gemini_tools()
```

### 5. AgentWithTools（带工具的代理）

支持工具调用的代理，实现工具调用循环：
- LLM 决定调用工具
- 执行工具
- 将结果反馈给 LLM
- 继续直到生成最终结果

**使用示例**：

```python
from app.services.gemini.agent import AgentWithTools, ToolRegistry
from app.services.gemini.google_service import GoogleService

google_service = GoogleService(api_key="your_api_key")
tool_registry = ToolRegistry()

# 创建带工具的代理
agent = AgentWithTools(
    name="research_agent",
    google_service=google_service,
    tool_registry=tool_registry,
    model="gemini-2.0-flash-exp"
)

# 执行任务（自动使用工具）
result = await agent.execute_with_tools(
    task="搜索并分析最新的人工智能趋势",
    available_tools=["google_search"]  # 指定可用工具
)

# 结果包含：
# - result: 最终结果
# - tool_calls: 工具调用历史
# - iterations: 迭代次数
```

### 6. CoordinatorAgent（协调代理）

协调代理（Coordinator/Dispatcher Pattern），负责：
- 分析用户意图（使用 LLM）
- 选择最合适的子代理
- 路由任务到选定的代理

**使用示例**：

```python
from app.services.gemini.agent import CoordinatorAgent
from app.services.gemini.agent.agent_registry import AgentRegistryService
from app.services.gemini.google_service import GoogleService

google_service = GoogleService(api_key="your_api_key")
agent_registry = AgentRegistryService(db=db)

coordinator = CoordinatorAgent(
    google_service=google_service,
    agent_registry=agent_registry,
    model="gemini-2.0-flash-exp"
)

# 协调任务
result = await coordinator.coordinate(
    user_id="user_123",
    task="分析销售数据并生成报告"
)

# 结果包含：
# - intent: 分析出的意图类型
# - selected_agent: 选定的代理信息
# - task: 任务描述
```

### 7. SequentialAgent（顺序代理）

顺序代理（Sequential Pipeline Pattern），负责：
- 按顺序执行子代理链
- 会话状态在代理间传递
- 支持输出键（output_key）机制

**使用示例**：

```python
from app.services.gemini.agent import SequentialAgent
from app.services.gemini.agent.agent_registry import AgentRegistryService

agent_registry = AgentRegistryService(db=db)

sequential_agent = SequentialAgent(
    name="DataPipeline",
    sub_agents=[
        {
            "agent_id": "agent_1",
            "agent_name": "数据读取代理",
            "output_key": "data"
        },
        {
            "agent_id": "agent_2",
            "agent_name": "数据处理代理",
            "input_key": "data",
            "output_key": "processed_data"
        },
        {
            "agent_id": "agent_3",
            "agent_name": "报告生成代理",
            "input_key": "processed_data",
            "output_key": "report"
        }
    ],
    agent_registry=agent_registry,
    google_service=google_service,
    tool_registry=tool_registry
)

# 执行顺序管道
result = await sequential_agent.execute(
    user_id="user_123",
    initial_input="读取并处理数据"
)

# 结果包含：
# - success: 是否成功
# - final_output: 最终输出
# - session_state: 会话状态（包含所有步骤的输出）
```

### 8. ParallelAgent（并行代理）

并行代理（Parallel Fan-Out/Gather Pattern），负责：
- 并发执行多个子代理
- 聚合所有代理的结果
- 支持超时和错误处理

**使用示例**：

```python
from app.services.gemini.agent import ParallelAgent
from app.services.gemini.agent.agent_registry import AgentRegistryService

agent_registry = AgentRegistryService(db=db)

parallel_agent = ParallelAgent(
    name="DataGather",
    sub_agents=[
        {
            "agent_id": "agent_1",
            "agent_name": "API 1 获取代理",
            "input_data": "fetch from API 1",
            "output_key": "api1_data",
            "timeout": 30.0
        },
        {
            "agent_id": "agent_2",
            "agent_name": "API 2 获取代理",
            "input_data": "fetch from API 2",
            "output_key": "api2_data",
            "timeout": 30.0
        }
    ],
    agent_registry=agent_registry,
    google_service=google_service,
    tool_registry=tool_registry
)

# 执行并行任务
result = await parallel_agent.execute(
    user_id="user_123",
    shared_input="shared input"
)

# 结果包含：
# - success: 是否全部成功
# - results: 所有任务的结果（按 output_key 组织）
# - errors: 错误信息（如果有）
# - completed_count: 完成的任务数
# - failed_count: 失败的任务数
```

### 9. AgentMatcher（代理匹配器）

为子任务匹配合适的代理，考虑：
- 能力匹配（capabilities）
- 专业领域匹配（specialization）
- 负载均衡（load balancing）

**使用示例**：

```python
from app.services.gemini.agent import AgentMatcher, SubTask

matcher = AgentMatcher()

# 更新代理负载
matcher.update_agent_load("agent_1", current_tasks=5, max_capacity=10)

# 匹配代理
subtask = SubTask(
    description="分析数据",
    required_capabilities=["分析", "统计"],
    id="subtask_1"
)

matched_agent = matcher.match_agent(
    subtask=subtask,
    available_agents=[
        {"id": "agent_1", "capabilities": ["分析", "处理"]},
        {"id": "agent_2", "capabilities": ["生成", "创作"]}
    ],
    consider_load=True  # 考虑负载均衡
)
```

## API 端点

### POST `/api/multi-agent/orchestrate`

编排多智能体任务。

**请求体**：
```json
{
  "task": "分析数据并生成报告",
  "agent_ids": ["agent_1", "agent_2"],  // 可选，如果不提供则自动选择
  "mode": "default",  // 可选：default, coordinator, sequential, parallel
  "workflow_config": {  // 可选，用于 sequential/parallel 模式
    "name": "工作流名称",
    "sub_agents": [
      {
        "agent_id": "agent_1",
        "agent_name": "代理名称",
        "output_key": "output_key",
        "input_key": "input_key"  // 仅用于 sequential
      }
    ],
    "timeout": 60.0  // 仅用于 parallel
  }
}
```

**模式说明**：
- `default`: 使用 Orchestrator（智能任务分解 + 执行图）
- `coordinator`: 使用 CoordinatorAgent（意图分析 + 代理选择）
- `sequential`: 使用 SequentialAgent（顺序执行管道）
- `parallel`: 使用 ParallelAgent（并行执行 + 结果聚合）

**响应**：
```json
{
  "results": [
    {
      "subtask_id": "subtask_1",
      "subtask_description": "分析数据",
      "agent_id": "agent_1",
      "result": "分析结果..."
    },
    {
      "subtask_id": "subtask_2",
      "subtask_description": "生成报告",
      "agent_id": "agent_2",
      "dependencies": ["subtask_1"],
      "result": "报告内容..."
    }
  ],
  "summary": "Aggregated 2 results"
}
```

## 工作流程

1. **任务分解**：使用 `SmartTaskDecomposer` 将复杂任务分解为子任务
2. **构建执行图**：使用 `ExecutionGraph` 管理子任务之间的依赖关系
3. **代理匹配**：使用 `AgentMatcher` 为每个子任务匹配合适的代理
4. **工具准备**：从 `ToolRegistry` 获取代理配置的工具
5. **按层级执行**：
   - 使用拓扑排序确定执行顺序
   - 同一层级的任务并行执行
   - 如果代理配置了工具，使用 `AgentWithTools` 执行（支持工具调用循环）
   - 等待依赖任务完成后再执行下一层级
6. **结果聚合**：收集所有子任务的结果并聚合

### 执行图优势

- **并行执行**：同一层级的任务可以并行执行，提高效率
- **依赖管理**：自动处理任务之间的依赖关系
- **循环检测**：自动检测并防止循环依赖
- **层级可视化**：清晰的执行层级，便于调试和监控

## 配置

### 启用智能任务分解

智能任务分解需要 GoogleService 实例。如果未提供，系统会自动回退到简单任务分解（平均分配）。

```python
# 启用智能分解
orchestrator = Orchestrator(
    db=db,
    google_service=google_service,
    use_smart_decomposition=True
)

# 使用简单分解（无 GoogleService）
orchestrator = Orchestrator(
    db=db,
    google_service=None,
    use_smart_decomposition=False
)
```

## 错误处理

- 如果智能任务分解失败，系统会自动回退到简单任务分解
- 如果代理匹配失败，会记录警告并继续执行
- 如果子任务执行失败，会在结果中标记错误，但不影响其他子任务
- 如果工具执行失败，会在结果中标记错误，但代理可以继续执行
- 如果 MCP 工具加载失败，会记录警告但继续使用其他工具

## 测试

运行单元测试：
```bash
# Phase 1: 智能任务分解
pytest backend/tests/test_task_decomposer.py
pytest backend/tests/test_agent_matcher.py
pytest backend/tests/test_orchestrator_integration.py

# Phase 2: 执行图（DAG）管理
pytest backend/tests/test_execution_graph.py
pytest backend/tests/test_orchestrator_execution_graph.py

# Phase 3: 工具生态系统
pytest backend/tests/test_tool_registry.py
pytest backend/tests/test_agent_with_tools.py
pytest backend/tests/test_orchestrator_tools_integration.py

# Phase 5: ADK 三种模式支持
pytest backend/tests/test_coordinator_agent.py
pytest backend/tests/test_sequential_agent.py
pytest backend/tests/test_parallel_agent.py
```

## 相关文档

- [设计文档](../../../../.kiro/specs/multi-agent-adk-integration/design.md)
- [任务清单](../../../../.kiro/specs/multi-agent-adk-integration/tasks.md)
