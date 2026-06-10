import { useEffect, useMemo, useState } from 'react';
import { cacheManager, CACHE_DOMAINS } from '../services/CacheManager';
import { requestJson } from '../services/http';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
  registerPrivateCacheResetHandler,
} from '../services/privateCacheInvalidation';
import { getPrivateCacheUserScope, scopedPrivateCacheKey } from '../services/privateCacheScope';
import { usePrivateCacheLifecycleRevision } from './usePrivateCacheScopeRevision';

import { normalizeSchema, type ModeControlsSchema } from './useModeControlsSchema.normalize';

// Re-export the public schema types + pixel-resolution helper so existing import paths
// (`from '.../useModeControlsSchema'`) keep working after the normalization layer moved
// into ./useModeControlsSchema.normalize.
export { getPixelResolutionFromSchema } from './useModeControlsSchema.normalize';
export type {
  ModeControlsSchema,
  VideoContract,
  VideoContractAttachmentSlot,
  VideoContractEnhancePromptPolicy,
  VideoContractExtensionConstraints,
  VideoContractExtensionMatrixEntry,
  VideoContractExtensionOption,
  VideoContractFieldPolicies,
  VideoContractInputStrategy,
  VideoContractStoryboardPromptPolicy,
  VideoContractSubtitlePolicy,
  VideoContractTogglePolicy,
} from './useModeControlsSchema.normalize';

type ControlsApiResponse = {
  success: boolean;
  provider: string;
  mode: string;
  modelId?: string;
  schema?: Record<string, unknown>;
};

const MODE_CONTROLS_SCHEMA_CACHE_TTL_MS = 30 * 60 * 1000;
cacheManager.setTTL(CACHE_DOMAINS.MODE_CONTROLS_SCHEMA, MODE_CONTROLS_SCHEMA_CACHE_TTL_MS);

// In-flight 请求去重：多个组件同 mount 时共享同一 Promise，避免并发重复 fetch
// （修复用户反馈：image-gen/controls 同 model_id 重复 2 次）
const inFlightSchemaRequests = new Map<string, Promise<ModeControlsSchema>>();
let schemaCacheGeneration = 0;

/**
 * 清空 user-scope schema cache + in-flight Map。
 * 应在 logout / 切换用户 profile 后调用，避免跨用户 cache 污染。
 */
export const clearSchemaCacheForLogout = (): void => {
  schemaCacheGeneration += 1;
  cacheManager.clearDomain(CACHE_DOMAINS.MODE_CONTROLS_SCHEMA);
  inFlightSchemaRequests.clear();
};

registerPrivateCacheResetHandler(clearSchemaCacheForLogout);

const ABORT_MESSAGE = 'Request cancelled by user';

const isAbortRequestError = (error: unknown): boolean => {
  if (!(error instanceof Error)) return false;
  return error.name === 'AbortError' || error.message === ABORT_MESSAGE;
};

function buildCacheKey(
  providerId: string,
  mode: string,
  modelId?: string,
  userScope?: string
): string {
  return scopedPrivateCacheKey(
    CACHE_DOMAINS.MODE_CONTROLS_SCHEMA,
    `${providerId}::${mode}::${modelId || ''}`,
    userScope
  );
}

export interface UseModeControlsSchemaOptions {
  /**
   * 是否启用 fetch。默认 true。调用方可传 `enabled: !!activeModelConfig` 让 mount 初期
   * modelId 还未就绪时跳过 fetch，避免"先 fetch 不带 model_id → 然后 model 就绪再 fetch
   * 带 model_id"的双请求（用户反馈：video-gen/controls 一次不带 model_id 一次带）。
   */
  enabled?: boolean;
}

export function useModeControlsSchema(
  providerId: string | undefined,
  mode: string,
  modelId?: string,
  options?: UseModeControlsSchemaOptions
) {
  const enabled = options?.enabled ?? true;
  const privateCacheUserScope = getPrivateCacheUserScope();
  const cacheKey = useMemo(
    () => buildCacheKey(providerId || '', mode, modelId, privateCacheUserScope),
    [providerId, mode, modelId, privateCacheUserScope]
  );

  const [schema, setSchema] = useState<ModeControlsSchema | null>(
    providerId ? cacheManager.get<ModeControlsSchema>(cacheKey) || null : null
  );
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  usePrivateCacheLifecycleRevision(
    () => {
      setSchema(null);
      setLoading(false);
      setError(null);
    },
    { includeCacheReset: true }
  );

  useEffect(() => {
    if (!providerId || !enabled) {
      // 未配置 provider 或 调用方明确禁用 → 跳过 fetch。无论哪种情况都不再 loading,
      // 否则 enabled 在 in-flight 期间翻转为 false 会让 loading 永久卡在 true。
      // 仅在 !providerId 时清空 schema;!enabled 保留已 cache 的 schema 不变。
      setLoading(false);
      if (!providerId) {
        setSchema(null);
        setError(null);
      }
      return;
    }

    const cached = cacheManager.get<ModeControlsSchema>(cacheKey);
    if (cached) {
      setSchema(cached);
      setLoading(false);
      setError(null);
      return;
    }

    let active = true;
    const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
    setLoading(true);

    // In-flight 去重：若同 cacheKey 已有 Promise，复用而不再 fetch
    // 注意：不能用 AbortController 取消共享 Promise（其他 consumer 会受影响）
    // 改为本地 `active` flag 控制 setState（保留原 cleanup 语义）
    let fetchPromise = inFlightSchemaRequests.get(cacheKey);
    if (!fetchPromise) {
      const generationAtStart = schemaCacheGeneration;
      const params = new URLSearchParams();
      if (modelId) {
        params.set('model_id', modelId);
      }
      const query = params.toString();
      const requestUrl = `/api/modes/${providerId}/${mode}/controls${query ? `?${query}` : ''}`;

      fetchPromise = requestJson<ControlsApiResponse>(requestUrl, {
        method: 'GET',
        withAuth: true,
        timeoutMs: 0,
        errorMessage: 'Failed to fetch controls schema',
      })
        .then((data) => {
          const normalized = normalizeSchema(data.schema);
          if (!normalized) {
            throw new Error('Invalid controls schema payload');
          }
          if (
            generationAtStart === schemaCacheGeneration &&
            isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)
          ) {
            cacheManager.set(cacheKey, normalized);
          }
          return normalized;
        })
        .finally(() => {
          // 完成后从 in-flight 移除；下一次未命中 cache 才会重新发起
          if (inFlightSchemaRequests.get(cacheKey) === fetchPromise) {
            inFlightSchemaRequests.delete(cacheKey);
          }
        });
      inFlightSchemaRequests.set(cacheKey, fetchPromise);
    }

    fetchPromise
      .then((normalized) => {
        if (!active || !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)) return;
        setSchema(normalized);
        setError(null);
      })
      .catch((err: unknown) => {
        if (
          !active ||
          !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot) ||
          isAbortRequestError(err)
        ) {
          return;
        }
        const message = err instanceof Error ? err.message : 'Failed to fetch controls schema';
        setError(message || 'Failed to fetch controls schema');
        setSchema(null);
      })
      .finally(() => {
        if (!active || !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)) return;
        setLoading(false);
      });

    return () => {
      active = false;
      // 不 abort 共享 Promise（其他 consumer 还在等）；仅本地停止 setState
    };
  }, [providerId, mode, modelId, cacheKey, enabled]);

  return { schema, loading, error };
}
