/**
 * Agent 节点图片生成参数面板。
 *
 * 1:1 抽离自 `AgentNodeConfigPanel.tsx` 图片生成 IIFE
 * （< 800 行合规拆分）。
 */

import React from 'react';
import { CustomNodeData } from '../../CustomNode';
import { getResolutionLabel } from '../../workflowResolution';

export interface AgentImageGenSectionProps {
  nodeData: CustomNodeData;
  updateNodeData: (patch: Partial<CustomNodeData>) => void;
}

export const AgentImageGenSection: React.FC<AgentImageGenSectionProps> = ({
  nodeData,
  updateNodeData,
}) => {
            const _tier = nodeData.agentResolutionTier || '1K';
            const _ratio = nodeData.agentAspectRatio || '1:1';
            const _ratios = [
              '1:1',
              '2:3',
              '3:2',
              '3:4',
              '4:3',
              '4:5',
              '5:4',
              '9:16',
              '16:9',
              '21:9',
            ];
            const _tiers = [
              { v: '1K', l: '1K 标准' },
              { v: '1.5K', l: '1.5K' },
              { v: '2K', l: '2K 高清' },
              { v: '4K', l: '4K 超清' },
            ];
            return (
              <div className="space-y-3 p-2.5 rounded-lg border border-pink-500/20 bg-pink-500/5">
                <div className="text-xs text-pink-300 font-medium">图片生成参数</div>
                {/* 宽高比（联动显示像素） */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">宽高比</label>
                  <select
                    value={_ratio}
                    onChange={(e) => updateNodeData({ agentAspectRatio: e.target.value })}
                    data-field-key="agentAspectRatio"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  >
                    {_ratios.map((r) => (
                      <option key={r} value={r}>
                        {r} ({getResolutionLabel(_tier, r)})
                      </option>
                    ))}
                  </select>
                </div>
                {/* 分辨率档位（联动显示像素） */}
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
                        {t.l} ({getResolutionLabel(t.v, _ratio)})
                      </option>
                    ))}
                  </select>
                </div>
                {/* 数量 + 风格 */}
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
                    <label className="block text-xs text-slate-500 mb-1">风格</label>
                    <select
                      value={nodeData.agentImageStyle || ''}
                      onChange={(e) => updateNodeData({ agentImageStyle: e.target.value })}
                      data-field-key="agentImageStyle"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                    >
                      <option value="">无风格</option>
                      <option value="Photorealistic">写实</option>
                      <option value="Anime">动漫</option>
                      <option value="Digital Art">数字艺术</option>
                      <option value="Oil Painting">油画</option>
                      <option value="Cyberpunk">赛博朋克</option>
                      <option value="Watercolor">水彩</option>
                    </select>
                  </div>
                </div>
                {/* 输出格式 + Seed */}
                <div className="grid grid-cols-2 gap-2">
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
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Seed</label>
                    <div className="flex gap-1">
                      <input
                        type="number"
                        value={nodeData.agentSeed ?? -1}
                        onChange={(e) =>
                          updateNodeData({ agentSeed: parseInt(e.target.value) || -1 })
                        }
                        data-field-key="agentSeed"
                        className="flex-1 px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono focus:outline-none focus:border-teal-500/50"
                        placeholder="-1 随机"
                      />
                      <button
                        onClick={() => updateNodeData({ agentSeed: -1 })}
                        className="px-1.5 bg-slate-800 border border-slate-700 rounded hover:bg-slate-700 text-slate-400 text-xs"
                        title="随机"
                      >
                        🎲
                      </button>
                    </div>
                  </div>
                </div>
                {/* 反向提示词 */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">反向提示词</label>
                  <input
                    type="text"
                    value={nodeData.agentNegativePrompt || ''}
                    onChange={(e) => updateNodeData({ agentNegativePrompt: e.target.value })}
                    data-field-key="agentNegativePrompt"
                    className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                    placeholder="blurry, bad quality, distorted..."
                  />
                </div>
                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={Boolean(nodeData.agentPromptExtend)}
                    onChange={(e) => updateNodeData({ agentPromptExtend: e.target.checked })}
                    data-field-key="agentPromptExtend"
                    className="accent-teal-500"
                  />
                  启用提示词优化（provider 支持时生效）
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={nodeData.agentAddMagicSuffix !== false}
                    onChange={(e) => updateNodeData({ agentAddMagicSuffix: e.target.checked })}
                    data-field-key="agentAddMagicSuffix"
                    className="accent-teal-500"
                  />
                  启用提示词增强后缀（provider 支持时生效）
                </label>
              </div>
            );
};
