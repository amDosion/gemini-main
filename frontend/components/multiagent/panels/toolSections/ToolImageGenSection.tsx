/**
 * Tool 节点图片生成参数面板。
 *
 * 1:1 抽离自 `ToolNodeConfigPanel.tsx` isImageGen IIFE
 * （< 800 行合规拆分）。
 */

import React from 'react';
import { CustomNodeData } from '../../CustomNode';
import { getResolutionLabel } from '../../workflowResolution';

const RATIOS = ['1:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9'];

const TIERS = [
  { value: '1K', label: '1K 标准' },
  { value: '1.25K', label: '1.25K' },
  { value: '1.5K', label: '1.5K' },
  { value: '2K', label: '2K 高清' },
];

export interface ToolImageGenSectionProps {
  nodeData: CustomNodeData;
  updateNodeData: (patch: Partial<CustomNodeData>) => void;
}

export const ToolImageGenSection: React.FC<ToolImageGenSectionProps> = ({
  nodeData,
  updateNodeData,
}) => {
  const parsedArgs = ((): Record<string, unknown> => {
    try {
      const parsed = JSON.parse(nodeData.toolArgsTemplate || '{}');
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      /* ignore parse error */
    }
    return {};
  })();
  const updateToolArgs = (patch: Record<string, unknown>) => {
    updateNodeData({ toolArgsTemplate: JSON.stringify({ ...parsedArgs, ...patch }) });
  };

  const promptValue = String(parsedArgs.prompt ?? '');
  const tier = nodeData.toolResolutionTier || nodeData.toolImageSize || '1K';
  const ratio = nodeData.toolAspectRatio || '1:1';
  return (
    <div className="space-y-3 p-2.5 rounded-lg border border-pink-500/20 bg-pink-500/5">
      <div className="text-xs text-pink-300 font-medium">图片生成参数</div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">提示词</label>
        <textarea
          value={promptValue}
          onChange={(e) => updateToolArgs({ prompt: e.target.value || '{{input.task}}' })}
          rows={2}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
          placeholder="{{input.task}}"
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-xs text-slate-500 mb-1">宽高比</label>
          <select
            value={ratio}
            onChange={(e) => updateNodeData({ toolAspectRatio: e.target.value })}
            data-field-key="toolAspectRatio"
            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
          >
            {RATIOS.map((item) => (
              <option key={item} value={item}>
                {item} ({getResolutionLabel(tier, item)})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">分辨率</label>
          <select
            value={tier}
            onChange={(e) => updateNodeData({ toolResolutionTier: e.target.value })}
            data-field-key="toolResolutionTier"
            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
          >
            {TIERS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label} ({getResolutionLabel(item.value, ratio)})
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-xs text-slate-500 mb-1">数量</label>
          <select
            value={nodeData.toolNumberOfImages ?? ''}
            onChange={(e) =>
              updateNodeData({
                toolNumberOfImages: e.target.value ? Number(e.target.value) : undefined,
              })
            }
            data-field-key="toolNumberOfImages"
            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
          >
            <option value="">默认(1)</option>
            <option value="1">1 张</option>
            <option value="2">2 张</option>
            <option value="3">3 张</option>
            <option value="4">4 张</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">风格</label>
          <select
            value={nodeData.toolImageStyle || ''}
            onChange={(e) => updateNodeData({ toolImageStyle: e.target.value })}
            data-field-key="toolImageStyle"
            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
          >
            <option value="">默认</option>
            <option value="photorealistic">写实</option>
            <option value="digital_art">数字艺术</option>
            <option value="anime">动漫</option>
            <option value="watercolor">水彩</option>
            <option value="oil_painting">油画</option>
          </select>
        </div>
      </div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">输出格式</label>
        <select
          value={nodeData.toolOutputMimeType || ''}
          onChange={(e) => updateNodeData({ toolOutputMimeType: e.target.value })}
          data-field-key="toolOutputMimeType"
          className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
        >
          <option value="">默认(PNG)</option>
          <option value="image/png">PNG</option>
          <option value="image/jpeg">JPEG</option>
          <option value="image/webp">WebP</option>
        </select>
      </div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">反向提示词</label>
        <input
          type="text"
          value={nodeData.toolNegativePrompt || ''}
          onChange={(e) => updateNodeData({ toolNegativePrompt: e.target.value })}
          data-field-key="toolNegativePrompt"
          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
          placeholder="不希望出现的内容..."
        />
      </div>
      <label className="flex items-center gap-2 text-xs text-slate-300">
        <input
          type="checkbox"
          checked={Boolean(nodeData.toolPromptExtend)}
          onChange={(e) => updateNodeData({ toolPromptExtend: e.target.checked })}
          data-field-key="toolPromptExtend"
          className="accent-teal-500"
        />
        启用提示词优化（provider 支持时生效）
      </label>
      <label className="flex items-center gap-2 text-xs text-slate-300">
        <input
          type="checkbox"
          checked={nodeData.toolAddMagicSuffix !== false}
          onChange={(e) => updateNodeData({ toolAddMagicSuffix: e.target.checked })}
          data-field-key="toolAddMagicSuffix"
          className="accent-teal-500"
        />
        启用提示词增强后缀（provider 支持时生效）
      </label>
    </div>
  );
};
