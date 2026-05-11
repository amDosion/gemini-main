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

/**
 * 清空 enhance prompt 模块级 cache。
 * 应在 logout / 切换用户 profile 后调用，避免跨用户 cache 污染（用户 B 看到 A 的模型列表）。
 */
export const clearEnhancePromptCacheForLogout = (): void => {
  enhancePromptCandidatesCache = null;
  inFlightEnhancePromptFetch = null;
};

/** 测试-only alias：等价 clearEnhancePromptCacheForLogout，命名标识 test-only 用途 */
export const __resetEnhancePromptModelsCacheForTesting = clearEnhancePromptCacheForLogout;
