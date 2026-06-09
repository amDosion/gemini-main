/**
 * Agent 节点图片编辑参数面板。
 *
 * 1:1 抽离自 `AgentNodeConfigPanel.tsx` 图片编辑 IIFE
 * （< 800 行合规拆分）。
 */

import React from 'react';
import { Upload } from 'lucide-react';
import { CustomNodeData } from '../../CustomNode';
import { getResolutionLabel } from '../../workflowResolution';
import { readInlineFilesAsDataUrls, reportInlineUploadError } from '../../uploadHandlers';
import { InlineReferenceImagePreview } from '../InlineReferenceImagePreview';

export interface AgentImageEditSectionProps {
  nodeData: CustomNodeData;
  updateNodeData: (patch: Partial<CustomNodeData>) => void;
}

const _ratios = ['1:1', '2:3', '3:2', '3:4', '4:3', '9:16', '16:9', '21:9'];
const _tiers = [
  { v: '1K', l: '1K 标准' },
  { v: '2K', l: '2K 高清' },
  { v: '4K', l: '4K 超清' },
];

export const AgentImageEditSection: React.FC<AgentImageEditSectionProps> = ({
  nodeData,
  updateNodeData,
}) => {
  const _tier = nodeData.agentResolutionTier || '1K';
  const _ratio = nodeData.agentAspectRatio || '1:1';
  const _hasRef = !!nodeData.agentReferenceImageUrl;
  return (
    <div className="space-y-3 p-2.5 rounded-lg border border-purple-500/20 bg-purple-500/5">
      <div className="text-xs text-purple-300 font-medium">图片编辑参数</div>
      {/* 参考图片上传 */}
      <div>
        <label className="block text-xs text-slate-500 mb-1">
          参考图片 <span className="text-red-400">*</span>
        </label>
        <InlineReferenceImagePreview
          imageUrl={nodeData.agentReferenceImageUrl}
          borderClassName="border-purple-500/30"
          onClear={() => updateNodeData({ agentReferenceImageUrl: '' })}
        />
        <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-purple-500/40 rounded-lg cursor-pointer hover:border-purple-500/60 transition-colors">
          <Upload size={12} className="text-purple-400" />
          <span className="text-xs text-purple-300">{_hasRef ? '更换图片' : '上传参考图片'}</span>
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              try {
                const [encoded] = await readInlineFilesAsDataUrls([f], '参考图片');
                updateNodeData({ agentReferenceImageUrl: encoded || '' });
              } catch (err) {
                reportInlineUploadError('参考图片读取失败', err);
              }
              e.target.value = '';
            }}
          />
        </label>
        <input
          type="text"
          value={
            !nodeData.agentReferenceImageUrl?.startsWith('data:')
              ? nodeData.agentReferenceImageUrl || ''
              : ''
          }
          onChange={(e) => updateNodeData({ agentReferenceImageUrl: e.target.value })}
          data-field-key="agentReferenceImageUrl"
          className="mt-1.5 w-full px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-400 font-mono focus:outline-none focus:border-purple-500/50"
          placeholder="或输入 URL / {{prev.output.imageUrl}}"
        />
      </div>
      {/* 编辑指令 */}
      <div>
        <label className="block text-xs text-slate-500 mb-1">编辑指令</label>
        <textarea
          value={nodeData.agentEditPrompt || ''}
          onChange={(e) => updateNodeData({ agentEditPrompt: e.target.value })}
          rows={2}
          data-field-key="agentEditPrompt"
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-purple-500/50 resize-none"
          placeholder="描述你想要的编辑效果..."
        />
      </div>
      {/* 宽高比 + 分辨率（联动） */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-xs text-slate-500 mb-1">宽高比</label>
          <select
            value={_ratio}
            onChange={(e) => updateNodeData({ agentAspectRatio: e.target.value })}
            data-field-key="agentAspectRatio"
            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
          >
            <option value="">保持原比例</option>
            {_ratios.map((r) => (
              <option key={r} value={r}>
                {r} ({getResolutionLabel(_tier, r)})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">分辨率</label>
          <select
            value={_tier}
            onChange={(e) => updateNodeData({ agentResolutionTier: e.target.value })}
            data-field-key="agentResolutionTier"
            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
          >
            {_tiers.map((t) => (
              <option key={t.v} value={t.v}>
                {t.l} ({getResolutionLabel(t.v, _ratio || '1:1')})
              </option>
            ))}
          </select>
        </div>
      </div>
      {/* 数量 + 输出格式 */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-xs text-slate-500 mb-1">数量</label>
          <select
            value={nodeData.agentNumberOfImages ?? ''}
            onChange={(e) =>
              updateNodeData({
                agentNumberOfImages: e.target.value ? Number(e.target.value) : undefined,
              })
            }
            data-field-key="agentNumberOfImages"
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
          <label className="block text-xs text-slate-500 mb-1">输出格式</label>
          <select
            value={nodeData.agentOutputMimeType || ''}
            onChange={(e) => updateNodeData({ agentOutputMimeType: e.target.value })}
            data-field-key="agentOutputMimeType"
            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
          >
            <option value="">默认(PNG)</option>
            <option value="image/png">PNG</option>
            <option value="image/jpeg">JPEG</option>
            <option value="image/webp">WebP</option>
          </select>
        </div>
      </div>
      <label className="flex items-center gap-2 text-xs text-slate-300">
        <input
          type="checkbox"
          checked={Boolean(nodeData.agentPromptExtend)}
          onChange={(e) => updateNodeData({ agentPromptExtend: e.target.checked })}
          data-field-key="agentPromptExtend"
          className="accent-teal-500"
        />
        启用编辑提示词优化（provider 支持时生效）
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="flex items-center gap-2 text-xs text-slate-300">
          <input
            type="checkbox"
            checked={nodeData.agentPreserveProductIdentity !== false}
            onChange={(e) => updateNodeData({ agentPreserveProductIdentity: e.target.checked })}
            data-field-key="agentPreserveProductIdentity"
            className="accent-purple-500"
          />
          保留主体
        </label>
        <div>
          <label className="block text-xs text-slate-500 mb-1">重试次数</label>
          <select
            value={nodeData.agentImageEditMaxRetries ?? 1}
            onChange={(e) => updateNodeData({ agentImageEditMaxRetries: Number(e.target.value) })}
            data-field-key="agentImageEditMaxRetries"
            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-purple-500/50"
          >
            <option value="0">0</option>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
          </select>
        </div>
      </div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">匹配阈值（50-95）</label>
        <input
          type="number"
          min={50}
          max={95}
          step={1}
          value={nodeData.agentProductMatchThreshold ?? 70}
          onChange={(e) => {
            const raw = Number(e.target.value);
            const safe = Number.isFinite(raw) ? Math.max(50, Math.min(95, Math.round(raw))) : 70;
            updateNodeData({ agentProductMatchThreshold: safe });
          }}
          data-field-key="agentProductMatchThreshold"
          className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-purple-500/50"
        />
      </div>
    </div>
  );
};
