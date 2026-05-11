/**
 * Multi-agent workflow Agent 节点完整配置面板。
 *
 * 1:1 抽离自 `PropertiesPanel.tsx` renderAgentNodeConfig L823-2401
 * （JIRA-frontend-properties-panel-deep-split.md Step 2）。
 *
 * 体积巨大（1500+ 行）— 后续 sub-ticket 按 agentTaskType（chat / image-gen /
 * image-edit / video-gen / audio-gen / vision-understand / data-analysis）继续拆。
 * 本步骤先做"主组件瘦身"，下一轮再做"sub-component 拆分"。
 *
 * 闭包依赖（10 个 props）：见 AgentNodeConfigPanelProps 接口。
 */

import React from 'react';
import { FileSpreadsheet, Info, Upload, X } from 'lucide-react';
import { CustomNodeData } from '../CustomNode';
import { NodeType } from '../nodeTypeConfigs';
import type { NodeStatus } from '../types';
import type { AgentDef } from '../types';
import { AgentSelector } from '../AgentSelector';
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
import {
  getResolutionLabel,
  normalizeWorkflowVideoResolutionSelection,
  normalizeWorkflowVideoSecondsSelection,
  normalizeWorkflowVideoExtensionSelection,
  getWorkflowVideoResolutionLabel,
} from '../workflowResolution';
import { fileToBase64 } from '../../../hooks/handlers/attachmentUtils';
import {
  analyzeAgentNodeDefaultUsage,
  buildAgentNodeDefaultsFromAgent,
} from '../agentNodeDefaults';
import { AgentVideoGenSection } from './agentSections/AgentVideoGenSection';
import { AgentImageEditSection } from './agentSections/AgentImageEditSection';
import { AgentImageGenSection } from './agentSections/AgentImageGenSection';
import { AgentAudioGenSection } from './agentSections/AgentAudioGenSection';
import { AgentDataAnalysisSection } from './agentSections/AgentDataAnalysisSection';
import { reportInlineUploadError, readInlineFilesAsDataUrls } from '../uploadHandlers';

export interface AgentNodeConfigPanelProps {
  nodeData: CustomNodeData;
  nodeType: NodeType;
  updateNodeData: (patch: Partial<CustomNodeData>) => void;
  providers: ProviderModels[];
  providersLoading: boolean;
  workflowVideoSchema: ReturnType<typeof useModeControlsSchema>['schema'];
  workflowVideoControlContract: ReturnType<typeof buildVideoControlContract>;
  status: NodeStatus;
  resolvedAgent: AgentDef | null;
  setResolvedAgent: React.Dispatch<React.SetStateAction<AgentDef | null>>;
  agentDefaultAnalysis: ReturnType<typeof analyzeAgentNodeDefaultUsage>;
}

