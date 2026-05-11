/**
 * Multi-agent workflow Tool 节点完整配置面板。
 *
 * 1:1 抽离自 `PropertiesPanel.tsx` renderToolNodeConfig L2403-3619
 * （JIRA-frontend-properties-panel-deep-split.md Step 1）。
 *
 * 体积巨大（1200+ 行）— 后续 sub-ticket 按 tool 类别（image-gen / video-gen /
 * prompt-optimize / table-analyze / amazon-ads / video-delete 等）进一步拆分。
 * 本步骤先做"主组件瘦身"，下一轮再做"sub-component 拆分"。
 *
 * 闭包依赖（7 个 props）：见 ToolNodeConfigPanelProps 接口。
 */

import React from 'react';
import { Upload, X } from 'lucide-react';
import { reportError } from '../../../utils/globalErrorHandler';
import { CustomNodeData } from '../CustomNode';
import { NodeType } from '../nodeTypeConfigs';
import {
  AgentTaskType,
  ModelOption,
  ProviderModels,
  formatModelTaskHint,
  modelSupportsTask,
  pickProviderDefaultModel,
} from '../providerModelUtils';
import { useModeControlsSchema } from '../../../hooks/useModeControlsSchema';
import {
  buildVideoControlContract,
  getVideoExtensionOptions,
} from '../../../utils/videoControlSchema';
import { classifyToolNode } from '../toolClassification';
import {
  getResolutionLabel,
  normalizeWorkflowVideoResolutionSelection,
  normalizeWorkflowVideoSecondsSelection,
  normalizeWorkflowVideoExtensionSelection,
  getWorkflowVideoResolutionLabel,
} from '../workflowResolution';
import { fileToBase64 } from '../../../hooks/handlers/attachmentUtils';
import { ToolVideoGenSection } from './toolSections/ToolVideoGenSection';
import { ToolImageGenSection } from './toolSections/ToolImageGenSection';

export interface ToolNodeConfigPanelProps {
  nodeData: CustomNodeData;
  nodeType: NodeType;
  updateNodeData: (patch: Partial<CustomNodeData>) => void;
  providers: ProviderModels[];
  providersLoading: boolean;
  workflowVideoSchema: ReturnType<typeof useModeControlsSchema>['schema'];
  workflowVideoControlContract: ReturnType<typeof buildVideoControlContract>;
}

