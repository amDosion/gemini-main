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
import {
  reportInlineUploadError,
  readInlineFilesAsDataUrls,
} from '../uploadHandlers';

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
                <label className="block text-xs text-slate-500 mb-1.5">
                  覆盖 Profile ID（可选）
                </label>
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
                  当前节点已配置参考图，但任务类型是 `{selectedTaskType}`。请改为
                  `vision-understand` 或 `image-edit`。
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

          {/* ========== 图片生成参数 ========== */}
          {nodeData.agentTaskType === 'image-gen' &&
            (() => {
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
                            agentNumberOfImages: e.target.value
                              ? Number(e.target.value)
                              : undefined,
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
            })()}

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

          {/* ========== 图片编辑参数 ========== */}
          {nodeData.agentTaskType === 'image-edit' &&
            (() => {
              const _tier = nodeData.agentResolutionTier || '1K';
              const _ratio = nodeData.agentAspectRatio || '1:1';
              const _ratios = ['1:1', '2:3', '3:2', '3:4', '4:3', '9:16', '16:9', '21:9'];
              const _tiers = [
                { v: '1K', l: '1K 标准' },
                { v: '2K', l: '2K 高清' },
                { v: '4K', l: '4K 超清' },
              ];
              const _hasRef = !!nodeData.agentReferenceImageUrl;
              return (
                <div className="space-y-3 p-2.5 rounded-lg border border-purple-500/20 bg-purple-500/5">
                  <div className="text-xs text-purple-300 font-medium">图片编辑参数</div>
                  {/* 参考图片上传 */}
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">
                      参考图片 <span className="text-red-400">*</span>
                    </label>
                    {_hasRef && nodeData.agentReferenceImageUrl?.startsWith('data:') && (
                      <div className="mb-2 relative group">
                        <img
                          src={nodeData.agentReferenceImageUrl}
                          alt="参考图片"
                          className="w-full h-24 object-cover rounded border border-purple-500/30"
                        />
                        <button
                          onClick={() => updateNodeData({ agentReferenceImageUrl: '' })}
                          className="absolute top-1 right-1 p-0.5 bg-red-500/80 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <X size={10} />
                        </button>
                      </div>
                    )}
                    <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-purple-500/40 rounded-lg cursor-pointer hover:border-purple-500/60 transition-colors">
                      <Upload size={12} className="text-purple-400" />
                      <span className="text-xs text-purple-300">
                        {_hasRef ? '更换图片' : '上传参考图片'}
                      </span>
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
                            agentNumberOfImages: e.target.value
                              ? Number(e.target.value)
                              : undefined,
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
                        onChange={(e) =>
                          updateNodeData({ agentPreserveProductIdentity: e.target.checked })
                        }
                        data-field-key="agentPreserveProductIdentity"
                        className="accent-purple-500"
                      />
                      保留主体
                    </label>
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">重试次数</label>
                      <select
                        value={nodeData.agentImageEditMaxRetries ?? 1}
                        onChange={(e) =>
                          updateNodeData({ agentImageEditMaxRetries: Number(e.target.value) })
                        }
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
                        const safe = Number.isFinite(raw)
                          ? Math.max(50, Math.min(95, Math.round(raw)))
                          : 70;
                        updateNodeData({ agentProductMatchThreshold: safe });
                      }}
                      data-field-key="agentProductMatchThreshold"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-purple-500/50"
                    />
                  </div>
                </div>
              );
            })()}

          {/* ========== 视频生成参数 ========== */}
          {nodeData.agentTaskType === 'video-gen' &&
            (() => {
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
                      nodeData.agentGenerateAudio ??
                      workflowVideoControlContract.defaultGenerateAudio
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
                            onChange={(e) =>
                              updateNodeData({ agentSubtitleScript: e.target.value })
                            }
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
                          ...(e.target.checked
                            ? { agentContinueFromPreviousLastFrame: false }
                            : {}),
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
            })()}

          {/* ========== 音频生成参数 ========== */}
          {nodeData.agentTaskType === 'audio-gen' &&
            (() => {
              const audioFormat = nodeData.agentAudioFormat || 'mp3';
              const audioSpeed = nodeData.agentSpeechSpeed ?? 1;
              return (
                <div className="space-y-3 p-2.5 rounded-lg border border-sky-500/20 bg-sky-500/5">
                  <div className="text-xs text-sky-300 font-medium">音频生成参数</div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">音色</label>
                    <input
                      type="text"
                      value={nodeData.agentVoice || ''}
                      onChange={(e) => updateNodeData({ agentVoice: e.target.value })}
                      data-field-key="agentVoice"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
                      placeholder="留空时使用 provider 默认音色"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">输出格式</label>
                      <select
                        value={audioFormat}
                        onChange={(e) => updateNodeData({ agentAudioFormat: e.target.value })}
                        data-field-key="agentAudioFormat"
                        className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
                      >
                        <option value="mp3">MP3</option>
                        <option value="wav">WAV</option>
                        <option value="opus">OPUS</option>
                        <option value="aac">AAC</option>
                        <option value="flac">FLAC</option>
                        <option value="pcm">PCM</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">语速</label>
                      <input
                        type="number"
                        min={0.25}
                        max={4}
                        step={0.25}
                        value={audioSpeed}
                        onChange={(e) => {
                          const raw = Number(e.target.value);
                          const safe = Number.isFinite(raw) ? Math.max(0.25, Math.min(4, raw)) : 1;
                          updateNodeData({ agentSpeechSpeed: safe });
                        }}
                        data-field-key="agentSpeechSpeed"
                        className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
                      />
                    </div>
                  </div>
                </div>
              );
            })()}

          {/* ========== 数据分析参数 ========== */}
          {nodeData.agentTaskType === 'data-analysis' &&
            (() => {
              const _hasFile = !!nodeData.agentFileUrl;
              const _fileName = nodeData.agentFileUrl?.startsWith('data:')
                ? '已上传文件'
                : nodeData.agentFileUrl || '';
              return (
                <div className="space-y-3 p-2.5 rounded-lg border border-cyan-500/20 bg-cyan-500/5">
                  <div className="text-xs text-cyan-300 font-medium">数据分析参数</div>
                  {/* 文件上传 */}
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">
                      数据文件 <span className="text-red-400">*</span>
                    </label>
                    {_hasFile && (
                      <div className="mb-2 flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 rounded border border-cyan-500/30">
                        <FileSpreadsheet size={14} className="text-cyan-400 flex-shrink-0" />
                        <span className="text-[10px] text-slate-300 truncate flex-1">
                          {_fileName}
                        </span>
                        <button
                          onClick={() => updateNodeData({ agentFileUrl: '' })}
                          className="p-0.5 hover:bg-red-500/20 rounded text-red-400"
                        >
                          <X size={10} />
                        </button>
                      </div>
                    )}
                    <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-cyan-500/40 rounded-lg cursor-pointer hover:border-cyan-500/60 transition-colors">
                      <Upload size={12} className="text-cyan-400" />
                      <span className="text-xs text-cyan-300">
                        {_hasFile ? '更换文件' : '上传文件'}
                      </span>
                      <input
                        type="file"
                        accept=".csv,.xlsx,.xls,.json,.tsv,.txt"
                        className="hidden"
                        onChange={async (e) => {
                          const f = e.target.files?.[0];
                          if (!f) return;
                          try {
                            updateNodeData({ agentFileUrl: await fileToBase64(f) });
                          } catch {
                            /* ignore */
                          }
                          e.target.value = '';
                        }}
                      />
                    </label>
                    <input
                      type="text"
                      value={
                        !nodeData.agentFileUrl?.startsWith('data:')
                          ? nodeData.agentFileUrl || ''
                          : ''
                      }
                      onChange={(e) => updateNodeData({ agentFileUrl: e.target.value })}
                      data-field-key="agentFileUrl"
                      className="mt-1.5 w-full px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-400 font-mono focus:outline-none focus:border-cyan-500/50"
                      placeholder="或输入 URL / {{prev.output.fileUrl}}"
                    />
                    <div className="mt-1 text-[10px] text-slate-600">
                      支持 Excel / CSV / JSON / TSV 文件
                    </div>
                  </div>
                  {/* 输出格式 */}
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">输出格式</label>
                    <select
                      value={nodeData.agentOutputFormat || ''}
                      onChange={(e) => updateNodeData({ agentOutputFormat: e.target.value })}
                      data-field-key="agentOutputFormat"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                    >
                      <option value="">默认（文本）</option>
                      <option value="text">纯文本</option>
                      <option value="json">JSON</option>
                      <option value="markdown">Markdown 表格</option>
                    </select>
                  </div>
                </div>
              );
            })()}

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
