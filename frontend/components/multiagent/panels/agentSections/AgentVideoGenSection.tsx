/**
 * Agent 节点视频生成参数面板。
 *
 * 1:1 抽离自 `AgentNodeConfigPanel.tsx` L1046-1443
 * （< 800 行合规拆分）。
 */

import React from 'react';
import { CustomNodeData } from '../../CustomNode';
import { useModeControlsSchema } from '../../../../hooks/useModeControlsSchema';
import {
  buildVideoControlContract,
  getVideoExtensionOptions,
} from '../../../../utils/videoControlSchema';
import {
  normalizeWorkflowVideoResolutionSelection,
  normalizeWorkflowVideoSecondsSelection,
  normalizeWorkflowVideoExtensionSelection,
  getWorkflowVideoResolutionLabel,
} from '../../workflowResolution';

export interface AgentVideoGenSectionProps {
  nodeData: CustomNodeData;
  updateNodeData: (patch: Partial<CustomNodeData>) => void;
  workflowVideoSchema: ReturnType<typeof useModeControlsSchema>['schema'];
  workflowVideoControlContract: ReturnType<typeof buildVideoControlContract>;
}

export const AgentVideoGenSection: React.FC<AgentVideoGenSectionProps> = ({
  nodeData,
  updateNodeData,
  workflowVideoSchema,
  workflowVideoControlContract,
}) => {
            const aspectRatioOptions =
              workflowVideoControlContract.validAspectRatios.length > 0
                ? workflowVideoControlContract.validAspectRatios
                : ['16:9', '9:16'];
            const videoAspectRatio = aspectRatioOptions.includes(
              String(nodeData.agentAspectRatio || '').trim()
            )
              ? String(nodeData.agentAspectRatio || '').trim()
              : workflowVideoControlContract.defaultAspectRatio;
            const resolutionOptions = workflowVideoSchema?.resolutionTiers?.length
              ? workflowVideoSchema.resolutionTiers
              : [
                  { value: '720p', label: '720p', baseResolution: '1280×720' },
                  { value: '1080p', label: '1080p', baseResolution: '1920×1080' },
                  { value: '4k', label: '4k', baseResolution: '3840×2160' },
                ];
            const resolutionValues = resolutionOptions.map((item) => item.value);
            const videoResolution = normalizeWorkflowVideoResolutionSelection(
              nodeData.agentResolutionTier,
              resolutionValues,
              workflowVideoControlContract.defaultResolution
            );
            const durationOptions =
              workflowVideoControlContract.validSeconds.length > 0
                ? workflowVideoControlContract.validSeconds
                : [workflowVideoControlContract.defaultVideoSeconds];
            const videoDuration = normalizeWorkflowVideoSecondsSelection(
              nodeData.agentVideoDurationSeconds,
              durationOptions,
              workflowVideoControlContract.defaultVideoSeconds
            );
            const inputStrategyOptions = workflowVideoSchema?.videoContract?.inputStrategies ?? [];
            const inputStrategyValues = inputStrategyOptions.map((item) => item.id);
            const videoInputStrategy = inputStrategyValues.includes(
              String(nodeData.agentVideoInputStrategy || '').trim()
            )
              ? String(nodeData.agentVideoInputStrategy || '').trim()
              : inputStrategyValues[0] || '';
            const supportsDrivingAudio =
              workflowVideoSchema?.videoContract?.attachmentSlots?.some(
                (slot) =>
                  slot.enabled !== false &&
                  (slot.kind === 'audio' || slot.name === 'driving_audio')
              ) ?? false;
            const extensionOptions = getVideoExtensionOptions(
              workflowVideoControlContract,
              videoDuration
            );
            const validExtensionCounts = extensionOptions.map((item) => item.count);
            const videoExtensionCount = normalizeWorkflowVideoExtensionSelection(
              nodeData.agentVideoExtensionCount,
              validExtensionCounts.length > 0 ? validExtensionCounts : [0],
              workflowVideoControlContract.defaultVideoExtensionCount
            );
            const continueFromPreviousVideo = Boolean(nodeData.agentContinueFromPreviousVideo);
            const continueFromPreviousLastFrame = Boolean(
              nodeData.agentContinueFromPreviousLastFrame
            );
            const promptExtendMandatory =
              workflowVideoControlContract.fieldPolicies.enhancePromptMandatory;
            const promptExtendValue = promptExtendMandatory
              ? true
              : Boolean(
                  nodeData.agentPromptExtend ?? workflowVideoControlContract.defaultEnhancePrompt
                );
            const generateAudioForcedValue =
              workflowVideoControlContract.fieldPolicies.generateAudioForcedValue;
            const generateAudioValue =
              typeof generateAudioForcedValue === 'boolean'
                ? generateAudioForcedValue
                : Boolean(
                    nodeData.agentGenerateAudio ?? workflowVideoControlContract.defaultGenerateAudio
                  );
            const subtitleModeOptions =
              workflowVideoControlContract.validSubtitleModes.length > 0
                ? workflowVideoControlContract.validSubtitleModes
                : ['none'];
            const subtitleModeValue = subtitleModeOptions.includes(
              String(nodeData.agentSubtitleMode || '').trim()
            )
              ? String(nodeData.agentSubtitleMode || '').trim()
              : workflowVideoControlContract.defaultSubtitleMode;
            const subtitleLanguageOptions = workflowVideoControlContract.validSubtitleLanguages;
            const subtitleLanguageValue = subtitleLanguageOptions.includes(
              String(nodeData.agentSubtitleLanguage || '').trim()
            )
              ? String(nodeData.agentSubtitleLanguage || '').trim()
              : workflowVideoControlContract.defaultSubtitleLanguage;
            const extensionSummary = extensionOptions.find(
              (item) => item.count === videoExtensionCount
            );
            return (
              <div className="space-y-3 p-2.5 rounded-lg border border-fuchsia-500/20 bg-fuchsia-500/5">
                <div className="text-xs text-fuchsia-300 font-medium">视频生成参数</div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">宽高比</label>
                    <select
                      value={videoAspectRatio}
                      onChange={(e) => updateNodeData({ agentAspectRatio: e.target.value })}
                      data-field-key="agentAspectRatio"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    >
                      {aspectRatioOptions.map((item) => (
                        <option key={item} value={item}>
                          {item} {item === '16:9' ? '横屏' : item === '9:16' ? '竖屏' : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">分辨率</label>
                    <select
                      value={videoResolution}
                      onChange={(e) => updateNodeData({ agentResolutionTier: e.target.value })}
                      data-field-key="agentResolutionTier"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    >
                      {resolutionOptions.map((item) => (
                        <option key={item.value} value={item.value}>
                          {getWorkflowVideoResolutionLabel(
                            videoAspectRatio,
                            item.value,
                            workflowVideoSchema
                          )}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">时长（秒）</label>
                    <select
                      value={videoDuration}
                      onChange={(e) => {
                        const nextSeconds = e.target.value;
                        const nextExtensionOptions = getVideoExtensionOptions(
                          workflowVideoControlContract,
                          nextSeconds
                        );
                        updateNodeData({
                          agentVideoDurationSeconds: Number(nextSeconds),
                          agentVideoExtensionCount: normalizeWorkflowVideoExtensionSelection(
                            nodeData.agentVideoExtensionCount,
                            nextExtensionOptions.map((item) => item.count),
                            workflowVideoControlContract.defaultVideoExtensionCount
                          ),
                        });
                      }}
                      data-field-key="agentVideoDurationSeconds"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    >
                      {durationOptions.map((item) => (
                        <option key={item} value={item}>
                          {item}s
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                {inputStrategyOptions.length > 0 && (
                  <div>
                    <label className="block text-xs text-slate-500 mb-1" htmlFor="agent-video-input-strategy">
                      输入方式
                    </label>
                    <select
                      id="agent-video-input-strategy"
                      value={videoInputStrategy}
                      onChange={(e) => updateNodeData({ agentVideoInputStrategy: e.target.value })}
                      data-field-key="agentVideoInputStrategy"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    >
                      {inputStrategyOptions.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.label || item.id}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {extensionOptions.length > 0 && (
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">延长次数</label>
                      <select
                        value={String(videoExtensionCount)}
                        onChange={(e) =>
                          updateNodeData({ agentVideoExtensionCount: Number(e.target.value) })
                        }
                        data-field-key="agentVideoExtensionCount"
                        className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                      >
                        {extensionOptions.map((item) => (
                          <option key={item.count} value={item.count}>
                            {item.count === 0 ? '不延长' : `延长 ${item.count} 次`}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="rounded border border-fuchsia-500/20 bg-slate-900/40 px-2.5 py-1.5">
                      <div className="text-[10px] text-slate-500">预计总时长</div>
                      <div className="text-xs text-slate-200">
                        {extensionSummary
                          ? `${extensionSummary.totalSeconds}s`
                          : `${videoDuration}s`}
                      </div>
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <label className="flex items-center gap-2 text-xs text-slate-300">
                    <input
                      type="checkbox"
                      checked={promptExtendValue}
                      disabled={promptExtendMandatory}
                      onChange={(e) => updateNodeData({ agentPromptExtend: e.target.checked })}
                      data-field-key="agentPromptExtend"
                      className="accent-fuchsia-500 disabled:opacity-60"
                    />
                    AI 增强提示词
                  </label>
                  {workflowVideoControlContract.fieldPolicies.generateAudioAvailable && (
                    <label className="flex items-center gap-2 text-xs text-slate-300">
                      <input
                        type="checkbox"
                        checked={generateAudioValue}
                        disabled={typeof generateAudioForcedValue === 'boolean'}
                        onChange={(e) => updateNodeData({ agentGenerateAudio: e.target.checked })}
                        data-field-key="agentGenerateAudio"
                        className="accent-fuchsia-500 disabled:opacity-60"
                      />
                      生成音频
                    </label>
                  )}
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">分镜提示词（可选）</label>
                  <textarea
                    value={nodeData.agentStoryboardPrompt || ''}
                    onChange={(e) => updateNodeData({ agentStoryboardPrompt: e.target.value })}
                    data-field-key="agentStoryboardPrompt"
                    rows={4}
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50 resize-y"
                    placeholder="Shot 1: macro lace cuff... Shot 2: styling reveal..."
                  />
                </div>
                {subtitleModeOptions.length > 0 && (
                  <>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">字幕模式</label>
                        <select
                          value={subtitleModeValue}
                          onChange={(e) => updateNodeData({ agentSubtitleMode: e.target.value })}
                          data-field-key="agentSubtitleMode"
                          className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                        >
                          {subtitleModeOptions.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </div>
                      {subtitleLanguageOptions.length > 0 && subtitleModeValue !== 'none' && (
                        <div>
                          <label className="block text-xs text-slate-500 mb-1">字幕语言</label>
                          <select
                            value={subtitleLanguageValue}
                            onChange={(e) =>
                              updateNodeData({ agentSubtitleLanguage: e.target.value })
                            }
                            data-field-key="agentSubtitleLanguage"
                            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                          >
                            {subtitleLanguageOptions.map((item) => (
                              <option key={item} value={item}>
                                {item}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>
                    {subtitleModeValue !== 'none' && (
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">
                          字幕脚本（可选）
                        </label>
                        <textarea
                          value={nodeData.agentSubtitleScript || ''}
                          onChange={(e) => updateNodeData({ agentSubtitleScript: e.target.value })}
                          data-field-key="agentSubtitleScript"
                          rows={3}
                          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50 resize-y"
                          placeholder="每行一句字幕，或留空让模型按分镜生成。"
                        />
                      </div>
                    )}
                  </>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Seed</label>
                    <input
                      type="number"
                      value={nodeData.agentSeed ?? workflowVideoControlContract.defaultSeed}
                      onChange={(e) => updateNodeData({ agentSeed: Number(e.target.value) || 0 })}
                      data-field-key="agentSeed"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono focus:outline-none focus:border-fuchsia-500/50"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">反向提示词</label>
                    <input
                      type="text"
                      value={nodeData.agentNegativePrompt || ''}
                      onChange={(e) => updateNodeData({ agentNegativePrompt: e.target.value })}
                      data-field-key="agentNegativePrompt"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                      placeholder="避免出现的画面元素..."
                    />
                  </div>
                </div>
                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={continueFromPreviousVideo}
                    onChange={(e) =>
                      updateNodeData({
                        agentContinueFromPreviousVideo: e.target.checked,
                        ...(e.target.checked ? { agentContinueFromPreviousLastFrame: false } : {}),
                      })
                    }
                    data-field-key="agentContinueFromPreviousVideo"
                    className="accent-fuchsia-500"
                  />
                  续接上一段视频结果
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={continueFromPreviousLastFrame}
                    onChange={(e) =>
                      updateNodeData({
                        agentContinueFromPreviousLastFrame: e.target.checked,
                        ...(e.target.checked ? { agentContinueFromPreviousVideo: false } : {}),
                      })
                    }
                    data-field-key="agentContinueFromPreviousLastFrame"
                    className="accent-fuchsia-500"
                  />
                  以上一段最后一帧作为首帧
                </label>
                <div className="text-[10px] text-slate-500">
                  直接续接会优先走 SDK
                  的视频扩展；尾帧桥接会提取上一段最后一帧，作为下一段视频的首帧输入。
                </div>
                <div className="text-[10px] text-slate-500">
                  720p 优先使用直接视频续写；1080p/4K 会自动使用末帧桥接并拼接最终视频。
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">源视频 URL（可选）</label>
                  <input
                    type="text"
                    value={nodeData.agentSourceVideoUrl || ''}
                    onChange={(e) => updateNodeData({ agentSourceVideoUrl: e.target.value })}
                    data-field-key="agentSourceVideoUrl"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    placeholder="https://... 或 {{prev.output.videoUrl}}"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">
                    首帧参考图 / 图生视频（可选）
                  </label>
                  <input
                    type="text"
                    value={nodeData.agentReferenceImageUrl || ''}
                    onChange={(e) => updateNodeData({ agentReferenceImageUrl: e.target.value })}
                    data-field-key="agentReferenceImageUrl"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    placeholder="https://... 或 {{input-image.output.imageUrl}}"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">末帧图片（可选）</label>
                  <input
                    type="text"
                    value={nodeData.agentLastFrameImageUrl || ''}
                    onChange={(e) => updateNodeData({ agentLastFrameImageUrl: e.target.value })}
                    data-field-key="agentLastFrameImageUrl"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    placeholder="https://... 或 {{input-last-frame.output.imageUrl}}"
                  />
                </div>
                {supportsDrivingAudio && (
                  <div>
                    <label className="block text-xs text-slate-500 mb-1" htmlFor="agent-audio-url">
                      驱动音频 URL（可选）
                    </label>
                    <input
                      id="agent-audio-url"
                      type="text"
                      value={nodeData.agentAudioUrl || ''}
                      onChange={(e) => updateNodeData({ agentAudioUrl: e.target.value })}
                      data-field-key="agentAudioUrl"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                      placeholder="https://... 或 {{input-audio.output.audioUrl}}"
                    />
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">
                      视频编辑掩码图（可选）
                    </label>
                    <input
                      type="text"
                      value={nodeData.agentVideoMaskImageUrl || ''}
                      onChange={(e) => updateNodeData({ agentVideoMaskImageUrl: e.target.value })}
                      data-field-key="agentVideoMaskImageUrl"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                      placeholder="https://... 或 {{input-mask.output.imageUrl}}"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">掩码模式</label>
                    <select
                      value={nodeData.agentVideoMaskMode || ''}
                      onChange={(e) => updateNodeData({ agentVideoMaskMode: e.target.value })}
                      data-field-key="agentVideoMaskMode"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    >
                      <option value="">无</option>
                      <option value="REMOVE">REMOVE · 替换遮罩区域</option>
                      <option value="INSERT">INSERT · 插入新内容</option>
                      <option value="REMOVE_STATIC">REMOVE_STATIC · 清除静态区域</option>
                      <option value="OUTPAINT">OUTPAINT · 向外扩展</option>
                    </select>
                  </div>
                </div>
              </div>
            );
};
