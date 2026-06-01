import React from 'react';
import { AlertCircle, Loader2, Save, X } from 'lucide-react';
import type { AgentDef } from '../types';
import { createDefaultAgentCard } from '../agentRegistryService';
import {
  AgentTaskType,
  AGENT_TASK_TYPES,
  ProviderModels,
  formatModelTaskHint,
  resolveProviderTaskModelSelection,
} from '../providerModelUtils';

const ICONS = ['🤖', '🧠', '📝', '🔍', '💡', '🎯', '📊', '🛠️', '🎨', '📚', '🌐', '⚡', '✨', '🔬'];
const ALLOWED_TASK_TYPES: AgentTaskType[] = AGENT_TASK_TYPES;

interface AgentManagerEditorFormProps {
  editing: AgentDef;
  isNew: boolean;
  saving: boolean;
  providers: ProviderModels[];
  onCancel: () => void;
  onSave: () => void;
  onChange: (next: AgentDef) => void;
}

export const AgentManagerEditorForm: React.FC<AgentManagerEditorFormProps> = ({
  editing,
  isNew,
  saving,
  providers,
  onCancel,
  onSave,
  onChange,
}) => {
  const baseDefaults = createDefaultAgentCard().defaults;

  const currentCard = editing.agentCard || createDefaultAgentCard();
  const defaults = currentCard.defaults || baseDefaults;
  const defaultTaskType = defaults.defaultTaskType || 'chat';
  const normalizedTaskType: AgentTaskType = ALLOWED_TASK_TYPES.includes(defaultTaskType as AgentTaskType)
    ? (defaultTaskType as AgentTaskType)
    : 'chat';

  const modelSelection = resolveProviderTaskModelSelection({
    providers,
    providerId: editing.providerId,
    modelId: editing.modelId,
    taskType: normalizedTaskType,
  });
  const selectedModelCompatible = modelSelection.selectedModelSupportsTask;
  const selectedModel = modelSelection.selectedModel;
  const currentModels = modelSelection.selectedModels;
  const currentModelValue = selectedModelCompatible ? editing.modelId : '';
  const hasCompatibleModels = modelSelection.compatibleModels.length > 0;
  const canSave = Boolean(
    editing.name.trim() &&
    editing.providerId &&
    currentModelValue &&
    selectedModelCompatible &&
    hasCompatibleModels &&
    !saving
  );

  const imageGenerationDefaults = defaults.imageGeneration || baseDefaults.imageGeneration;
  const imageEditDefaults = defaults.imageEdit || baseDefaults.imageEdit;
  const videoGenerationDefaults = defaults.videoGeneration || baseDefaults.videoGeneration;
  const audioGenerationDefaults = defaults.audioGeneration || baseDefaults.audioGeneration;
  const visionUnderstandDefaults = defaults.visionUnderstand || baseDefaults.visionUnderstand;
  const dataAnalysisDefaults = defaults.dataAnalysis || baseDefaults.dataAnalysis;

  const patchAgentCard = (patch: Partial<typeof defaults>) => {
    onChange({
      ...editing,
      agentCard: {
        ...currentCard,
        defaults: {
          ...defaults,
          ...patch,
        },
      },
    });
  };

  const pickCompatibleModelId = (provider: ProviderModels | undefined, taskType: AgentTaskType): string => {
    return resolveProviderTaskModelSelection({
      providers,
      providerId: provider?.providerId || '',
      taskType,
    }).pickCompatibleModel()?.id || '';
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 text-slate-200">
      <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
        <span className="text-sm font-bold">{isNew ? '创建 Agent' : '编辑 Agent'}</span>
        <button onClick={onCancel} className="p-1 hover:bg-slate-800 rounded">
          <X size={16} className="text-slate-400" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1.5">图标</label>
          <div className="flex gap-1 flex-wrap">
            {ICONS.map((iconValue) => (
              <button
                key={iconValue}
                onClick={() => onChange({ ...editing, icon: iconValue })}
                className={`w-8 h-8 rounded text-lg flex items-center justify-center transition-colors ${
                  editing.icon === iconValue ? 'bg-teal-600 ring-2 ring-teal-400' : 'bg-slate-800 hover:bg-slate-700'
                }`}
              >
                {iconValue}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1.5">颜色</label>
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={editing.color || '#14b8a6'}
              onChange={(event) => onChange({ ...editing, color: event.target.value })}
              className="h-9 w-12 p-1 bg-slate-800 border border-slate-700 rounded"
            />
            <input
              value={editing.color}
              onChange={(event) => onChange({ ...editing, color: event.target.value })}
              className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30"
              placeholder="#14b8a6"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1.5">名称 *</label>
          <input
            value={editing.name}
            onChange={(event) => onChange({ ...editing, name: event.target.value })}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30"
            placeholder="例如：翻译助手"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1.5">描述</label>
          <input
            value={editing.description}
            onChange={(event) => onChange({ ...editing, description: event.target.value })}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30"
            placeholder="Agent 的功能描述"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1.5">LLM 提供商 *</label>
          {providers.length === 0 ? (
            <div className="flex items-center gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
              <AlertCircle size={14} className="text-amber-400 flex-shrink-0" />
              <span className="text-xs text-amber-300">未配置任何提供商，请先在设置中添加 API Key</span>
            </div>
          ) : (
            <select
              value={editing.providerId}
              onChange={(event) => {
                const providerId = event.target.value;
                const nextProvider = providers.find((provider) => provider.providerId === providerId);
                onChange({
                  ...editing,
                  providerId,
                  modelId: pickCompatibleModelId(nextProvider, normalizedTaskType),
                });
              }}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30"
            >
              {providers.map((provider) => (
                <option key={provider.providerId} value={provider.providerId}>
                  {provider.providerName}
                </option>
              ))}
            </select>
          )}
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1.5">模型 *</label>
          {currentModels.length === 0 ? (
            <div className="p-3 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-500">
              当前任务类型暂无兼容模型
            </div>
          ) : (
            <select
              value={currentModelValue}
              onChange={(event) => onChange({ ...editing, modelId: event.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30"
            >
              {!currentModelValue && (
                <option value="">请选择兼容模型</option>
              )}
              {currentModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name} · {formatModelTaskHint(model.supportedTasks)}
                </option>
              ))}
            </select>
          )}
          {editing.modelId && <div className="mt-1 text-[10px] text-slate-500 font-mono">{editing.modelId}</div>}
          {modelSelection.compatibleModels.length === 0 && modelSelection.providerModels.length > 0 && (
            <div className="mt-1 text-[10px] text-amber-300">
              当前任务类型没有兼容模型，请切换提供商或任务类型。
            </div>
          )}
          {!selectedModelCompatible && selectedModel && (
            <div className="mt-1 text-[10px] text-amber-300">
              当前模型与任务类型不匹配，保存前必须切换到支持 {normalizedTaskType} 的模型。
            </div>
          )}
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1.5">System Prompt</label>
          <textarea
            value={editing.systemPrompt}
            onChange={(event) => onChange({ ...editing, systemPrompt: event.target.value })}
            rows={5}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30 resize-none"
            placeholder="定义 Agent 的行为和角色..."
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs text-slate-400">Temperature</label>
            <span className="text-xs text-teal-400 font-mono">{editing.temperature}</span>
          </div>
          <input
            type="range"
            min="0"
            max="2"
            step="0.1"
            value={editing.temperature}
            onChange={(event) => onChange({ ...editing, temperature: parseFloat(event.target.value) })}
            className="w-full accent-teal-500"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1.5">Max Tokens</label>
          <input
            type="number"
            min={1}
            value={editing.maxTokens}
            onChange={(event) => onChange({ ...editing, maxTokens: parseInt(event.target.value, 10) || 4096 })}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30"
          />
        </div>

        <div className="p-3 rounded-lg border border-indigo-500/20 bg-indigo-500/5 space-y-3">
          <div className="text-xs text-indigo-300 font-medium">默认工作流能力</div>
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">默认任务类型</label>
            <select
              value={defaultTaskType}
              onChange={(event) => {
                const nextTaskType = event.target.value as AgentTaskType;
                const nextDefaults: Record<string, unknown> = {
                  ...defaults,
                  defaultTaskType: nextTaskType,
                };
                if (nextTaskType === 'image-gen' && (!nextDefaults.imageGeneration || typeof nextDefaults.imageGeneration !== 'object')) {
                  nextDefaults.imageGeneration = { ...baseDefaults.imageGeneration };
                }
                if (nextTaskType === 'image-edit' && (!nextDefaults.imageEdit || typeof nextDefaults.imageEdit !== 'object')) {
                  nextDefaults.imageEdit = { ...baseDefaults.imageEdit };
                }
                if (nextTaskType === 'video-gen' && (!nextDefaults.videoGeneration || typeof nextDefaults.videoGeneration !== 'object')) {
                  nextDefaults.videoGeneration = { ...baseDefaults.videoGeneration };
                }
                if (nextTaskType === 'audio-gen' && (!nextDefaults.audioGeneration || typeof nextDefaults.audioGeneration !== 'object')) {
                  nextDefaults.audioGeneration = { ...baseDefaults.audioGeneration };
                }
                if (nextTaskType === 'vision-understand' && (!nextDefaults.visionUnderstand || typeof nextDefaults.visionUnderstand !== 'object')) {
                  nextDefaults.visionUnderstand = { ...baseDefaults.visionUnderstand };
                }
                if (nextTaskType === 'data-analysis' && (!nextDefaults.dataAnalysis || typeof nextDefaults.dataAnalysis !== 'object')) {
                  nextDefaults.dataAnalysis = { ...baseDefaults.dataAnalysis };
                }
                onChange({
                  ...editing,
                  modelId: resolveProviderTaskModelSelection({
                    providers,
                    providerId: editing.providerId,
                    modelId: editing.modelId,
                    taskType: nextTaskType,
                  }).selectedModelSupportsTask
                    ? editing.modelId
                    : pickCompatibleModelId(modelSelection.selectedProvider, nextTaskType),
                  agentCard: {
                    ...currentCard,
                    defaults: nextDefaults,
                  },
                });
              }}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30"
            >
              <option value="chat">💬 对话</option>
              <option value="image-gen">🖼️ 图片生成</option>
              <option value="image-edit">🪄 图片编辑</option>
              <option value="video-gen">🎬 视频生成</option>
              <option value="audio-gen">🎧 音频生成</option>
              <option value="vision-understand">🧠 图片理解</option>
              <option value="data-analysis">📊 数据分析</option>
            </select>
          </div>

          {defaultTaskType === 'image-gen' && (
            <div className="grid grid-cols-2 gap-2">
              <input
                value={imageGenerationDefaults.aspectRatio || '1:1'}
                onChange={(event) => patchAgentCard({
                  imageGeneration: {
                    ...imageGenerationDefaults,
                    aspectRatio: event.target.value,
                  },
                })}
                className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs focus:outline-none focus:border-teal-500/50"
                placeholder="宽高比 (1:1)"
              />
              <input
                value={imageGenerationDefaults.resolutionTier || '1K'}
                onChange={(event) => patchAgentCard({
                  imageGeneration: {
                    ...imageGenerationDefaults,
                    resolutionTier: event.target.value,
                  },
                })}
                className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs focus:outline-none focus:border-teal-500/50"
                placeholder="分辨率档位 (1K)"
              />
              <input
                type="number"
                min={1}
                max={4}
                value={imageGenerationDefaults.numberOfImages ?? 1}
                onChange={(event) => patchAgentCard({
                  imageGeneration: {
                    ...imageGenerationDefaults,
                    numberOfImages: Math.max(1, Number(event.target.value) || 1),
                  },
                })}
                className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs focus:outline-none focus:border-teal-500/50"
                placeholder="数量"
              />
              <input
                value={imageGenerationDefaults.outputMimeType || 'image/png'}
                onChange={(event) => patchAgentCard({
                  imageGeneration: {
                    ...imageGenerationDefaults,
                    outputMimeType: event.target.value,
                  },
                })}
                className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs focus:outline-none focus:border-teal-500/50"
                placeholder="输出 MIME (image/png)"
              />
              <label className="col-span-2 flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={Boolean(imageGenerationDefaults.promptExtend)}
                  onChange={(event) => patchAgentCard({
                    imageGeneration: {
                      ...imageGenerationDefaults,
                      promptExtend: event.target.checked,
                    },
                  })}
                  className="accent-teal-500"
                />
                启用提示词优化（provider 支持时生效）
              </label>
              <label className="col-span-2 flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={imageGenerationDefaults.addMagicSuffix !== false}
                  onChange={(event) => patchAgentCard({
                    imageGeneration: {
                      ...imageGenerationDefaults,
                      addMagicSuffix: event.target.checked,
                    },
                  })}
                  className="accent-teal-500"
                />
                启用提示词增强后缀（provider 支持时生效）
              </label>
            </div>
          )}

          {defaultTaskType === 'image-edit' && (
            <div className="grid grid-cols-2 gap-2">
              <label className="space-y-1 text-xs text-slate-400">
                <span>编辑模式</span>
                <input
                  value={imageEditDefaults.editMode || 'image-chat-edit'}
                  onChange={(event) => patchAgentCard({
                    imageEdit: {
                      ...imageEditDefaults,
                      editMode: event.target.value,
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>宽高比</span>
                <input
                  value={imageEditDefaults.aspectRatio || ''}
                  onChange={(event) => patchAgentCard({
                    imageEdit: {
                      ...imageEditDefaults,
                      aspectRatio: event.target.value,
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  placeholder="可空"
                />
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>图片尺寸</span>
                <input
                  value={imageEditDefaults.imageSize || '1K'}
                  onChange={(event) => patchAgentCard({
                    imageEdit: {
                      ...imageEditDefaults,
                      imageSize: event.target.value,
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>分辨率档位</span>
                <input
                  value={imageEditDefaults.resolutionTier || '1K'}
                  onChange={(event) => patchAgentCard({
                    imageEdit: {
                      ...imageEditDefaults,
                      resolutionTier: event.target.value,
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>图片数量</span>
                <input
                  type="number"
                  min={1}
                  max={4}
                  value={imageEditDefaults.numberOfImages ?? 1}
                  onChange={(event) => patchAgentCard({
                    imageEdit: {
                      ...imageEditDefaults,
                      numberOfImages: Math.max(1, Number(event.target.value) || 1),
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>输出 MIME</span>
                <input
                  value={imageEditDefaults.outputMimeType || 'image/png'}
                  onChange={(event) => patchAgentCard({
                    imageEdit: {
                      ...imageEditDefaults,
                      outputMimeType: event.target.value,
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>商品一致性阈值</span>
                <input
                  type="number"
                  min={50}
                  max={95}
                  value={imageEditDefaults.productMatchThreshold ?? 72}
                  onChange={(event) => patchAgentCard({
                    imageEdit: {
                      ...imageEditDefaults,
                      productMatchThreshold: Math.max(50, Math.min(95, Number(event.target.value) || 72)),
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>编辑重试次数</span>
                <input
                  type="number"
                  min={0}
                  max={3}
                  value={imageEditDefaults.maxRetries ?? 2}
                  onChange={(event) => patchAgentCard({
                    imageEdit: {
                      ...imageEditDefaults,
                      maxRetries: Math.max(0, Math.min(3, Number(event.target.value) || 0)),
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </label>
              <label className="col-span-2 space-y-1 text-xs text-slate-400">
                <span>输出语言</span>
                <input
                  value={imageEditDefaults.outputLanguage || ''}
                  onChange={(event) => patchAgentCard({
                    imageEdit: {
                      ...imageEditDefaults,
                      outputLanguage: event.target.value,
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  placeholder="例如 en / zh"
                />
              </label>
              <label className="col-span-2 flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={Boolean(imageEditDefaults.promptExtend)}
                  onChange={(event) => patchAgentCard({
                    imageEdit: {
                      ...imageEditDefaults,
                      promptExtend: event.target.checked,
                    },
                  })}
                  className="accent-teal-500"
                />
                启用编辑提示词优化（provider 支持时生效）
              </label>
              <label className="col-span-2 flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={imageEditDefaults.addMagicSuffix !== false}
                  onChange={(event) => patchAgentCard({
                    imageEdit: {
                      ...imageEditDefaults,
                      addMagicSuffix: event.target.checked,
                    },
                  })}
                  className="accent-teal-500"
                />
                启用提示词增强后缀（provider 支持时生效）
              </label>
              <label className="col-span-2 flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={Boolean(imageEditDefaults.preserveProductIdentity)}
                  onChange={(event) => patchAgentCard({
                    imageEdit: {
                      ...imageEditDefaults,
                      preserveProductIdentity: event.target.checked,
                    },
                  })}
                  className="accent-teal-500"
                />
                保留商品主体一致性
              </label>
            </div>
          )}

          {defaultTaskType === 'video-gen' && (
            <div className="grid grid-cols-2 gap-2">
              <label className="space-y-1 text-xs text-slate-400">
                <span>视频宽高比</span>
                <select
                  value={videoGenerationDefaults.aspectRatio || '16:9'}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      aspectRatio: event.target.value,
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                >
                  <option value="16:9">16:9 横屏</option>
                  <option value="9:16">9:16 竖屏</option>
                </select>
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>视频分辨率</span>
                <select
                  value={videoGenerationDefaults.resolution || '1080p'}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      resolution: event.target.value,
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                >
                  <option value="720p">720p</option>
                  <option value="1080p">1080p</option>
                  <option value="4k">4k</option>
                </select>
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>视频时长</span>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={videoGenerationDefaults.durationSeconds ?? 5}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      durationSeconds: Math.max(1, Math.min(20, Number(event.target.value) || 5)),
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>视频延长次数</span>
                <input
                  type="number"
                  min={0}
                  max={20}
                  value={videoGenerationDefaults.videoExtensionCount ?? 0}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      videoExtensionCount: Math.max(0, Math.min(20, Number(event.target.value) || 0)),
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>字幕模式</span>
                <select
                  value={videoGenerationDefaults.subtitleMode || 'none'}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      subtitleMode: event.target.value,
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                >
                  <option value="none">none</option>
                  <option value="vtt">vtt</option>
                  <option value="srt">srt</option>
                  <option value="both">both</option>
                </select>
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>字幕语言</span>
                <input
                  value={videoGenerationDefaults.subtitleLanguage || ''}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      subtitleLanguage: event.target.value,
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  placeholder="例如 zh-CN"
                />
              </label>
              <label className="space-y-1 text-xs text-slate-400">
                <span>随机种子</span>
                <input
                  type="number"
                  value={videoGenerationDefaults.seed ?? -1}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      seed: Number(event.target.value),
                    },
                  })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </label>
              <label className="col-span-2 flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={Boolean(videoGenerationDefaults.continueFromPreviousVideo)}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      continueFromPreviousVideo: event.target.checked,
                      ...(event.target.checked ? { continueFromPreviousLastFrame: false } : {}),
                    },
                  })}
                  className="accent-fuchsia-500"
                />
                顺序视频节点时自动续接上一段视频
              </label>
              <label className="col-span-2 flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={Boolean(videoGenerationDefaults.continueFromPreviousLastFrame)}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      continueFromPreviousLastFrame: event.target.checked,
                      ...(event.target.checked ? { continueFromPreviousVideo: false } : {}),
                    },
                  })}
                  className="accent-fuchsia-500"
                />
                顺序视频节点时以上一段最后一帧作为首帧
              </label>
              <label className="col-span-2 flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={videoGenerationDefaults.generateAudio !== false}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      generateAudio: event.target.checked,
                    },
                  })}
                  className="accent-fuchsia-500"
                />
                生成原生音频
              </label>
              <label className="col-span-2 flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={Boolean(videoGenerationDefaults.promptExtend)}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      promptExtend: event.target.checked,
                    },
                  })}
                  className="accent-fuchsia-500"
                />
                启用视频提示词优化
              </label>
              <label className="col-span-2 space-y-1 text-xs text-slate-400">
                <span>字幕脚本</span>
                <textarea
                  value={videoGenerationDefaults.subtitleScript || ''}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      subtitleScript: event.target.value,
                    },
                  })}
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 resize-none"
                />
              </label>
              <label className="col-span-2 space-y-1 text-xs text-slate-400">
                <span>反向提示词</span>
                <textarea
                  value={videoGenerationDefaults.negativePrompt || ''}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      negativePrompt: event.target.value,
                    },
                  })}
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 resize-none"
                />
              </label>
              <label className="col-span-2 space-y-1 text-xs text-slate-400">
                <span>分镜提示词</span>
                <textarea
                  value={videoGenerationDefaults.storyboardPrompt || ''}
                  onChange={(event) => patchAgentCard({
                    videoGeneration: {
                      ...videoGenerationDefaults,
                      storyboardPrompt: event.target.value,
                    },
                  })}
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 resize-none"
                />
              </label>
            </div>
          )}

          {defaultTaskType === 'audio-gen' && (
            <div className="grid grid-cols-2 gap-2">
              <input
                value={audioGenerationDefaults.voice || ''}
                onChange={(event) => patchAgentCard({
                  audioGeneration: {
                    ...audioGenerationDefaults,
                    voice: event.target.value,
                  },
                })}
                className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs focus:outline-none focus:border-teal-500/50"
                placeholder="音色（留空走 provider 默认）"
              />
              <select
                value={audioGenerationDefaults.responseFormat || 'mp3'}
                onChange={(event) => patchAgentCard({
                  audioGeneration: {
                    ...audioGenerationDefaults,
                    responseFormat: event.target.value,
                  },
                })}
                className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs focus:outline-none focus:border-teal-500/50"
              >
                <option value="mp3">MP3</option>
                <option value="wav">WAV</option>
                <option value="opus">OPUS</option>
                <option value="aac">AAC</option>
                <option value="flac">FLAC</option>
                <option value="pcm">PCM</option>
              </select>
              <input
                type="number"
                min={0.25}
                max={4}
                step={0.25}
                value={audioGenerationDefaults.speed ?? 1}
                onChange={(event) => patchAgentCard({
                  audioGeneration: {
                    ...audioGenerationDefaults,
                    speed: Math.max(0.25, Math.min(4, Number(event.target.value) || 1)),
                  },
                })}
                className="col-span-2 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs focus:outline-none focus:border-teal-500/50"
                placeholder="语速"
              />
            </div>
          )}

          {defaultTaskType === 'vision-understand' && (
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">视觉理解输出格式</label>
              <select
                value={visionUnderstandDefaults.outputFormat || 'json'}
                onChange={(event) => patchAgentCard({
                  visionUnderstand: {
                    ...visionUnderstandDefaults,
                    outputFormat: event.target.value,
                  },
                })}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30"
              >
                <option value="json">JSON（推荐）</option>
                <option value="markdown">Markdown</option>
                <option value="text">文本</option>
              </select>
              <div className="mt-1 text-[10px] text-slate-500">
                图片理解节点将通过对话接口携带附件执行，不会退化为纯文本识别。
              </div>
            </div>
          )}

          {defaultTaskType === 'data-analysis' && (
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">默认输出格式</label>
              <select
                value={dataAnalysisDefaults.outputFormat || 'markdown'}
                onChange={(event) => patchAgentCard({
                  dataAnalysis: {
                    ...dataAnalysisDefaults,
                    outputFormat: event.target.value,
                  },
                })}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30"
              >
                <option value="text">文本</option>
                <option value="json">JSON</option>
                <option value="markdown">Markdown</option>
              </select>
            </div>
          )}
        </div>
      </div>

      <div className="p-4 border-t border-slate-700">
        <button
          onClick={onSave}
          disabled={!canSave}
          className="w-full py-2.5 bg-teal-600 hover:bg-teal-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors"
        >
          {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          {saving ? '保存中...' : '保存'}
        </button>
      </div>
    </div>
  );
};
