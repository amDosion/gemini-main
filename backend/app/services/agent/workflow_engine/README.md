# Workflow Engine

`backend/app/services/agent/workflow_engine/` 是 Multi-Agent 工作流执行器的实现目录。  
对外稳定入口只有两层：

- `backend/app/services/agent/workflow_engine.py`
  - 兼容旧导入路径的 shim。
- `backend/app/services/agent/workflow_engine/__init__.py`
  - package entrypoint，导出 `WorkflowEngine` 和 `ExecutionContext`。

## 边界规则

- `engine.py`
  - 只保留 `WorkflowEngine` 类壳、常量、缓存字段、方法绑定、少量桥接。
  - 不再承载大段业务实现。
- 新增复杂逻辑时，优先放到独立模块，再通过 `WorkflowEngine.<method> = helper` 方式绑定回类。
- 如果一个实现会同时被多个节点路径复用，不要放回 `engine.py`，应该抽成 helper module。
- 目录内模块尽量单向依赖 `engine` 的绑定方法，不要在 helper module 之间形成复杂双向导入。

## 模块职责

- `engine.py`
  - `WorkflowEngine` 类定义。
  - 常量、缓存、helper 绑定。
- `orchestration.py`
  - 工作流级执行编排。
  - `execute`、`_execute_node`、trace、callback、并发队列。
  - 负责“节点怎么跑”，不负责 provider/model 细节。
- `agent_execution.py`
  - `agent` 节点执行。
  - Agent 查找、默认值解析、task type 路由、ADK/runtime 分流。
  - 负责“agent 节点怎么决策”，不负责底层媒体细节实现。
- `agent_resolution.py`
  - provider/profile/model 选择与 service 创建。
  - inline agent 构造、模型兼容性判断、默认模型推断。
- `image_pipeline.py`
  - 图片生成、图片编辑、vision understand、图片质量校验。
  - 负责 image/vision 专用 prompt、kwargs、重试与校验。
- `media.py`
  - 视频/音频生成参数构造与 service result 归一化。
  - 负责 audio/video runtime payload，不处理图片编辑。
- `analysis_tools.py`
  - `sheet_analyze`、`prompt_optimize`、`table_analyze`。
  - 负责分析型 builtin tool 的高层执行。
- `builtin_tools.py`
  - 内置工具调度。
  - web search、MCP、sheet-stage、browse/read-webpage 等 runtime bridge。
- `flow_control.py`
  - 条件、router、loop、merge、模板解析、tool args 解析。
  - 负责控制流，不涉及 provider/runtime。
- `references.py`
  - 文件/表格引用加载。
  - `file_url`、`data_url`、DataFrame 解析、远程引用校验。
- `payload_media.py`
  - media/file URL 归一化与提取。
  - 输入 payload 媒体抽取、reference image 归一化。
- `text_utils.py`
  - 文本、data URL、CSV、preview、类型转换。
- `amazon_ads.py`
  - Amazon Ads 专用分析与字段映射。

## 修改指南

### 1. 新增节点类型

- 首先修改 `orchestration.py` 的 `execute_node()`。
- 如果节点逻辑较重，新增独立模块，然后在 `engine.py` 绑定 helper。
- 不要把新节点完整实现直接塞回 `engine.py`。

### 2. 新增 agent task type

- 修改 `agent_execution.py`。
- 如果是媒体任务：
  - 图片/视觉相关放 `image_pipeline.py`
  - 视频/音频相关放 `media.py`
- 如果涉及 provider/model 选择，补到 `agent_resolution.py`。

### 3. 新增 builtin tool

- 调度入口放 `builtin_tools.py` 或 `analysis_tools.py`。
- 纯 payload 归一化放 `payload_media.py` / `text_utils.py` / `references.py`。
- 如果前端属性面板需要新工具，也要同步更新 `frontend/components/multiagent/PropertiesPanel.tsx`。

### 4. 新增模板/解析能力

- 控制流与模板变量解析放 `flow_control.py`。
- 文件/表格输入解析放 `references.py`。
- 不要在 agent 节点里重复拼文件解析逻辑。

## 推荐检查清单

- 改 `orchestration.py` / `agent_execution.py` 后：
  - `backend/tests/test_workflow_final_status_contract.py`
  - `backend/tests/test_workflow_preview_budget_contract.py`
- 改媒体执行后：
  - `backend/tests/test_workflow_engine_media_execution.py`
  - `backend/tests/test_workflow_engine_media_helpers.py`
  - `backend/tests/test_workflow_engine_media_output_sanitization.py`
- 改模板/能力分类后：
  - `backend/tests/test_workflow_template_coverage_report.py`
  - `backend/tests/test_workflow_available_models_media_classification.py`

> **注意**：以上测试文件待创建（测试文件待创建）。

## 当前结构目标

- `engine.py` 是壳层，不是实现堆栈。
- 单个 helper module 关注一个主题。
- 新增能力时优先扩模块，不回退到“大文件集中实现”。
