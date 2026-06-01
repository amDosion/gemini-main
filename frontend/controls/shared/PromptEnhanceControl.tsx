import React, { useEffect, useId } from 'react';
import { Sparkles } from 'lucide-react';
import { ModelConfig } from '../../types/types';
import FeatureToggleControl from './FeatureToggleControl';
import type { ThinkingLevel } from '../types';

const THINKING_LEVEL_OPTIONS: Array<{ label: string; value: ThinkingLevel }> = [
  { label: '自动', value: 'auto' },
  { label: '极简', value: 'minimal' },
  { label: '低', value: 'low' },
  { label: '中', value: 'medium' },
  { label: '高', value: 'high' },
];

export interface PromptEnhanceControlProps {
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  modelId?: string;
  onModelIdChange?: (modelId: string) => void;
  modelOptions?: ModelConfig[];
  allowAutoModel?: boolean;
  autoSelectFirstModel?: boolean;
  disabled?: boolean;
  disabledHint?: string;
  thinkingLevel?: ThinkingLevel;
  onThinkingLevelChange?: (level: ThinkingLevel) => void;
}

export const PromptEnhanceControl: React.FC<PromptEnhanceControlProps> = ({
  enabled,
  onEnabledChange,
  modelId = '',
  onModelIdChange,
  modelOptions = [],
  allowAutoModel = true,
  autoSelectFirstModel = false,
  disabled = false,
  disabledHint,
  thinkingLevel = 'auto',
  onThinkingLevelChange,
}) => {
  const selectId = useId();
  const thinkingSelectId = useId();
  const showModelSelect = enabled && typeof onModelIdChange === 'function';
  const showThinkingLevel = enabled && typeof onThinkingLevelChange === 'function';

  useEffect(() => {
    if (!showModelSelect || !onModelIdChange) {
      return;
    }

    const selectedStillAvailable = modelOptions.some((model) => model.id === modelId);
    if (modelId && selectedStillAvailable) {
      return;
    }

    if (allowAutoModel) {
      if (modelId) {
        onModelIdChange('');
      }
      return;
    }

    if (autoSelectFirstModel && modelOptions.length > 0) {
      onModelIdChange(modelOptions[0].id);
    }
  }, [
    allowAutoModel,
    autoSelectFirstModel,
    modelId,
    modelOptions,
    onModelIdChange,
    showModelSelect,
  ]);

  return (
    <div className="space-y-2">
      <FeatureToggleControl
        enabled={enabled}
        onEnabledChange={onEnabledChange}
        icon={<Sparkles size={12} className="text-pink-400" />}
        label="AI 增强提示词"
        activeClass="bg-pink-600"
        disabled={disabled}
        disabledHint={disabledHint}
      />

      {showModelSelect ? (
        <div className="space-y-2">
          <label htmlFor={selectId} className="text-xs text-slate-300">
            增强提示词模型
          </label>
          <select
            id={selectId}
            aria-label="增强提示词模型"
            value={modelId}
            onChange={(event) => onModelIdChange?.(event.target.value)}
            disabled={!allowAutoModel && modelOptions.length === 0}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-pink-500/50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {allowAutoModel ? (
              <option value="">自动选择</option>
            ) : (
              <option value="" disabled>
                {modelOptions.length > 0 ? '请选择模型' : '未找到可用模型'}
              </option>
            )}
            {modelOptions.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name || model.id}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      {showThinkingLevel ? (
        <div className="space-y-2">
          <label htmlFor={thinkingSelectId} className="text-xs text-slate-300">
            思考等级
          </label>
          <select
            id={thinkingSelectId}
            aria-label="思考等级"
            value={thinkingLevel}
            onChange={(event) => onThinkingLevelChange?.(event.target.value as ThinkingLevel)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-pink-500/50"
          >
            {THINKING_LEVEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      ) : null}
    </div>
  );
};

export default PromptEnhanceControl;
