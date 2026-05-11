import { useState, useEffect } from 'react';
import { ModelConfig } from '../types/types';
import { llmService } from '../services/llmService';
import { getEnhancePromptModelCandidates } from '../utils/modelSuitability';

/**
 * 独立获取增强提示词模型候选列表
 *
 * 不受当前模式或 hiddenModels 影响，从完整模型池中筛选
 * 支持多模态理解的模型（有 vision 能力的通用 Gemini 模型）
 *
 * 模块级 cache + in-flight dedupe：3 controls 实例（ImageGenControls /
 * ImageEditControls / VideoGenControls）同 mount 时共享同一 Promise。
 */

let enhancePromptCandidatesCache: ModelConfig[] | null = null;
let inFlightEnhancePromptFetch: Promise<ModelConfig[]> | null = null;

export function useEnhancePromptModels(): ModelConfig[] {
  const [candidates, setCandidates] = useState<ModelConfig[]>(
    () => enhancePromptCandidatesCache ?? []
  );

  useEffect(() => {
    let cancelled = false;
    if (enhancePromptCandidatesCache) {
      setCandidates(enhancePromptCandidatesCache);
      return;
    }
    let fetchPromise = inFlightEnhancePromptFetch;
    if (!fetchPromise) {
      fetchPromise = llmService
        .getAvailableModelsPayload(true)
        .then((payload) => {
          const all = Array.isArray(payload.models) ? (payload.models as ModelConfig[]) : [];
          const filtered = getEnhancePromptModelCandidates(all);
          enhancePromptCandidatesCache = filtered;
          return filtered;
        })
        .finally(() => {
          inFlightEnhancePromptFetch = null;
        });
      inFlightEnhancePromptFetch = fetchPromise;
    }
    fetchPromise
      .then((list) => {
        if (cancelled) return;
        setCandidates(list);
      })
      .catch(() => {
        // 静默失败，使用空列表
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return candidates;
}

/** 测试-only：清模块 cache 让单测之间隔离 */
export const __resetEnhancePromptModelsCacheForTesting = (): void => {
  enhancePromptCandidatesCache = null;
  inFlightEnhancePromptFetch = null;
};
