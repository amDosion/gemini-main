import { useState, useEffect, useMemo } from 'react';
import { ModelConfig } from '../types/types';
import { cacheManager, CACHE_DOMAINS } from '../services/CacheManager';
import { llmService } from '../services/llmService';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
  registerPrivateCacheResetHandler,
} from '../services/privateCacheInvalidation';
import {
  scopedPrivateCacheKey,
} from '../services/privateCacheScope';
import type { EnhancePromptModelCandidateOptions } from '../utils/modelSuitability';
import { getEnhancePromptModelCandidates } from '../utils/modelSuitability';
import { usePrivateCacheLifecycleRevision } from './usePrivateCacheScopeRevision';

interface UseEnhancePromptModelsOptions extends EnhancePromptModelCandidateOptions {
  includeHidden?: boolean;
}

/**
 * 独立获取增强提示词模型候选列表
 *
 * 从调用方传入的当前 profile 模型池中筛选；未传入模型池时再从 provider
 * 模型接口拉取并缓存。调用方一旦传入模型池，Hook 不再二次兜底，
 * 避免掩盖上游把模式模型列表误传成 provider 全量模型列表的问题。
 * Tongyi 这类 provider 可以显式 includeHidden 读取工具模型池，避免主模型
 * 下拉隐藏的 Qwen-VL 模型导致增强提示词无候选项。
 * 支持多模态理解的模型（有 vision 能力的通用 Gemini 模型）
 *
 * 数据缓存统一走 CacheManager + private user scope；同 key 并发请求用模块级
 * in-flight Map 去重。
 */

const ENHANCE_PROMPT_MODELS_CACHE_TTL_MS = 30 * 60 * 1000;
cacheManager.setTTL(CACHE_DOMAINS.ENHANCE_PROMPT_MODELS, ENHANCE_PROMPT_MODELS_CACHE_TTL_MS);

const inFlightEnhancePromptFetch = new Map<string, Promise<ModelConfig[]>>();
let enhancePromptCacheGeneration = 0;

const buildModelsFingerprint = (models?: ModelConfig[]): string => {
  if (!models?.length) {
    return '';
  }
  return models
    .map((model) => [
      model.id,
      model.name,
      model.capabilities?.vision ? 'v1' : 'v0',
      model.capabilities?.reasoning ? 'r1' : 'r0',
      model.traits?.multimodalUnderstanding ? 'm1' : 'm0',
      model.traits?.thinking ? 't1' : 't0',
    ].join(':'))
    .join('|');
};

const buildCacheKey = (
  providerId: string,
  requiresVision: boolean,
  includeHidden: boolean
): string =>
  scopedPrivateCacheKey(
    CACHE_DOMAINS.ENHANCE_PROMPT_MODELS,
    [
      providerId,
      requiresVision ? 'vision' : 'default',
      includeHidden ? 'include-hidden' : 'visible',
    ].join(':')
  );

export const clearEnhancePromptModelsCache = (): void => {
  enhancePromptCacheGeneration += 1;
  cacheManager.clearDomain(CACHE_DOMAINS.ENHANCE_PROMPT_MODELS);
  inFlightEnhancePromptFetch.clear();
};

registerPrivateCacheResetHandler(clearEnhancePromptModelsCache);

export function useEnhancePromptModels(
  providerId?: string,
  currentModels?: ModelConfig[],
  options: UseEnhancePromptModelsOptions = {}
): ModelConfig[] {
  const effectiveProviderId = (providerId || llmService.getProviderId() || 'default').toLowerCase();
  const requiresVision = Boolean(options.requiresVision);
  const includeHidden = Boolean(options.includeHidden);
  const currentModelsFingerprint = buildModelsFingerprint(currentModels);
  const currentModelCandidates = useMemo(() => {
    if (!currentModels) {
      return null;
    }
    return getEnhancePromptModelCandidates(
      currentModels,
      effectiveProviderId,
      { requiresVision }
    );
  }, [currentModels, currentModelsFingerprint, effectiveProviderId, requiresVision]);

  const cacheKey = buildCacheKey(effectiveProviderId, requiresVision, includeHidden);
  const [candidates, setCandidates] = useState<ModelConfig[]>(
    () => currentModelCandidates ?? cacheManager.get<ModelConfig[]>(cacheKey) ?? []
  );
  usePrivateCacheLifecycleRevision(() => {
    setCandidates([]);
  }, { includeCacheReset: true });

  useEffect(() => {
    let cancelled = false;
    const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();

    if (currentModelCandidates) {
      setCandidates(currentModelCandidates);
      return;
    }

    const cachedCandidates = cacheManager.get<ModelConfig[]>(cacheKey);
    if (cachedCandidates !== null) {
      setCandidates(cachedCandidates);
      return;
    }
    let fetchPromise = inFlightEnhancePromptFetch.get(cacheKey);
    if (!fetchPromise) {
      const generationAtStart = enhancePromptCacheGeneration;
      fetchPromise = llmService
        .getAvailableModelsPayload(
          true,
          undefined,
          includeHidden ? { includeHidden: true } : undefined
        )
        .then((payload) => {
          const all = Array.isArray(payload.models) ? (payload.models as ModelConfig[]) : [];
          const payloadProviderId = providerId || payload.provider || llmService.getProviderId();
          const filtered = getEnhancePromptModelCandidates(
            all,
            payloadProviderId,
            { requiresVision }
          );
          if (
            generationAtStart === enhancePromptCacheGeneration &&
            isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)
          ) {
            cacheManager.set(cacheKey, filtered);
          }
          return filtered;
        })
        .finally(() => {
          if (inFlightEnhancePromptFetch.get(cacheKey) === fetchPromise) {
            inFlightEnhancePromptFetch.delete(cacheKey);
          }
        });
      inFlightEnhancePromptFetch.set(cacheKey, fetchPromise);
    }
    fetchPromise
      .then((list) => {
        if (cancelled || !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)) return;
        setCandidates(list);
      })
      .catch(() => {
        // 静默失败，使用空列表
      });
    return () => {
      cancelled = true;
    };
  }, [cacheKey, providerId, currentModelCandidates, requiresVision, includeHidden]);

  return candidates;
}

/**
 * 清空 enhance prompt user-scope cache。
 * 应在 logout / 切换用户 profile 后调用，避免跨用户 cache 污染。
 */
export const clearEnhancePromptCacheForLogout = (): void => {
  clearEnhancePromptModelsCache();
};

/** 测试-only alias：等价 clearEnhancePromptCacheForLogout，命名标识 test-only 用途 */
export const __resetEnhancePromptModelsCacheForTesting = clearEnhancePromptCacheForLogout;
