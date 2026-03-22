import { useState, useEffect } from 'react';
import { ModelConfig } from '../types/types';
import { llmService } from '../services/llmService';
import { getEnhancePromptModelCandidates } from '../utils/modelSuitability';

/**
 * 独立获取增强提示词模型候选列表
 * 
 * 不受当前模式或 hiddenModels 影响，从完整模型池中筛选
 * 支持多模态理解的模型（有 vision 能力的通用 Gemini 模型）
 */
export function useEnhancePromptModels(): ModelConfig[] {
  const [candidates, setCandidates] = useState<ModelConfig[]>([]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        // 获取完整模型列表（不受 mode/hidden 过滤）
        const payload = await llmService.getAvailableModelsPayload(true);
        if (cancelled) return;
        const all = Array.isArray(payload.models) ? payload.models as ModelConfig[] : [];
        setCandidates(getEnhancePromptModelCandidates(all));
      } catch {
        // 静默失败，使用空列表
      }
    };

    load();
    return () => { cancelled = true; };
  }, []);

  return candidates;
}
