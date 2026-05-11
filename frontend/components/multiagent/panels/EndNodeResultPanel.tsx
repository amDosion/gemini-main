/**
 * end 节点结束出口面板:内联结果预览(图/视频/音频/文本) + "打开结束结果"按钮。
 *
 * 1:1 抽离自 `PropertiesPanel.tsx` renderResultNodeConfig L3638-3734
 * (JIRA-frontend-view-decomposition.md P0 #1 续 — 主组件瘦身)。
 *
 * 注:与 ResultSection.tsx 不同 — ResultSection 用于通用节点的执行结果可视化,
 * 本 panel 专门处理 end 节点的"结束出口"语义(含 dispatchScopedWorkflowEvent
 * 触发独立结果面板)。
 */

import React from 'react';
import { CustomNodeData } from '../CustomNode';
import type { NodeStatus } from '../types';
import { dispatchScopedWorkflowEvent } from '../workflowEditorUtils';

export interface EndNodeResultPanelProps {
  nodeData: CustomNodeData;
  selectedNodeId: string;
  status: NodeStatus;
  resultPreviewUrls: string[];
  resultPreviewVideoUrls: string[];
  resultPreviewAudioUrls: string[];
  resultPreviewText: string;
}

export const EndNodeResultPanel: React.FC<EndNodeResultPanelProps> = ({
  nodeData,
  selectedNodeId,
  status,
  resultPreviewUrls,
  resultPreviewVideoUrls,
  resultPreviewAudioUrls,
  resultPreviewText,
}) => {
  const hasInlineResult = nodeData.result !== undefined && nodeData.result !== null;

  return (
    <div className="space-y-4">
      <div className="p-2.5 rounded-lg border border-rose-500/20 bg-rose-500/5">
        <div className="text-xs text-rose-300 font-medium">结束出口配置</div>
        <div className="mt-1 text-[10px] text-slate-500">
          结束节点内置最终结果预览，并可打开独立结果面板查看完整输出。
        </div>
      </div>
      {hasInlineResult ? (
        <div className="p-2.5 rounded-lg border border-indigo-500/30 bg-indigo-500/10 space-y-2">
          <div className="text-xs text-indigo-200 font-medium">结束结果预览</div>
          {resultPreviewUrls.length > 0 && (
            <div>
              <div className="text-[11px] text-slate-400 mb-1">
                结果图片共 {resultPreviewUrls.length} 张
              </div>
              <div className="grid grid-cols-4 gap-2 max-h-56 overflow-y-auto pr-1">
                {resultPreviewUrls.map((imageUrl, index) => (
                  <img
                    key={`${selectedNodeId}-end-result-${index}`}
                    src={imageUrl}
                    alt={`end-result-${index + 1}`}
                    className="w-full h-16 object-cover rounded border border-slate-700 bg-slate-900"
                  />
                ))}
              </div>
            </div>
          )}
          {resultPreviewVideoUrls.length > 0 && (
            <div>
              <div className="text-[11px] text-slate-400 mb-1">
                结果视频共 {resultPreviewVideoUrls.length} 条
              </div>
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {resultPreviewVideoUrls.map((videoUrl, index) => (
                  <video
                    key={`${selectedNodeId}-end-video-${index}`}
                    src={videoUrl}
                    controls
                    className="w-full rounded border border-slate-700 bg-slate-900"
                  />
                ))}
              </div>
            </div>
          )}
          {resultPreviewAudioUrls.length > 0 && (
            <div>
              <div className="text-[11px] text-slate-400 mb-1">
                结果音频共 {resultPreviewAudioUrls.length} 条
              </div>
              <div className="space-y-2 max-h-44 overflow-y-auto pr-1">
                {resultPreviewAudioUrls.map((audioUrl, index) => (
                  <audio
                    key={`${selectedNodeId}-end-audio-${index}`}
                    src={audioUrl}
                    controls
                    className="w-full"
                  />
                ))}
              </div>
            </div>
          )}
          {resultPreviewText && (
            <pre className="text-[11px] text-slate-300 whitespace-pre-wrap break-words max-h-[160px] overflow-y-auto">
              {resultPreviewText}
            </pre>
          )}
        </div>
      ) : (
        <div className="p-2.5 rounded-lg border border-slate-700 bg-slate-800/50 text-[11px] text-slate-400">
          当前还没有结束结果，执行工作流后会自动显示。
        </div>
      )}
      {status === 'failed' && nodeData.error && (
        <div className="p-2.5 rounded-lg border border-red-500/30 bg-red-500/10 text-[11px] text-red-300 whitespace-pre-wrap break-words">
          {nodeData.error}
        </div>
      )}
      <button
        onClick={(event) => {
          dispatchScopedWorkflowEvent('workflow:end-request', event.currentTarget, {
            nodeId: selectedNodeId,
          });
        }}
        className="w-full px-3 py-2 text-xs rounded-lg border border-rose-500/40 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20 transition-colors"
      >
        打开结束结果
      </button>
    </div>
  );
};
