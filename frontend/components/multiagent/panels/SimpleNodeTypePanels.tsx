/**
 * 简单节点类型编辑面板集合（condition / router / parallel / merge / loop / human）。
 *
 * 1:1 抽离自 `PropertiesPanel.tsx` 的 renderNodeConfigEditor 内 6 个 if-branch
 * （JIRA-frontend-view-decomposition.md P0 #1 续 — 主组件大刀阔斧拆分）。
 *
 * 设计：每个 panel 仅依赖 nodeData 字段 + updateNodeData 回调，无需任何 closure。
 * 这是 PropertiesPanel 中最简单的一批 node-type 编辑器；agent / tool / end / start /
 * input_* 因依赖更多 closure（providers / schema / refs）暂未在此处抽离，
 * 留待后续 sub-ticket（参见 plan 备注：主组件 ~3000 行分两轮）。
 */

import React from 'react';
import { Info } from 'lucide-react';
import { CustomNodeData } from '../CustomNode';

interface BasePanelProps {
  nodeData: CustomNodeData;
  updateNodeData: (patch: Partial<CustomNodeData>) => void;
}

/** condition 节点：条件表达式 + True/False 出口提示 */
export const ConditionNodePanel: React.FC<BasePanelProps> = ({ nodeData, updateNodeData }) => (
  <div className="space-y-4">
    <div>
      <label className="block text-xs text-slate-500 mb-1">条件表达式</label>
      <div className="flex items-start gap-1 mb-1.5">
        <Info size={10} className="text-slate-600 mt-0.5 flex-shrink-0" />
        <span className="text-[10px] text-slate-600">
          支持模板变量，例如 {'{{prev.output.text}}'}
        </span>
      </div>
      <textarea
        value={nodeData.expression || ''}
        onChange={(e) => updateNodeData({ expression: e.target.value })}
        rows={3}
        data-field-key="expression"
        className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 font-mono focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
        placeholder="{{prev.output.text}}.includes('通过')"
      />
    </div>
    <div className="p-2.5 rounded-lg border border-slate-700 bg-slate-800/50 text-[11px] text-slate-400">
      True 分支使用上方输出口，False 分支使用下方输出口。
    </div>
  </div>
);

/** router 节点：路由策略（intent/keyword/llm）+ 路由提示词 */
export const RouterNodePanel: React.FC<BasePanelProps> = ({ nodeData, updateNodeData }) => (
  <div className="space-y-4">
    <div>
      <label className="block text-xs text-slate-500 mb-1.5">路由策略</label>
      <select
        value={nodeData.routerStrategy || 'intent'}
        onChange={(e) =>
          updateNodeData({
            routerStrategy: e.target.value as CustomNodeData['routerStrategy'],
          })
        }
        data-field-key="routerStrategy"
        className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
      >
        <option value="intent">Intent（推荐）</option>
        <option value="keyword">Keyword</option>
        <option value="llm">LLM 分类</option>
      </select>
    </div>
    <div>
      <label className="block text-xs text-slate-500 mb-1">路由提示词</label>
      <textarea
        value={nodeData.routerPrompt || ''}
        onChange={(e) => updateNodeData({ routerPrompt: e.target.value })}
        rows={3}
        data-field-key="routerPrompt"
        className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
        placeholder="根据任务意图将输入分发到最合适的分支..."
      />
    </div>
  </div>
);

/** parallel 节点：汇聚模式 + 超时（秒） */
export const ParallelNodePanel: React.FC<BasePanelProps> = ({ nodeData, updateNodeData }) => (
  <div className="space-y-4">
    <div>
      <label className="block text-xs text-slate-500 mb-1.5">汇聚模式</label>
      <select
        value={nodeData.joinMode || 'wait_all'}
        onChange={(e) => updateNodeData({ joinMode: e.target.value as CustomNodeData['joinMode'] })}
        data-field-key="joinMode"
        className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
      >
        <option value="wait_all">等待全部分支完成</option>
        <option value="race_first">任一分支先完成即返回</option>
      </select>
    </div>
    <div>
      <label className="block text-xs text-slate-500 mb-1.5">超时（秒）</label>
      <input
        type="number"
        min={5}
        value={nodeData.timeoutSeconds ?? 60}
        onChange={(e) =>
          updateNodeData({ timeoutSeconds: Math.max(5, Number(e.target.value) || 60) })
        }
        data-field-key="timeoutSeconds"
        className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
      />
    </div>
  </div>
);

/** merge 节点：结果合并策略 */
export const MergeNodePanel: React.FC<BasePanelProps> = ({ nodeData, updateNodeData }) => (
  <div className="space-y-4">
    <div>
      <label className="block text-xs text-slate-500 mb-1.5">结果合并策略</label>
      <select
        value={nodeData.mergeStrategy || 'append'}
        onChange={(e) =>
          updateNodeData({ mergeStrategy: e.target.value as CustomNodeData['mergeStrategy'] })
        }
        data-field-key="mergeStrategy"
        className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
      >
        <option value="append">顺序拼接</option>
        <option value="json_merge">JSON 合并</option>
        <option value="latest">选择最新结果</option>
      </select>
    </div>
  </div>
);

/** loop 节点：循环条件 + 最大迭代次数 */
export const LoopNodePanel: React.FC<BasePanelProps> = ({ nodeData, updateNodeData }) => (
  <div className="space-y-4">
    <div>
      <label className="block text-xs text-slate-500 mb-1.5">循环条件</label>
      <textarea
        value={nodeData.loopCondition || ''}
        onChange={(e) => updateNodeData({ loopCondition: e.target.value })}
        rows={2}
        data-field-key="loopCondition"
        className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 font-mono focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
        placeholder="{{prev.output.retry}} < 3"
      />
    </div>
    <div>
      <label className="block text-xs text-slate-500 mb-1.5">最大迭代次数</label>
      <input
        type="number"
        min={1}
        value={nodeData.maxIterations ?? 3}
        onChange={(e) =>
          updateNodeData({ maxIterations: Math.max(1, Number(e.target.value) || 1) })
        }
        data-field-key="maxIterations"
        className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
      />
    </div>
  </div>
);

/** human 节点：人工审核提示 */
export const HumanNodePanel: React.FC<BasePanelProps> = ({ nodeData, updateNodeData }) => (
  <div className="space-y-4">
    <div>
      <label className="block text-xs text-slate-500 mb-1.5">人工审核提示</label>
      <textarea
        value={nodeData.approvalPrompt || ''}
        onChange={(e) => updateNodeData({ approvalPrompt: e.target.value })}
        rows={3}
        data-field-key="approvalPrompt"
        className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
        placeholder="请确认输出是否满足业务规则..."
      />
    </div>
    <label className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
      <input
        type="checkbox"
        checked={nodeData.autoApprove === true}
        onChange={(e) => updateNodeData({ autoApprove: e.target.checked })}
        data-field-key="autoApprove"
        className="mt-0.5 h-4 w-4 rounded border-amber-400/50 bg-slate-900 text-amber-500 focus:ring-amber-500/30"
      />
      <span>
        显式自动通过。当前还没有真实人工确认流程，未开启时该节点不能执行或保存为模板。
      </span>
    </label>
  </div>
);
