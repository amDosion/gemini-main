/**
 * Node Type Configurations for Multi-Agent Workflow Editor
 * 
 * Defines all available node types with their visual properties and behavior
 * Includes Google ADK patterns: parallel, loop, coordinator
 */

export type NodeType = 
  | 'start'       // 开始节点
  | 'end'         // 结束节点
  | 'llm'         // 大模型节点
  | 'knowledge'   // 知识库节点
  | 'agent'       // 智能体节点
  | 'condition'   // 条件节点
  | 'merge'       // 合并节点
  | 'code'        // 代码节点
  | 'api'         // API 调用节点
  | 'parallel'    // 并行执行节点 (ADK ParallelAgent)
  | 'loop'        // 循环节点 (ADK LoopAgent)
  | 'coordinator'; // 协调器节点 (ADK Coordinator pattern)

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
    description: '工作流起点',
    category: '基础节点',
    defaultInputs: 0,
    defaultOutputs: 1
  },
  llm: {
    type: 'llm',
    icon: '🤖',
    iconColor: 'bg-green-500',
    label: '大模型',
    description: '调用大语言模型',
    category: '运维节点',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  knowledge: {
    type: 'knowledge',
    icon: '📚',
    iconColor: 'bg-purple-500',
    label: '知识库',
    description: '检索知识库内容',
    category: '运维节点',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  agent: {
    type: 'agent',
    icon: '🎯',
    iconColor: 'bg-teal-500',
    label: '智能体',
    description: '执行智能体任务',
    category: '运维节点',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  condition: {
    type: 'condition',
    icon: '🔀',
    iconColor: 'bg-yellow-500',
    label: '条件判断',
    description: '根据条件分支执行',
    category: '分支节点',
    defaultInputs: 1,
    defaultOutputs: 2
  },
  merge: {
    type: 'merge',
    icon: '🔗',
    iconColor: 'bg-orange-500',
    label: '结果合并',
    description: '合并多个分支结果',
    category: '分支节点',
    defaultInputs: 2,
    defaultOutputs: 1
  },
  code: {
    type: 'code',
    icon: '💻',
    iconColor: 'bg-indigo-500',
    label: '代码执行',
    description: '执行自定义代码',
    category: '代码节点',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  api: {
    type: 'api',
    icon: '🌐',
    iconColor: 'bg-pink-500',
    label: 'API 调用',
    description: '调用外部 API',
    category: '代码节点',
    defaultInputs: 1,
    defaultOutputs: 1
  },
  end: {
    type: 'end',
    icon: '⏹️',
    iconColor: 'bg-red-500',
    label: '结束',
    description: '工作流终点',
    category: '基础节点',
    defaultInputs: 1,
    defaultOutputs: 0
  },
  // ADK Pattern Nodes
  parallel: {
    type: 'parallel',
    icon: '⚡',
    iconColor: 'bg-cyan-500',
    label: '并行执行',
    description: '并行执行多个子任务 (ADK ParallelAgent)',
    category: 'ADK 模式',
    defaultInputs: 1,
    defaultOutputs: 3
  },
  loop: {
    type: 'loop',
    icon: '🔄',
    iconColor: 'bg-amber-500',
    label: '循环执行',
    description: '循环执行直到满足条件 (ADK LoopAgent)',
    category: 'ADK 模式',
    defaultInputs: 1,
    defaultOutputs: 2
  },
  coordinator: {
    type: 'coordinator',
    icon: '🎛️',
    iconColor: 'bg-violet-500',
    label: '协调器',
    description: '智能路由和任务分发 (ADK Coordinator)',
    category: 'ADK 模式',
    defaultInputs: 1,
    defaultOutputs: 1
  }
};

// Group node types by category for the component library
export const nodeCategories = [
  {
    name: '基础节点',
    items: [nodeTypeConfigs.start, nodeTypeConfigs.end]
  },
  {
    name: '运维节点',
    items: [nodeTypeConfigs.llm, nodeTypeConfigs.knowledge, nodeTypeConfigs.agent]
  },
  {
    name: '分支节点',
    items: [nodeTypeConfigs.condition, nodeTypeConfigs.merge]
  },
  {
    name: '代码节点',
    items: [nodeTypeConfigs.code, nodeTypeConfigs.api]
  },
  {
    name: 'ADK 模式',
    items: [nodeTypeConfigs.parallel, nodeTypeConfigs.loop, nodeTypeConfigs.coordinator]
  }
];
