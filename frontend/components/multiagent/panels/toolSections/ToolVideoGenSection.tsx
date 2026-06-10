/**
 * Tool 节点视频生成参数面板。
 *
 * 1:1 抽离自 `ToolNodeConfigPanel.tsx` isVideoGenerate IIFE
 * （< 800 行合规拆分）。
 */

import React, { useCallback, useMemo } from 'react';
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

export interface ToolVideoGenSectionProps {
  nodeData: CustomNodeData;
  updateNodeData: (patch: Partial<CustomNodeData>) => void;
  workflowVideoSchema: ReturnType<typeof useModeControlsSchema>['schema'];
  workflowVideoControlContract: ReturnType<typeof buildVideoControlContract>;
}

export const ToolVideoGenSection: React.FC<ToolVideoGenSectionProps> = ({
  nodeData,
  updateNodeData,
  workflowVideoSchema,
  workflowVideoControlContract,
}) => {
  const parsedToolArgs = useMemo<Record<string, any>>(() => {
    try {
      const parsed = JSON.parse(nodeData.toolArgsTemplate || '{}');
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, any>;
      }
    } catch {
      /* ignore parse error */
    }
    return {} as Record<string, any>;
  }, [nodeData.toolArgsTemplate]);
  const updateToolArgs = useCallback(
    (patch: Record<string, any>) => {
      updateNodeData({ toolArgsTemplate: JSON.stringify({ ...parsedToolArgs, ...patch }) });
    },
    [parsedToolArgs, updateNodeData]
  );
  const videoPromptValue = String(parsedToolArgs.prompt ?? '');

  const aspectRatioOptions =
    workflowVideoControlContract.validAspectRatios.length > 0
      ? workflowVideoControlContract.validAspectRatios
      : ['16:9', '9:16'];
  const trimmedAspectRatio = String(nodeData.toolAspectRatio || '').trim();
  const aspectRatio = aspectRatioOptions.includes(trimmedAspectRatio)
    ? trimmedAspectRatio
    : workflowVideoControlContract.defaultAspectRatio;
  const resolutionOptions = workflowVideoSchema?.resolutionTiers?.length
    ? workflowVideoSchema.resolutionTiers
    : [
        { value: '720p', label: '720p', baseResolution: '1280×720' },
        { value: '1080p', label: '1080p', baseResolution: '1920×1080' },
        { value: '4k', label: '4k', baseResolution: '3840×2160' },
      ];
  const resolution = normalizeWorkflowVideoResolutionSelection(
    nodeData.toolResolutionTier,
    resolutionOptions.map((item) => item.value),
    workflowVideoControlContract.defaultResolution
  );
  const durationOptions =
    workflowVideoControlContract.validSeconds.length > 0
      ? workflowVideoControlContract.validSeconds
      : [workflowVideoControlContract.defaultVideoSeconds];
  const duration = normalizeWorkflowVideoSecondsSelection(
    nodeData.toolVideoDurationSeconds,
    durationOptions,
    workflowVideoControlContract.defaultVideoSeconds
  );
  const extensionOptions = getVideoExtensionOptions(workflowVideoControlContract, duration);
  const toolVideoExtensionCount = normalizeWorkflowVideoExtensionSelection(
    nodeData.toolVideoExtensionCount,
    extensionOptions.map((item) => item.count),
    workflowVideoControlContract.defaultVideoExtensionCount
  );
  const subtitleMode = String(
    nodeData.toolSubtitleMode || workflowVideoControlContract.defaultSubtitleMode || 'none'
  );
  return (
    <div className="space-y-3 p-2.5 rounded-lg border border-fuchsia-500/20 bg-fuchsia-500/5">
      <div className="text-xs text-fuchsia-300 font-medium">视频生成参数</div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">提示词</label>
        <textarea
          value={videoPromptValue}
          onChange={(e) => updateToolArgs({ prompt: e.target.value || '{{input.task}}' })}
          rows={3}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-fuchsia-500/50 focus:ring-1 focus:ring-fuchsia-500/20 resize-none"
          placeholder="{{input.task}}"
        />
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className="block text-xs text-slate-500 mb-1">宽高比</label>
          <select
            value={aspectRatio}
            onChange={(e) => updateNodeData({ toolAspectRatio: e.target.value })}
            data-field-key="toolAspectRatio"
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
            value={resolution}
            onChange={(e) => updateNodeData({ toolResolutionTier: e.target.value })}
            data-field-key="toolResolutionTier"
            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
          >
            {resolutionOptions.map((item) => (
              <option key={item.value} value={item.value}>
                {getWorkflowVideoResolutionLabel(aspectRatio, item.value, workflowVideoSchema)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">时长（秒）</label>
          <select
            value={duration}
            onChange={(e) => {
              const nextSeconds = e.target.value;
              const nextExtensionOptions = getVideoExtensionOptions(
                workflowVideoControlContract,
                nextSeconds
              );
              updateNodeData({
                toolVideoDurationSeconds: Number(nextSeconds),
                toolVideoExtensionCount: normalizeWorkflowVideoExtensionSelection(
                  nodeData.toolVideoExtensionCount,
                  nextExtensionOptions.map((item) => item.count),
                  workflowVideoControlContract.defaultVideoExtensionCount
                ),
              });
            }}
            data-field-key="toolVideoDurationSeconds"
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
      {extensionOptions.length > 0 && (
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs text-slate-500 mb-1">延长次数</label>
            <select
              value={String(toolVideoExtensionCount)}
              onChange={(e) => updateNodeData({ toolVideoExtensionCount: Number(e.target.value) })}
              data-field-key="toolVideoExtensionCount"
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
              {extensionOptions.find((item) => item.count === toolVideoExtensionCount)
                ?.totalSeconds ?? duration}
              s
            </div>
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        <label className="flex items-center gap-2 text-xs text-slate-300">
          <input
            type="checkbox"
            checked={Boolean(
              nodeData.toolPromptExtend ?? workflowVideoControlContract.defaultEnhancePrompt
            )}
            onChange={(e) => updateNodeData({ toolPromptExtend: e.target.checked })}
            data-field-key="toolPromptExtend"
            className="accent-fuchsia-500"
          />
          AI 增强提示词
        </label>
        {workflowVideoControlContract.fieldPolicies.generateAudioAvailable && (
          <label className="flex items-center gap-2 text-xs text-slate-300">
            <input
              type="checkbox"
              checked={Boolean(
                nodeData.toolGenerateAudio ?? workflowVideoControlContract.defaultGenerateAudio
              )}
              onChange={(e) => updateNodeData({ toolGenerateAudio: e.target.checked })}
              data-field-key="toolGenerateAudio"
              className="accent-fuchsia-500"
            />
            生成音频
          </label>
        )}
      </div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">分镜提示词（可选）</label>
        <textarea
          value={nodeData.toolStoryboardPrompt || ''}
          onChange={(e) => updateNodeData({ toolStoryboardPrompt: e.target.value })}
          data-field-key="toolStoryboardPrompt"
          rows={3}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-fuchsia-500/50 resize-none"
          placeholder="Shot 1: product hero... Shot 2: tracking close-up..."
        />
      </div>
      {workflowVideoControlContract.validSubtitleModes.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-slate-500 mb-1">字幕模式</label>
              <select
                value={subtitleMode}
                onChange={(e) => updateNodeData({ toolSubtitleMode: e.target.value })}
                data-field-key="toolSubtitleMode"
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
              >
                {workflowVideoControlContract.validSubtitleModes.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>
            {workflowVideoControlContract.validSubtitleLanguages.length > 0 &&
              subtitleMode !== 'none' && (
                <div>
                  <label className="block text-xs text-slate-500 mb-1">字幕语言</label>
                  <select
                    value={String(
                      nodeData.toolSubtitleLanguage ||
                        workflowVideoControlContract.defaultSubtitleLanguage ||
                        ''
                    )}
                    onChange={(e) => updateNodeData({ toolSubtitleLanguage: e.target.value })}
                    data-field-key="toolSubtitleLanguage"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  >
                    {workflowVideoControlContract.validSubtitleLanguages.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </div>
              )}
          </div>
          {subtitleMode !== 'none' && (
            <div>
              <label className="block text-xs text-slate-500 mb-1">字幕脚本（可选）</label>
              <textarea
                value={nodeData.toolSubtitleScript || ''}
                onChange={(e) => updateNodeData({ toolSubtitleScript: e.target.value })}
                data-field-key="toolSubtitleScript"
                rows={3}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-fuchsia-500/50 resize-none"
                placeholder="每行一句字幕，或留空让模型按分镜生成。"
              />
            </div>
          )}
        </>
      )}
      <div>
        <label className="block text-xs text-slate-500 mb-1">
          源视频 URL（可选，视频续接 / 视频编辑）
        </label>
        <input
          type="text"
          value={nodeData.toolSourceVideoUrl || ''}
          onChange={(e) => updateNodeData({ toolSourceVideoUrl: e.target.value })}
          data-field-key="toolSourceVideoUrl"
          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
          placeholder="https://... 或 {{prev.output.videoUrl}}"
        />
      </div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">首帧参考图 / 图生视频（可选）</label>
        <input
          type="text"
          value={nodeData.toolReferenceImageUrl || ''}
          onChange={(e) => updateNodeData({ toolReferenceImageUrl: e.target.value })}
          data-field-key="toolReferenceImageUrl"
          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
          placeholder="https://... 或 {{input-image.output.imageUrl}}"
        />
      </div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">末帧图片（可选）</label>
        <input
          type="text"
          value={nodeData.toolLastFrameImageUrl || ''}
          onChange={(e) => updateNodeData({ toolLastFrameImageUrl: e.target.value })}
          data-field-key="toolLastFrameImageUrl"
          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
          placeholder="https://... 或 {{prev.output.lastFrameImageUrl}}"
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-xs text-slate-500 mb-1">视频编辑掩码图（可选）</label>
          <input
            type="text"
            value={nodeData.toolVideoMaskImageUrl || ''}
            onChange={(e) => updateNodeData({ toolVideoMaskImageUrl: e.target.value })}
            data-field-key="toolVideoMaskImageUrl"
            className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
            placeholder="https://... 或 {{input-mask.output.imageUrl}}"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">掩码模式</label>
          <select
            value={nodeData.toolVideoMaskMode || ''}
            onChange={(e) => updateNodeData({ toolVideoMaskMode: e.target.value })}
            data-field-key="toolVideoMaskMode"
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
      <div className="text-[10px] text-slate-500">
        不填源视频时是文生视频；只填参考图时是图生视频；同时填源视频 + 掩码时走视频编辑。
      </div>
    </div>
  );
};