export const AgentNodeConfigPanel: React.FC<AgentNodeConfigPanelProps> = ({
  nodeData,
  nodeType,
  updateNodeData,
  providers,
  providersLoading,
  workflowVideoSchema,
  workflowVideoControlContract,
  status,
  resolvedAgent,
  setResolvedAgent,
  agentDefaultAnalysis,
}) => {
  if (nodeType === 'agent') {
    const selectedProviderId = nodeData.modelOverrideProviderId || '';
    const selectedProvider = providers.find(
      (provider) => provider.providerId === selectedProviderId
    );
    const selectedTaskType: AgentTaskType = (
      [
        'chat',
        'image-gen',
        'image-edit',
        'video-gen',
        'audio-gen',
        'vision-understand',
        'data-analysis',
      ].includes(String(nodeData.agentTaskType || 'chat'))
        ? String(nodeData.agentTaskType || 'chat')
        : 'chat'
    ) as AgentTaskType;
    const hasAgentReferenceImage = Boolean(String(nodeData.agentReferenceImageUrl || '').trim());
    const taskSupportsReferenceImage =
      selectedTaskType === 'image-edit' || selectedTaskType === 'vision-understand';
    const providerModels = selectedProvider?.allModels || selectedProvider?.models || [];
    const compatibleModels = providerModels.filter((model) =>
      modelSupportsTask(model, selectedTaskType)
    );
    const selectedModels = compatibleModels;
    const providerHasNoCompatibleModels =
      selectedProviderId !== '' && providerModels.length > 0 && compatibleModels.length === 0;
    const selectedOverrideModel = providerModels.find(
      (model) => model.id === (nodeData.modelOverrideModelId || '')
    );
    const effectiveProvider = nodeData.modelOverrideProviderId || nodeData.agentProviderId || '';
    const effectiveModel = nodeData.modelOverrideModelId || nodeData.agentModelId || '';
    const effectiveModelPool =
      providers.find((provider) => provider.providerId === effectiveProvider)?.allModels ||
      providers.find((provider) => provider.providerId === effectiveProvider)?.models ||
      [];
    const effectiveModelOption = effectiveModelPool.find((model) => model.id === effectiveModel);
    const effectiveSupportedTasks = Array.isArray(effectiveModelOption?.supportedTasks)
      ? effectiveModelOption.supportedTasks
      : [];
    const hasEffectiveTaskConstraint = effectiveSupportedTasks.length > 0;
    const taskOptions: Array<{ value: AgentTaskType; label: string }> = [
      { value: 'chat', label: '💬 对话（文本生成）' },
      { value: 'image-gen', label: '🖼️ 图片生成（文生图）' },
      { value: 'image-edit', label: '🪄 图片编辑（图生图）' },
      { value: 'video-gen', label: '🎬 视频生成（文生视频）' },
      { value: 'audio-gen', label: '🎧 音频生成（语音/旁白）' },
      { value: 'vision-understand', label: '🧠 图片理解（多模态）' },
      { value: 'data-analysis', label: '📊 数据分析' },
    ];
    const isTaskCompatible = (model: ModelOption | undefined, taskType: AgentTaskType) => {
      return modelSupportsTask(model, taskType);
    };
    const findProvider = (providerId: string): ProviderModels | undefined => {
      return providers.find((item) => item.providerId === providerId);
    };
    const findProviderModels = (providerId: string): ModelOption[] => {
      const provider = findProvider(providerId);
      return provider?.allModels || provider?.models || [];
    };
    const findModelById = (providerId: string, modelId: string): ModelOption | undefined => {
      if (!providerId || !modelId) return undefined;
      return findProviderModels(providerId).find((model) => model.id === modelId);
    };
    const pickCompatibleModel = (
      providerId: string,
      taskType: AgentTaskType
    ): ModelOption | undefined => {
      const provider = findProvider(providerId);
      return pickProviderDefaultModel(provider, taskType);
    };
    const handleAgentTaskTypeChange = (nextTaskType: AgentTaskType) => {
      const updates: Partial<CustomNodeData> = { agentTaskType: nextTaskType };
      if (nextTaskType === 'video-gen') {
        if (!String(nodeData.agentAspectRatio || '').trim()) {
          updates.agentAspectRatio = workflowVideoControlContract.defaultAspectRatio;
        }
        if (!String(nodeData.agentResolutionTier || '').trim()) {
          updates.agentResolutionTier = workflowVideoControlContract.defaultResolution;
        }
        if (!Number.isFinite(Number(nodeData.agentVideoDurationSeconds))) {
          updates.agentVideoDurationSeconds = Number(
            workflowVideoControlContract.defaultVideoSeconds || '8'
          );
        }
        if (!Number.isFinite(Number(nodeData.agentVideoExtensionCount))) {
          updates.agentVideoExtensionCount =
            workflowVideoControlContract.defaultVideoExtensionCount;
        }
        if (typeof nodeData.agentContinueFromPreviousVideo !== 'boolean') {
          updates.agentContinueFromPreviousVideo = false;
        }
        if (typeof nodeData.agentContinueFromPreviousLastFrame !== 'boolean') {
          updates.agentContinueFromPreviousLastFrame = false;
        }
        if (typeof nodeData.agentGenerateAudio !== 'boolean') {
          updates.agentGenerateAudio = workflowVideoControlContract.defaultGenerateAudio;
        }
        if (!String(nodeData.agentSubtitleMode || '').trim()) {
          updates.agentSubtitleMode = workflowVideoControlContract.defaultSubtitleMode;
        }
        if (
          !String(nodeData.agentSubtitleLanguage || '').trim() &&
          workflowVideoControlContract.defaultSubtitleLanguage
        ) {
          updates.agentSubtitleLanguage = workflowVideoControlContract.defaultSubtitleLanguage;
        }
        if (
          !String(nodeData.agentSubtitleScript || '').trim() &&
          workflowVideoControlContract.defaultSubtitleScript
        ) {
          updates.agentSubtitleScript = workflowVideoControlContract.defaultSubtitleScript;
        }
        if (
          !String(nodeData.agentStoryboardPrompt || '').trim() &&
          workflowVideoControlContract.defaultStoryboardPrompt
        ) {
          updates.agentStoryboardPrompt = workflowVideoControlContract.defaultStoryboardPrompt;
        }
        if (
          !String(nodeData.agentNegativePrompt || '').trim() &&
          workflowVideoControlContract.defaultNegativePrompt
        ) {
          updates.agentNegativePrompt = workflowVideoControlContract.defaultNegativePrompt;
        }
        if (!Number.isFinite(Number(nodeData.agentSeed))) {
          updates.agentSeed = workflowVideoControlContract.defaultSeed;
        }
        if (typeof nodeData.agentPromptExtend !== 'boolean') {
          updates.agentPromptExtend = workflowVideoControlContract.defaultEnhancePrompt;
        }
      }
      if (nextTaskType === 'audio-gen') {
        if (!String(nodeData.agentAudioFormat || '').trim()) {
          updates.agentAudioFormat = 'mp3';
        }
        if (!Number.isFinite(Number(nodeData.agentSpeechSpeed))) {
          updates.agentSpeechSpeed = 1;
        }
      }
      if (
        nextTaskType === 'vision-understand' &&
        !String(nodeData.agentOutputFormat || '').trim()
      ) {
        updates.agentOutputFormat = 'json';
      }
      if (nextTaskType === 'data-analysis' && !String(nodeData.agentOutputFormat || '').trim()) {
        updates.agentOutputFormat = 'markdown';
      }
      const overrideProviderId = String(nodeData.modelOverrideProviderId || '').trim();
      const overrideModelId = String(nodeData.modelOverrideModelId || '').trim();

      if (overrideProviderId) {
        const overrideModel = findModelById(overrideProviderId, overrideModelId);
        if (!isTaskCompatible(overrideModel, nextTaskType)) {
          const fallback = pickCompatibleModel(overrideProviderId, nextTaskType);
          updates.modelOverrideModelId = fallback?.id || '';
        }
        updateNodeData(updates);
        return;
      }

      const baseProviderId = String(nodeData.agentProviderId || '').trim();
      const baseModelId = String(nodeData.agentModelId || '').trim();
      if (!baseProviderId) {
        updateNodeData(updates);
        return;
      }
      const baseModel = findModelById(baseProviderId, baseModelId);
      if (!isTaskCompatible(baseModel, nextTaskType)) {
        const fallback = pickCompatibleModel(baseProviderId, nextTaskType);
        if (fallback?.id) {
          updates.modelOverrideProviderId = baseProviderId;
          updates.modelOverrideModelId = fallback.id;
        }
      }
      updateNodeData(updates);
    };
    const duplicateFieldKeys = agentDefaultAnalysis.duplicated.map((item) => item.fieldKey);
    const clearDuplicatedAgentDefaults = () => {
      if (duplicateFieldKeys.length === 0) {
        return;
      }
      const updates: Partial<CustomNodeData> = {};
      duplicateFieldKeys.forEach((fieldKey) => {
        (updates as Record<string, undefined>)[String(fieldKey)] = undefined;
      });
      updateNodeData(updates);
    };
    const renderAgentDefaultFieldList = (
      title: string,
      items: typeof agentDefaultAnalysis.inherited,
      toneClassName: string,
      emptyText: string
    ) => (
      <div>
        <div className="text-[11px] text-slate-400 mb-1">{title}</div>
        {items.length === 0 ? (
          <div className="text-[10px] text-slate-500">{emptyText}</div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {items.map((item) => (
              <div
                key={`${item.status}-${item.fieldKey}`}
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] ${toneClassName}`}
              >
                <span className="font-medium">{item.label}</span>
                <span className="opacity-80">
                  {item.status === 'overridden'
                    ? `${item.agentValue || '默认'} → ${item.nodeValue || '空'}`
                    : item.agentValue || item.nodeValue || '已配置'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    );

    return (
      <div className="space-y-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1.5">选择智能体</label>
          <AgentSelector
            value={nodeData.agentId || ''}
            agentName={nodeData.agentName || ''}
            onResolvedAgent={setResolvedAgent}
            onChange={(agentId, agentName, agent) => {
              updateNodeData({
                agentId,
                agentName,
                agentProviderId: agent?.providerId || '',
                agentModelId: agent?.modelId || '',
                modelOverrideProviderId: '',
                modelOverrideModelId: '',
                ...buildAgentNodeDefaultsFromAgent(agent),
              });
            }}
          />
        </div>

        {resolvedAgent && (
          <div className="p-2.5 rounded-lg border border-teal-500/20 bg-teal-500/5 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs text-teal-300 font-medium">Agent 默认值继承分析</div>
                <div className="mt-1 text-[10px] text-slate-500">
                  节点会继承 Agent 默认值；只有与默认不同的字段才值得保留在节点上。
                </div>
              </div>
              {agentDefaultAnalysis.duplicated.length > 0 && (
                <button
                  type="button"
                  onClick={clearDuplicatedAgentDefaults}
                  className="px-2 py-1 rounded border border-amber-500/30 bg-amber-500/10 text-[10px] text-amber-200 hover:bg-amber-500/20 transition-colors"
                >
                  清理重复字段 {agentDefaultAnalysis.duplicated.length}
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5 text-[10px]">
              {resolvedAgent.source?.label && (
                <div className="inline-flex px-1.5 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-200">
                  来源: {resolvedAgent.source.label}
                </div>
              )}
              {resolvedAgent.runtime?.label && (
                <div className="inline-flex px-1.5 py-0.5 rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-200">
                  Runtime: {resolvedAgent.runtime.label}
                </div>
              )}
              <div className="inline-flex px-1.5 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
                继承 {agentDefaultAnalysis.inherited.length}
              </div>
              <div className="inline-flex px-1.5 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-200">
                重复 {agentDefaultAnalysis.duplicated.length}
              </div>
              <div className="inline-flex px-1.5 py-0.5 rounded border border-indigo-500/30 bg-indigo-500/10 text-indigo-200">
                覆盖 {agentDefaultAnalysis.overridden.length}
              </div>
            </div>
            {renderAgentDefaultFieldList(
              '继承中的默认值',
              agentDefaultAnalysis.inherited.slice(0, 8),
              'border border-emerald-500/20 bg-emerald-500/10 text-emerald-200',
              '当前没有可继承的 Agent 默认值。'
            )}
            {renderAgentDefaultFieldList(
              '与 Agent 默认重复的节点字段',
              agentDefaultAnalysis.duplicated,
              'border border-amber-500/20 bg-amber-500/10 text-amber-200',
              '当前没有重复字段。'
            )}
            {renderAgentDefaultFieldList(
              '节点级覆盖',
              agentDefaultAnalysis.overridden,
              'border border-indigo-500/20 bg-indigo-500/10 text-indigo-200',
              '当前没有节点级覆盖。'
            )}
          </div>
        )}

        <div className="p-2.5 rounded-lg border border-indigo-500/20 bg-indigo-500/5">
          <div className="text-xs text-indigo-300 font-medium mb-2">节点级模型覆盖（可选）</div>
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">覆盖提供商</label>
              <select
                value={selectedProviderId}
                onChange={(e) => {
                  const providerId = e.target.value;
                  const provider = providers.find((item) => item.providerId === providerId);
                  const firstModel = pickProviderDefaultModel(provider, selectedTaskType);
                  updateNodeData({
                    modelOverrideProviderId: providerId,
                    modelOverrideModelId: providerId ? firstModel?.id || '' : '',
                  });
                }}
                data-field-key="modelOverrideProviderId"
                disabled={providersLoading}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 disabled:opacity-50"
              >
                <option value="">跟随智能体默认</option>
                {providers.map((provider) => (
                  <option key={provider.providerId} value={provider.providerId}>
                    {provider.providerName}
                  </option>
                ))}
              </select>
            </div>
            {selectedProviderId && (
              <div>
                <label className="block text-xs text-slate-500 mb-1.5">覆盖模型</label>
                <select
                  value={nodeData.modelOverrideModelId || ''}
                  onChange={(e) => updateNodeData({ modelOverrideModelId: e.target.value })}
                  data-field-key="modelOverrideModelId"
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
                    当前提供商没有可用于该任务的兼容模型，已阻止回退到不兼容模型。
                  </div>
                )}
                {selectedOverrideModel &&
                  !modelSupportsTask(selectedOverrideModel, selectedTaskType) && (
                    <div className="mt-1 text-[10px] text-amber-300">
                      当前覆盖模型与任务类型不匹配，建议清空或切换到兼容模型。
                    </div>
                  )}
              </div>
            )}
            <div className="text-[10px] text-slate-500">
              当前生效模型：
              {effectiveProvider && effectiveModel
                ? `${effectiveProvider} / ${effectiveModel}`
                : '未配置'}
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">覆盖 Profile ID（可选）</label>
              <input
                type="text"
                value={nodeData.modelOverrideProfileId || ''}
                onChange={(e) => updateNodeData({ modelOverrideProfileId: e.target.value })}
                data-field-key="modelOverrideProfileId"
                placeholder="例如 profile-google-prod"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20"
              />
              <div className="mt-1 text-[10px] text-slate-500">
                仅在同 Provider 多配置档并存时使用；留空则按当前活动配置。
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-slate-500 mb-1.5">温度（可选）</label>
                <input
                  type="number"
                  min={0}
                  max={2}
                  step={0.1}
                  value={nodeData.agentTemperature ?? ''}
                  onChange={(e) => {
                    const raw = e.target.value.trim();
                    updateNodeData({ agentTemperature: raw === '' ? undefined : Number(raw) });
                  }}
                  data-field-key="agentTemperature"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20"
                  placeholder="默认"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1.5">Max Tokens（可选）</label>
                <input
                  type="number"
                  min={1}
                  max={65536}
                  step={1}
                  value={nodeData.agentMaxTokens ?? ''}
                  onChange={(e) => {
                    const raw = e.target.value.trim();
                    updateNodeData({ agentMaxTokens: raw === '' ? undefined : Number(raw) });
                  }}
                  data-field-key="agentMaxTokens"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20"
                  placeholder="默认"
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-300">
              <input
                type="checkbox"
                checked={Boolean(nodeData.agentPreferLatestModel)}
                onChange={(e) => updateNodeData({ agentPreferLatestModel: e.target.checked })}
                data-field-key="agentPreferLatestModel"
                className="accent-indigo-500"
              />
              优先自动选择当前任务可用的最新模型
            </label>
          </div>
        </div>

        {/* 任务类型选择 */}
        <div>
          <label className="block text-xs text-slate-500 mb-1.5">任务类型</label>
          <select
            value={nodeData.agentTaskType || 'chat'}
            onChange={(e) => {
              const nextTaskType = (
                [
                  'chat',
                  'image-gen',
                  'image-edit',
                  'video-gen',
                  'audio-gen',
                  'vision-understand',
                  'data-analysis',
                ].includes(e.target.value)
                  ? e.target.value
                  : 'chat'
              ) as AgentTaskType;
              handleAgentTaskTypeChange(nextTaskType);
            }}
            data-field-key="agentTaskType"
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20"
          >
            {taskOptions.map((option) => {
              const unsupported =
                hasEffectiveTaskConstraint && !effectiveSupportedTasks.includes(option.value);
              return (
                <option
                  key={`agent-task-${option.value}`}
                  value={option.value}
                  disabled={unsupported && option.value !== selectedTaskType}
                >
                  {option.label}
                  {unsupported ? '（当前模型不支持）' : ''}
                </option>
              );
            })}
          </select>
          {hasEffectiveTaskConstraint && (
            <div className="mt-1 text-[10px] text-slate-500">
              当前模型支持：{effectiveSupportedTasks.join(' / ')}
            </div>
          )}
          {hasEffectiveTaskConstraint && !effectiveSupportedTasks.includes(selectedTaskType) && (
            <div className="mt-1 text-[10px] text-amber-300">
              当前任务类型与生效模型不匹配，建议切换任务类型或模型。
            </div>
          )}
          {hasAgentReferenceImage && !taskSupportsReferenceImage && (
            <div className="mt-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-2">
              <div className="text-[11px] text-rose-300">
                当前节点已配置参考图，但任务类型是 `{selectedTaskType}`。请改为 `vision-understand`
                或 `image-edit`。
              </div>
              <button
                type="button"
                onClick={() => handleAgentTaskTypeChange('vision-understand')}
                className="mt-2 px-2 py-1 text-[11px] rounded border border-indigo-500/40 bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20"
              >
                一键改为图片理解
              </button>
            </div>
          )}
        </div>

        {/* ========== 图片生成参数（抽离至 ./agentSections/AgentImageGenSection） ========== */}
        {nodeData.agentTaskType === 'image-gen' && (
          <AgentImageGenSection nodeData={nodeData} updateNodeData={updateNodeData} />
        )}

        {/* ========== 图片理解参数 ========== */}
        {nodeData.agentTaskType === 'vision-understand' &&
          (() => {
            const hasRef = !!nodeData.agentReferenceImageUrl;
            return (
              <div className="space-y-3 p-2.5 rounded-lg border border-indigo-500/20 bg-indigo-500/5">
                <div className="text-xs text-indigo-300 font-medium">图片理解参数</div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">
                    参考图片 <span className="text-red-400">*</span>
                  </label>
                  {hasRef && nodeData.agentReferenceImageUrl?.startsWith('data:') && (
                    <div className="mb-2 relative group">
                      <img
                        src={nodeData.agentReferenceImageUrl}
                        alt="参考图片"
                        className="w-full h-24 object-cover rounded border border-indigo-500/30"
                      />
                      <button
                        onClick={() => updateNodeData({ agentReferenceImageUrl: '' })}
                        className="absolute top-1 right-1 p-0.5 bg-red-500/80 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X size={10} />
                      </button>
                    </div>
                  )}
                  <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-indigo-500/40 rounded-lg cursor-pointer hover:border-indigo-500/60 transition-colors">
                    <Upload size={12} className="text-indigo-300" />
                    <span className="text-xs text-indigo-200">
                      {hasRef ? '更换图片' : '上传参考图片'}
                    </span>
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        try {
                          const [encoded] = await readInlineFilesAsDataUrls([file], '参考图片');
                          updateNodeData({ agentReferenceImageUrl: encoded || '' });
                        } catch (error) {
                          reportInlineUploadError('参考图片读取失败', error);
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
                    className="mt-1.5 w-full px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-400 font-mono focus:outline-none focus:border-indigo-500/50"
                    placeholder="或输入 URL / {{prev.output.imageUrl}}"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">输出格式</label>
                  <select
                    value={nodeData.agentOutputFormat || 'json'}
                    onChange={(e) => updateNodeData({ agentOutputFormat: e.target.value })}
                    data-field-key="agentOutputFormat"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
                  >
                    <option value="json">JSON（推荐）</option>
                    <option value="markdown">Markdown</option>
                    <option value="text">Text</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">理解任务说明</label>
                  <textarea
                    value={nodeData.inputMapping || ''}
                    onChange={(e) => updateNodeData({ inputMapping: e.target.value })}
                    rows={2}
                    data-field-key="inputMapping"
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-indigo-500/50 resize-none"
                    placeholder="例如：识别主体、颜色、材质，并给出可保留/需规避元素"
                  />
                </div>
              </div>
            );
          })()}

        {/* ========== 图片编辑参数（抽离至 ./agentSections/AgentImageEditSection） ========== */}
        {nodeData.agentTaskType === 'image-edit' && (
          <AgentImageEditSection nodeData={nodeData} updateNodeData={updateNodeData} />
        )}

        {/* ========== 视频生成参数（抽离至 ./agentSections/AgentVideoGenSection） ========== */}
        {nodeData.agentTaskType === 'video-gen' && (
          <AgentVideoGenSection
            nodeData={nodeData}
            updateNodeData={updateNodeData}
            workflowVideoSchema={workflowVideoSchema}
            workflowVideoControlContract={workflowVideoControlContract}
          />
        )}

        {/* ========== 音频生成参数（抽离至 ./agentSections/AgentAudioGenSection） ========== */}
        {nodeData.agentTaskType === 'audio-gen' && (
          <AgentAudioGenSection nodeData={nodeData} updateNodeData={updateNodeData} />
        )}

        {/* ========== 数据分析参数（抽离至 ./agentSections/AgentDataAnalysisSection） ========== */}
        {nodeData.agentTaskType === 'data-analysis' && (
          <AgentDataAnalysisSection nodeData={nodeData} updateNodeData={updateNodeData} />
        )}

        {/* 输出格式（对话模式） */}
        {(!nodeData.agentTaskType || nodeData.agentTaskType === 'chat') && (
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">输出格式</label>
            <select
              value={nodeData.agentOutputFormat || ''}
              onChange={(e) => updateNodeData({ agentOutputFormat: e.target.value })}
              data-field-key="agentOutputFormat"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
            >
              <option value="">默认（文本）</option>
              <option value="text">纯文本</option>
              <option value="json">JSON</option>
              <option value="markdown">Markdown</option>
            </select>
          </div>
        )}

        <div>
          <label className="block text-xs text-slate-500 mb-1">节点指令</label>
          <div className="flex items-start gap-1 mb-1.5">
            <Info size={10} className="text-slate-600 mt-0.5 flex-shrink-0" />
            <span className="text-[10px] text-slate-600">追加到 Agent System Prompt</span>
          </div>
          <textarea
            value={nodeData.instructions || ''}
            onChange={(e) => updateNodeData({ instructions: e.target.value })}
            rows={4}
            data-field-key="instructions"
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
            placeholder="例如：请用中文回答，输出 JSON 格式..."
          />
        </div>

        <div>
          <label className="block text-xs text-slate-500 mb-1">输入映射</label>
          <div className="flex items-start gap-1 mb-1.5">
            <Info size={10} className="text-slate-600 mt-0.5 flex-shrink-0" />
            <span className="text-[10px] text-slate-600">留空默认使用上一节点输出</span>
          </div>
          <textarea
            value={nodeData.inputMapping || ''}
            onChange={(e) => updateNodeData({ inputMapping: e.target.value })}
            rows={2}
            data-field-key="inputMapping"
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 font-mono focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
            placeholder="{{prev.output.text}}"
          />
        </div>
      </div>
    );
  }

  return null;
};