export const ToolNodeConfigPanel: React.FC<ToolNodeConfigPanelProps> = ({
  nodeData,
  nodeType,
  updateNodeData,
  providers,
  providersLoading,
  workflowVideoSchema,
  workflowVideoControlContract,
}) => {
  if (nodeType === 'tool') {
    // Tool 分类抽离至 ./toolClassification（业务下沉准备 — 未来由后端 tool registry 提供）
    const toolClass = classifyToolNode(nodeData.toolName);
    const toolName = toolClass.normalizedToolName;
    const {
      isImageGen,
      isImageEdit,
      isVideoGenerate,
      isVideoUnderstand,
      isVideoDelete,
      isPromptOptimize,
      isTableAnalyze,
      isAmazonAdsOptimize,
      taskType: toolTaskType,
      shouldShowToolModelOverride,
      shouldShowToolProviderOverride,
    } = toolClass;
    const selectedProviderId = nodeData.toolProviderId || '';
    const selectedProvider = providers.find(
      (provider) => provider.providerId === selectedProviderId
    );
    const providerModels = selectedProvider?.allModels || selectedProvider?.models || [];
    const compatibleModels = providerModels.filter((model) =>
      modelSupportsTask(model, toolTaskType)
    );
    const selectedModels = compatibleModels;
    const providerHasNoCompatibleModels =
      selectedProviderId !== '' && providerModels.length > 0 && compatibleModels.length === 0;
    const selectedToolModel = providerModels.find(
      (model) => model.id === (nodeData.toolModelId || '')
    );
    const isToolTaskCompatible = (model: ModelOption | undefined, taskType: AgentTaskType) => {
      return modelSupportsTask(model, taskType);
    };
    const findProviderModels = (providerId: string): ModelOption[] => {
      const provider = providers.find((item) => item.providerId === providerId);
      return provider?.allModels || provider?.models || [];
    };
    const pickCompatibleToolModel = (
      providerId: string,
      taskType: AgentTaskType
    ): ModelOption | undefined => {
      const provider = providers.find((item) => item.providerId === providerId);
      return pickProviderDefaultModel(provider, taskType);
    };
    const handleToolNameChange = (nextToolName: string) => {
      // 使用 classifyToolNode 替代内联 alias 重复（与 renderToolNodeConfig 起始处共用同一分类逻辑）
      const nextClass = classifyToolNode(nextToolName);
      const {
        isImageGen: nextIsImageGen,
        isImageEdit: nextIsImageEdit,
        isVideoGenerate: nextIsVideoGenerate,
        isVideoUnderstand: nextIsVideoUnderstand,
        isVideoDelete: nextIsVideoDelete,
        isPromptOptimize: nextIsPromptOptimize,
      } = nextClass;
      const updates: Partial<CustomNodeData> = { toolName: nextToolName };

      if (nextIsVideoGenerate) {
        if (!String(nodeData.toolAspectRatio || '').trim()) {
          updates.toolAspectRatio = workflowVideoControlContract.defaultAspectRatio || '16:9';
        }
        if (!String(nodeData.toolResolutionTier || '').trim()) {
          updates.toolResolutionTier = workflowVideoControlContract.defaultResolution || '720p';
        }
        if (!Number.isFinite(Number(nodeData.toolVideoDurationSeconds))) {
          updates.toolVideoDurationSeconds = Number(
            workflowVideoControlContract.defaultVideoSeconds || '8'
          );
        }
        if (!Number.isFinite(Number(nodeData.toolVideoExtensionCount))) {
          updates.toolVideoExtensionCount = workflowVideoControlContract.defaultVideoExtensionCount;
        }
        if (typeof nodeData.toolGenerateAudio !== 'boolean') {
          updates.toolGenerateAudio = workflowVideoControlContract.defaultGenerateAudio;
        }
        if (!String(nodeData.toolSubtitleMode || '').trim()) {
          updates.toolSubtitleMode = workflowVideoControlContract.defaultSubtitleMode;
        }
        if (
          !String(nodeData.toolSubtitleLanguage || '').trim() &&
          workflowVideoControlContract.defaultSubtitleLanguage
        ) {
          updates.toolSubtitleLanguage = workflowVideoControlContract.defaultSubtitleLanguage;
        }
      }

      if (
        nextIsImageGen ||
        nextIsImageEdit ||
        nextIsPromptOptimize ||
        nextIsVideoGenerate ||
        nextIsVideoUnderstand
      ) {
        const targetTask: AgentTaskType = nextIsImageEdit
          ? 'image-edit'
          : nextIsImageGen
            ? 'image-gen'
            : nextIsVideoGenerate
              ? 'video-gen'
              : nextIsVideoUnderstand
                ? 'vision-understand'
                : 'chat';
        const currentProviderId = String(nodeData.toolProviderId || '').trim();
        const currentModelId = String(nodeData.toolModelId || '').trim();

        if (currentProviderId) {
          const currentModel = findProviderModels(currentProviderId).find(
            (model) => model.id === currentModelId
          );
          if (!isToolTaskCompatible(currentModel, targetTask)) {
            const fallback = pickCompatibleToolModel(currentProviderId, targetTask);
            updates.toolModelId = fallback?.id || '';
          }
        } else {
          const providerWithModel = providers.find((provider) => {
            const modelPool = provider.allModels || provider.models || [];
            return modelPool.some((model) => isToolTaskCompatible(model, targetTask));
          });

          if (providerWithModel?.providerId) {
            const fallback = pickCompatibleToolModel(providerWithModel.providerId, targetTask);
            updates.toolProviderId = providerWithModel.providerId;
            updates.toolModelId = fallback?.id || '';
          }
        }
      } else if (nextIsVideoDelete && !String(nodeData.toolProviderId || '').trim()) {
        const googleProvider = providers.find((provider) => provider.providerId === 'google');
        if (googleProvider?.providerId) {
          updates.toolProviderId = googleProvider.providerId;
          updates.toolModelId = '';
        }
      }

      updateNodeData(updates);
    };

    const parseToolArgs = () => {
      try {
        const parsed = JSON.parse(nodeData.toolArgsTemplate || '{}');
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          return parsed as Record<string, any>;
        }
      } catch {
        // ignore parse error
      }
      return {} as Record<string, any>;
    };

    const updateToolArgs = (patch: Record<string, any>) => {
      const current = parseToolArgs();
      updateNodeData({ toolArgsTemplate: JSON.stringify({ ...current, ...patch }) });
    };

    const amazonArgs = parseToolArgs();
    const amazonTargetAcosRaw = amazonArgs.targetAcos ?? '';
    const amazonTargetAcosValue =
      typeof amazonTargetAcosRaw === 'number'
        ? String(amazonTargetAcosRaw > 1 ? amazonTargetAcosRaw : amazonTargetAcosRaw * 100)
        : String(amazonTargetAcosRaw || '').replace('%', '');
    const promptOptimizeArgs = parseToolArgs();
    const promptOptimizePromptValue = String(promptOptimizeArgs.prompt ?? '');
    const promptOptimizeGoalValue = String(promptOptimizeArgs.goal ?? '');
    const promptOptimizeStyleValue = String(promptOptimizeArgs.style ?? '');
    const promptOptimizeLanguageValue = String(promptOptimizeArgs.language ?? 'auto');
    const promptOptimizeLengthValue = String(promptOptimizeArgs.length ?? 'medium');
    const promptOptimizeMustKeepValue = Array.isArray(promptOptimizeArgs.must_keep)
      ? promptOptimizeArgs.must_keep.join(', ')
      : String(promptOptimizeArgs.must_keep ?? '');
    const promptOptimizeAvoidValue = Array.isArray(promptOptimizeArgs.avoid)
      ? promptOptimizeArgs.avoid.join(', ')
      : String(promptOptimizeArgs.avoid ?? '');
    const promptOptimizeRequirementsValue = String(promptOptimizeArgs.requirements ?? '');
    const videoPromptValue = String(parseToolArgs().prompt ?? '');
    const videoUnderstandOutputFormatValue = String(parseToolArgs().output_format ?? 'markdown');
    const videoDeleteProviderFileNameValue = String(parseToolArgs().provider_file_name ?? '');
    const videoDeleteProviderFileUriValue = String(parseToolArgs().provider_file_uri ?? '');
    const videoDeleteGcsUriValue = String(parseToolArgs().gcs_uri ?? '');

    return (
      <div className="space-y-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1.5">工具类型</label>
          <select
            value={nodeData.toolName || ''}
            onChange={(e) => handleToolNameChange(e.target.value)}
            data-field-key="toolName"
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
          >
            <option value="">请选择工具</option>
            <optgroup label="图片生成">
              <option value="image_generate">🖼️ 图片生成</option>
            </optgroup>
            <optgroup label="图片编辑">
              <option value="image_chat_edit">🪄 图片编辑（对话式）</option>
              <option value="image_mask_edit">🎭 蒙版编辑</option>
              <option value="image_inpainting">🖌️ 局部重绘</option>
              <option value="image_background_edit">🏞️ 背景替换</option>
              <option value="image_recontext">🔄 场景重构</option>
              <option value="image_outpaint">📐 图片扩展</option>
            </optgroup>
            <optgroup label="视频">
              <option value="video_generate">🎬 视频生成 / 图生视频</option>
              <option value="video_understand">🧠 视频理解</option>
              <option value="video_delete">🗑️ 视频删除</option>
            </optgroup>
            <optgroup label="数据分析">
              <option value="table_analyze">📊 表格分析</option>
              <option value="sheet_analyze">🧾 全量表格剖析</option>
              <option value="sheet_stage_ingest">🧱 Sheet Stage · Ingest</option>
              <option value="sheet_stage_profile">📐 Sheet Stage · Profile</option>
              <option value="sheet_stage_query">🔎 Sheet Stage · Query</option>
              <option value="sheet_stage_export">📤 Sheet Stage · Export</option>
              <option value="amazon_ads_keyword_optimize">🛒 Amazon 广告关键词优化</option>
            </optgroup>
            <optgroup label="搜索">
              <option value="web_search">🔍 网页搜索</option>
              <option value="google_search">🔍 网页搜索（兼容别名）</option>
              <option value="read_webpage">📖 网页读取</option>
              <option value="selenium_browse">🧭 浏览器抓取</option>
            </optgroup>
            <optgroup label="MCP">
              <option value="mcp_tool_call">🧩 MCP 工具调用</option>
            </optgroup>
            <optgroup label="数据处理">
              <option value="json_extract">📋 JSON 提取</option>
              <option value="text_length">📏 文本长度</option>
            </optgroup>
            <optgroup label="提示词">
              <option value="prompt_optimize">✨ 提示词优化</option>
            </optgroup>
          </select>
        </div>

        {shouldShowToolProviderOverride && (
          <div className="p-2.5 rounded-lg border border-indigo-500/20 bg-indigo-500/5 space-y-3">
            <div className="text-xs text-indigo-300 font-medium">
              {isPromptOptimize
                ? '文本模型覆盖（可选）'
                : isVideoGenerate
                  ? '视频生成模型覆盖（可选）'
                  : isVideoUnderstand
                    ? '视频理解模型覆盖（可选）'
                    : isVideoDelete
                      ? '视频删除 Provider（必填）'
                      : '图片模型覆盖（可选）'}
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">提供商</label>
              <select
                value={selectedProviderId}
                onChange={(e) => {
                  const providerId = e.target.value;
                  const provider = providers.find((item) => item.providerId === providerId);
                  const fallbackModel = pickProviderDefaultModel(provider, toolTaskType);
                  updateNodeData({
                    toolProviderId: providerId,
                    toolModelId:
                      shouldShowToolModelOverride && providerId ? fallbackModel?.id || '' : '',
                  });
                }}
                data-field-key="toolProviderId"
                disabled={providersLoading}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 disabled:opacity-50"
              >
                <option value="">自动选择（按已配置 provider 回退）</option>
                {providers.map((provider) => (
                  <option key={provider.providerId} value={provider.providerId}>
                    {provider.providerName}
                  </option>
                ))}
              </select>
            </div>
            {selectedProviderId && shouldShowToolModelOverride && (
              <div>
                <label className="block text-xs text-slate-500 mb-1.5">模型</label>
                <select
                  value={nodeData.toolModelId || ''}
                  onChange={(e) => updateNodeData({ toolModelId: e.target.value })}
                  data-field-key="toolModelId"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20"
                >
                  <option value="">请选择模型</option>
                  {selectedModels.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name} · {formatModelTaskHint(model.supportedTasks)}
                    </option>
                  ))}
                </select>
                {providerHasNoCompatibleModels && (
                  <div className="mt-1 text-[10px] text-amber-300">
                    当前提供商没有可用于该工具任务的兼容模型，已阻止回退到不兼容模型。
                  </div>
                )}
                {selectedToolModel && !modelSupportsTask(selectedToolModel, toolTaskType) && (
                  <div className="mt-1 text-[10px] text-amber-300">
                    当前覆盖模型与工具任务类型不匹配，建议清空或切换到兼容模型。
                  </div>
                )}
              </div>
            )}
            <div className="text-[10px] text-slate-500">
              当前生效：
              {selectedProviderId
                ? nodeData.toolModelId || !shouldShowToolModelOverride
                  ? `${selectedProviderId}${nodeData.toolModelId ? ` / ${nodeData.toolModelId}` : ''}`
                  : `${selectedProviderId} / 自动回退`
                : '自动回退选择'}
            </div>
          </div>
        )}

        {/* 图片生成参数（抽离至 ./toolSections/ToolImageGenSection） */}
        {isImageGen && (
          <ToolImageGenSection nodeData={nodeData} updateNodeData={updateNodeData} />
        )}

        {/* 视频生成参数（抽离至 ./toolSections/ToolVideoGenSection） */}
        {isVideoGenerate && (
          <ToolVideoGenSection
            nodeData={nodeData}
            updateNodeData={updateNodeData}
            workflowVideoSchema={workflowVideoSchema}
            workflowVideoControlContract={workflowVideoControlContract}
          />
        )}

        {isVideoUnderstand && (
          <div className="space-y-3 p-2.5 rounded-lg border border-indigo-500/20 bg-indigo-500/5">
            <div className="text-xs text-indigo-300 font-medium">视频理解参数</div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">分析提示词</label>
              <textarea
                value={videoPromptValue}
                onChange={(e) =>
                  updateToolArgs({
                    prompt: e.target.value || '请分析该视频的主要场景、动作、镜头变化和关键信息。',
                  })
                }
                rows={3}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 resize-none"
                placeholder="请分析该视频的主要场景、动作、镜头变化和关键信息。"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">源视频 URL</label>
              <input
                type="text"
                value={nodeData.toolSourceVideoUrl || ''}
                onChange={(e) => updateNodeData({ toolSourceVideoUrl: e.target.value })}
                data-field-key="toolSourceVideoUrl"
                className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
                placeholder="https://... 或 {{prev.output.videoUrl}}"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">输出格式</label>
              <select
                value={videoUnderstandOutputFormatValue}
                onChange={(e) => updateToolArgs({ output_format: e.target.value || 'markdown' })}
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
              >
                <option value="markdown">Markdown</option>
                <option value="json">JSON</option>
                <option value="text">文本</option>
              </select>
            </div>
          </div>
        )}

        {isVideoDelete && (
          <div className="space-y-3 p-2.5 rounded-lg border border-rose-500/20 bg-rose-500/5">
            <div className="text-xs text-rose-300 font-medium">视频删除参数</div>
            <div className="text-[10px] text-slate-500">
              如果当前节点接在视频生成节点后面，留空即可自动读取上一节点的 provider 资产信息。
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                Provider File Name（Gemini Files）
              </label>
              <input
                type="text"
                value={videoDeleteProviderFileNameValue}
                onChange={(e) =>
                  updateToolArgs({ provider_file_name: e.target.value || undefined })
                }
                className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-rose-500/50"
                placeholder="files/..."
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Provider File URI（可选）</label>
              <input
                type="text"
                value={videoDeleteProviderFileUriValue}
                onChange={(e) => updateToolArgs({ provider_file_uri: e.target.value || undefined })}
                className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-rose-500/50"
                placeholder="files/... 或 gs://..."
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">GCS URI（Vertex）</label>
              <input
                type="text"
                value={videoDeleteGcsUriValue}
                onChange={(e) => updateToolArgs({ gcs_uri: e.target.value || undefined })}
                className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-rose-500/50"
                placeholder="gs://bucket/path/video.mp4"
              />
            </div>
          </div>
        )}

        {/* 提示词优化参数 */}
        {isPromptOptimize && (
          <div className="space-y-3 p-2.5 rounded-lg border border-fuchsia-500/20 bg-fuchsia-500/5">
            <div className="text-xs text-fuchsia-300 font-medium">提示词优化参数</div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">原始提示词</label>
              <textarea
                value={promptOptimizePromptValue}
                onChange={(e) => updateToolArgs({ prompt: e.target.value || '{{input.task}}' })}
                rows={2}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-fuchsia-500/50 focus:ring-1 focus:ring-fuchsia-500/20 resize-none"
                placeholder="{{input.task}}"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">优化目标</label>
              <input
                type="text"
                value={promptOptimizeGoalValue}
                onChange={(e) => updateToolArgs({ goal: e.target.value || undefined })}
                className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                placeholder="如：电商主图生成，强调主体和构图"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-slate-500 mb-1">风格</label>
                <input
                  type="text"
                  value={promptOptimizeStyleValue}
                  onChange={(e) => updateToolArgs({ style: e.target.value || undefined })}
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  placeholder="专业 / 创意 / 营销"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">长度</label>
                <select
                  value={promptOptimizeLengthValue}
                  onChange={(e) => updateToolArgs({ length: e.target.value || 'medium' })}
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                >
                  <option value="short">短</option>
                  <option value="medium">中</option>
                  <option value="long">长</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">输出语言</label>
              <select
                value={promptOptimizeLanguageValue}
                onChange={(e) => updateToolArgs({ language: e.target.value || 'auto' })}
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
              >
                <option value="auto">自动</option>
                <option value="zh-CN">中文</option>
                <option value="en-US">English</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                必须保留关键词（逗号分隔）
              </label>
              <input
                type="text"
                value={promptOptimizeMustKeepValue}
                onChange={(e) => {
                  const keywords = e.target.value
                    .split(/[,，;\n]+/)
                    .map((item) => item.trim())
                    .filter(Boolean);
                  updateToolArgs({ must_keep: keywords.length > 0 ? keywords : undefined });
                }}
                className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                placeholder="主体名称, 材质, 品牌元素"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">禁止元素（逗号分隔）</label>
              <input
                type="text"
                value={promptOptimizeAvoidValue}
                onChange={(e) => {
                  const keywords = e.target.value
                    .split(/[,，;\n]+/)
                    .map((item) => item.trim())
                    .filter(Boolean);
                  updateToolArgs({ avoid: keywords.length > 0 ? keywords : undefined });
                }}
                className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                placeholder="水印, 低质量, 变形"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">附加约束</label>
              <textarea
                value={promptOptimizeRequirementsValue}
                onChange={(e) => updateToolArgs({ requirements: e.target.value || undefined })}
                rows={2}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-fuchsia-500/50 focus:ring-1 focus:ring-fuchsia-500/20 resize-none"
                placeholder="如：必须可直接用于 image generation API，不要解释文本"
              />
            </div>
          </div>
        )}

        {/* 图片编辑参数 */}
        {isImageEdit && (
          <div className="space-y-3 p-2.5 rounded-lg border border-purple-500/20 bg-purple-500/5">
            <div className="text-xs text-purple-300 font-medium">图片编辑参数</div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                参考图片 <span className="text-red-400">*</span>
              </label>
              {!!nodeData.toolReferenceImageUrl &&
                nodeData.toolReferenceImageUrl.startsWith('data:') && (
                  <div className="mb-2 relative group">
                    <img
                      src={nodeData.toolReferenceImageUrl}
                      alt="参考图片"
                      className="w-full h-24 object-cover rounded border border-purple-500/30"
                    />
                    <button
                      onClick={() => updateNodeData({ toolReferenceImageUrl: '' })}
                      className="absolute top-1 right-1 p-0.5 bg-red-500/80 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <X size={10} />
                    </button>
                  </div>
                )}
              <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-purple-500/40 rounded-lg cursor-pointer hover:border-purple-500/60 transition-colors">
                <Upload size={12} className="text-purple-400" />
                <span className="text-xs text-purple-300">
                  {nodeData.toolReferenceImageUrl ? '更换图片' : '上传参考图片'}
                </span>
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    try {
                      updateNodeData({ toolReferenceImageUrl: await fileToBase64(file) });
                    } catch (err) {
                      reportError('文件转换失败', err);
                    }
                    e.target.value = '';
                  }}
                />
              </label>
              <input
                type="text"
                value={
                  !nodeData.toolReferenceImageUrl?.startsWith('data:')
                    ? nodeData.toolReferenceImageUrl || ''
                    : ''
                }
                onChange={(e) => updateNodeData({ toolReferenceImageUrl: e.target.value })}
                data-field-key="toolReferenceImageUrl"
                className="mt-1.5 w-full px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-400 font-mono focus:outline-none focus:border-purple-500/50"
                placeholder="或输入 URL / {{prev.output.imageUrl}}"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">编辑指令</label>
              <textarea
                value={nodeData.toolEditPrompt || ''}
                onChange={(e) => updateNodeData({ toolEditPrompt: e.target.value })}
                rows={2}
                data-field-key="toolEditPrompt"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
                placeholder="描述你想要的编辑效果..."
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-slate-500 mb-1">宽高比</label>
                <select
                  value={nodeData.toolAspectRatio || ''}
                  onChange={(e) => updateNodeData({ toolAspectRatio: e.target.value })}
                  data-field-key="toolAspectRatio"
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                >
                  <option value="">保持原比例</option>
                  <option value="1:1">1:1</option>
                  <option value="16:9">16:9</option>
                  <option value="9:16">9:16</option>
                  <option value="4:3">4:3</option>
                  <option value="3:4">3:4</option>
                </select>
              </div>
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
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-300">
              <input
                type="checkbox"
                checked={Boolean(nodeData.toolPromptExtend)}
                onChange={(e) => updateNodeData({ toolPromptExtend: e.target.checked })}
                data-field-key="toolPromptExtend"
                className="accent-teal-500"
              />
              启用编辑提示词优化（provider 支持时生效）
            </label>
          </div>
        )}

        {/* 表格分析参数 */}
        {isTableAnalyze && (
          <div className="space-y-3 p-2.5 rounded-lg border border-cyan-500/20 bg-cyan-500/5">
            <div className="text-xs text-cyan-300 font-medium">表格分析参数</div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">分析类型</label>
              <select
                value={nodeData.toolAnalysisType || 'comprehensive'}
                onChange={(e) => updateNodeData({ toolAnalysisType: e.target.value })}
                data-field-key="toolAnalysisType"
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
              >
                <option value="comprehensive">综合分析</option>
                <option value="statistics">描述统计</option>
                <option value="correlation">相关性分析</option>
                <option value="trends">趋势分析</option>
                <option value="distribution">分布与异常</option>
              </select>
            </div>
          </div>
        )}

        {/* Amazon 广告优化参数 */}
        {isAmazonAdsOptimize && (
          <div className="space-y-3 p-2.5 rounded-lg border border-amber-500/20 bg-amber-500/5">
            <div className="text-xs text-amber-300 font-medium">Amazon 广告优化参数</div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">目标 ACoS（%）</label>
              <input
                type="number"
                min={1}
                max={200}
                value={amazonTargetAcosValue}
                onChange={(e) => {
                  const nextValue = e.target.value.trim();
                  if (!nextValue) {
                    updateToolArgs({ targetAcos: undefined });
                    return;
                  }
                  const numeric = Number(nextValue);
                  if (Number.isFinite(numeric) && numeric > 0) {
                    updateToolArgs({ targetAcos: numeric });
                  }
                }}
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-amber-500/50"
                placeholder="例如 30"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">优化目标说明</label>
              <textarea
                value={String(amazonArgs.query || '')}
                onChange={(e) => updateToolArgs({ query: e.target.value })}
                rows={2}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/20 resize-none"
                placeholder="例如：控 ACOS 到 30% 以内，并扩大高转化词流量"
              />
            </div>
            <div className="text-[10px] text-slate-500">
              文件请通过“文件输入组件”传入，工具会自动识别表头并输出否定词/加投词建议。
            </div>
          </div>
        )}

        {/* 高级：原始参数模板（所有工具通用） */}
        <details className="group">
          <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-400 flex items-center gap-1">
            <span className="group-open:rotate-90 transition-transform">▶</span>
            高级：自定义参数 JSON
          </summary>
          <div className="mt-2">
            <textarea
              value={nodeData.toolArgsTemplate || ''}
              onChange={(e) => updateNodeData({ toolArgsTemplate: e.target.value })}
              rows={3}
              data-field-key="toolArgsTemplate"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 font-mono focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
              placeholder={'{"query":"{{prev.output.text}}"}'}
            />
            <div className="mt-1 text-[10px] text-slate-600">
              支持模板变量：{'{{input.task}}'}, {'{{prev.output.text}}'}
            </div>
          </div>
        </details>
      </div>
    );
  }

  return null;
};
