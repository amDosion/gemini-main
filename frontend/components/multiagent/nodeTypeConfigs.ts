/**
 * Node Type Configurations for Multi-Agent Workflow Editor
 *
 * Architecture principle: Agent is the primary abstraction.
 * LLM/model is an internal component of an agent, NOT a standalone node.
 * Tools (knowledge, code, API) are capabilities attached to agents, NOT peer-level nodes.
 *
 * Node categories:
 * - Flow Control: start, end, condition, merge, loop
 * - Agent Execution: agent, tool, human
 * - Orchestration Patterns: router, parallel
 */

export type NodeType =
  | 'start'       // Flow entry point
  | 'end'         // Flow exit point
  | 'input_text'  // Structured text input node
  | 'input_image' // Image input node
  | 'input_video' // Video input node
  | 'input_audio' // Audio input node
  | 'input_file'  // File input node
  | 'agent'       // Core execution unit (has model + system prompt + tools)
  | 'tool'        // External tool / MCP tool node
  | 'router'      // Intent-based routing / dispatcher
  | 'parallel'    // Fan-out / gather pattern
  | 'condition'   // Conditional branching
  | 'merge'       // Merge multiple branches
  | 'loop'        // Loop until condition met
  | 'human';      // Human-in-the-loop checkpoint

export interface NodeTypeConfig {
  type: NodeType;
  icon: string;
  iconColor: string;
  label: string;
  description: string;
  category: string;
  defaultInputs: number;
  defaultOutputs: number;
}

export const nodeTypeConfigs: Record<NodeType, NodeTypeConfig> = {
  start: {
    type: 'start',
    icon: '▶️',
    iconColor: 'bg-blue-500',
    label: '开始',
    description: '工作流入口',
    category: '流程控制',
    defaultInputs: 0,
    defaultOutputs: 1
  },
  end: {
    type: 'end',
    icon: '⏹️',
    iconColor: 'bg-red-500',
    label: '结束',
    description: '工作流出口',
    category: '流程控制',
    defaultInputs: 1,
    defaultOutputs: 0
  },
  input_text: {
    type: 'input_text',
    icon: '📝',
    iconColor: 'bg-emerald-500',
    label: '文本输入',
    description: '向下游节点注入任务文本',
    category: '流程控制',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  input_image: {
    type: 'input_image',
    icon: '🖼️',
    iconColor: 'bg-lime-500',
    label: '图片输入',
    description: '注入图片 URL 或上传图片',
    category: '流程控制',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  input_video: {
    type: 'input_video',
    icon: '🎬',
    iconColor: 'bg-indigo-500',
    label: '视频输入',
    description: '注入视频 URL 或上传视频',
    category: '流程控制',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  input_audio: {
    type: 'input_audio',
    icon: '🎧',
    iconColor: 'bg-sky-500',
    label: '音频输入',
    description: '注入音频 URL 或上传音频',
    category: '流程控制',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  input_file: {
    type: 'input_file',
    icon: '📎',
    iconColor: 'bg-cyan-500',
    label: '文件输入',
    description: '注入文件 URL 或上传文件',
    category: '流程控制',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  condition: {
    type: 'condition',
    icon: '🔀',
    iconColor: 'bg-yellow-500',
    label: '条件判断',
    description: '根据条件分支执行',
    category: '流程控制',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  merge: {
    type: 'merge',
    icon: '🔗',
    iconColor: 'bg-orange-500',
    label: '结果合并',
    description: '合并多个分支结果',
    category: '流程控制',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  loop: {
    type: 'loop',
    icon: '🔄',
    iconColor: 'bg-amber-500',
    label: '循环执行',
    description: '循环执行直到满足条件',
    category: '流程控制',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  agent: {
    type: 'agent',
    icon: '🤖',
    iconColor: 'bg-teal-500',
    label: '智能体',
    description: '核心执行单元：模型 + 指令 + 工具',
    category: '智能体',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  tool: {
    type: 'tool',
    icon: '🔧',
    iconColor: 'bg-indigo-500',
    label: '工具',
    description: '外部工具 / MCP 工具调用',
    category: '智能体',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  human: {
    type: 'human',
    icon: '👤',
    iconColor: 'bg-pink-500',
    label: '人工审核',
    description: '等待人工确认后继续',
    category: '智能体',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  router: {
    type: 'router',
    icon: '🎛️',
    iconColor: 'bg-violet-500',
    label: '路由器',
    description: '根据意图智能分发任务到子智能体',
    category: '编排模式',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  parallel: {
    type: 'parallel',
    icon: '⚡',
    iconColor: 'bg-cyan-500',
    label: '并行执行',
    description: '并行执行多个子任务，汇聚结果',
    category: '编排模式',
    defaultInputs: 1,
    defaultOutputs: 1
  }
};

// Group node types by category for the component library
export const nodeCategories = [
  {
    name: '流程控制',
    items: [
      nodeTypeConfigs.start,
      nodeTypeConfigs.end,
      nodeTypeConfigs.input_text,
      nodeTypeConfigs.input_image,
      nodeTypeConfigs.input_video,
      nodeTypeConfigs.input_audio,
      nodeTypeConfigs.input_file,
      nodeTypeConfigs.condition,
      nodeTypeConfigs.merge,
      nodeTypeConfigs.loop
    ]
  },
  {
    name: '智能体',
    items: [nodeTypeConfigs.agent, nodeTypeConfigs.tool, nodeTypeConfigs.human]
  },
  {
    name: '编排模式',
    items: [nodeTypeConfigs.router, nodeTypeConfigs.parallel]
  }
];
