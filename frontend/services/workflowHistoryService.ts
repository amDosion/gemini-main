import { requestJson } from './http';

const REQUEST_FAILED_STATUS_RE = /^Request failed:\s*(\d+)$/;
const PREVIEW_FETCH_FAILED_MESSAGE = '加载图片预览失败';
const MEDIA_PREVIEW_FETCH_FAILED_MESSAGE = '加载媒体预览失败';
const INLINE_MEDIA_DATA_URL_MAX_CHARS = 4096;

export type WorkflowHistoryMediaKind = 'audio' | 'video';

type WorkflowPreviewPayload = {
  images?: Array<{ dataUrl?: string }>;
  skippedCount?: unknown;
  count?: unknown;
};

type WorkflowMediaPreviewPayload = {
  mediaType?: unknown;
  items?: Array<{
    index?: unknown;
    sourceUrl?: unknown;
    resolvedUrl?: unknown;
    mimeType?: unknown;
    fileName?: unknown;
    previewUrl?: unknown;
  }>;
  skippedCount?: unknown;
  count?: unknown;
};

export interface WorkflowPreviewImagesMeta {
  imageUrls: string[];
  skippedCount: number;
  count: number;
}

export interface WorkflowHistoryMediaPreviewItem {
  index: number;
  sourceUrl: string;
  resolvedUrl: string;
  mimeType: string;
  fileName: string;
  previewUrl: string;
}

export interface WorkflowHistoryMediaPreviewMeta {
  mediaType: WorkflowHistoryMediaKind;
  items: WorkflowHistoryMediaPreviewItem[];
  skippedCount: number;
  count: number;
}

const remapRequestFailedError = (error: unknown, fallbackMessage: string): Error => {
  if (error instanceof Error) {
    const matched = REQUEST_FAILED_STATUS_RE.exec(String(error.message || '').trim());
    if (matched) {
      return new Error(`${fallbackMessage} (HTTP ${matched[1]})`);
    }
    return error;
  }
  return new Error(fallbackMessage);
};

const normalizePreviewLimit = (limit?: number): number | null => {
  if (limit == null) return null;
  if (!Number.isFinite(limit)) return null;
  const normalized = Math.floor(limit);
  if (normalized <= 0) return null;
  return normalized;
};

const toNonNegativeInteger = (value: unknown, fallback: number): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    const normalized = Math.floor(value);
    return normalized >= 0 ? normalized : fallback;
  }
  if (typeof value === 'string' && value.trim()) {
    const normalized = Number.parseInt(value.trim(), 10);
    if (Number.isFinite(normalized) && normalized >= 0) {
      return normalized;
    }
  }
  return fallback;
};

const extractPreviewImageUrls = (payload: WorkflowPreviewPayload | null | undefined): string[] => {
  const previewItems = Array.isArray(payload?.images) ? payload.images : [];
  return previewItems
    .map((item: { dataUrl?: string }) => item?.dataUrl)
    .filter((url: unknown): url is string => typeof url === 'string' && url.trim().length > 0);
};

const isSafeWorkflowMediaPreviewUrl = (value: unknown): value is string => {
  if (typeof value !== 'string') return false;
  const trimmed = value.trim();
  if (!trimmed) return false;
  const lowered = trimmed.toLowerCase();
  if (lowered.startsWith('data:audio/') || lowered.startsWith('data:video/')) {
    return trimmed.length <= INLINE_MEDIA_DATA_URL_MAX_CHARS;
  }
  return (
    lowered.startsWith('/api/') ||
    lowered.startsWith('https://') ||
    lowered.startsWith('http://')
  );
};

const normalizeWorkflowMediaKind = (value: unknown): WorkflowHistoryMediaKind | null => {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'audio' || normalized === 'video') {
    return normalized;
  }
  return null;
};

const extractPreviewMediaItems = (
  payload: WorkflowMediaPreviewPayload | null | undefined
): WorkflowHistoryMediaPreviewItem[] => {
  const previewItems = Array.isArray(payload?.items) ? payload.items : [];
  return previewItems
    .map((item, index) => {
      const previewUrl = isSafeWorkflowMediaPreviewUrl(item?.previewUrl) ? item.previewUrl.trim() : '';
      if (!previewUrl) {
        return null;
      }
      return {
        index: toNonNegativeInteger(item?.index, index + 1) || index + 1,
        sourceUrl: typeof item?.sourceUrl === 'string' ? item.sourceUrl.trim() : '',
        resolvedUrl: typeof item?.resolvedUrl === 'string' ? item.resolvedUrl.trim() : '',
        mimeType: typeof item?.mimeType === 'string' ? item.mimeType.trim() : '',
        fileName: typeof item?.fileName === 'string' ? item.fileName.trim() : '',
        previewUrl,
      } satisfies WorkflowHistoryMediaPreviewItem;
    })
    .filter((item): item is WorkflowHistoryMediaPreviewItem => Boolean(item));
};

export const fetchWorkflowPreviewImagesWithMeta = async (
  executionId: string,
  limit?: number,
  signal?: AbortSignal
): Promise<WorkflowPreviewImagesMeta> => {
  const safeExecutionId = String(executionId || '').trim();
  if (!safeExecutionId) {
    return {
      imageUrls: [],
      skippedCount: 0,
      count: 0,
    };
  }

  const safeLimit = normalizePreviewLimit(limit);
  const query = safeLimit ? `?limit=${safeLimit}` : '';
  let payload: WorkflowPreviewPayload;
  try {
    payload = await requestJson<WorkflowPreviewPayload>(
      `/api/workflows/history/${encodeURIComponent(safeExecutionId)}/images/preview${query}`,
      {
        credentials: 'include',
        signal,
        timeoutMs: 0,
        withAuth: true,
      }
    );
  } catch (error) {
    throw remapRequestFailedError(error, PREVIEW_FETCH_FAILED_MESSAGE);
  }
  const imageUrls = extractPreviewImageUrls(payload);
  return {
    imageUrls,
    skippedCount: toNonNegativeInteger(payload?.skippedCount, 0),
    count: toNonNegativeInteger(payload?.count, imageUrls.length),
  };
};

export const fetchWorkflowPreviewImages = async (
  executionId: string,
  limit?: number,
  signal?: AbortSignal
): Promise<string[]> => {
  const { imageUrls } = await fetchWorkflowPreviewImagesWithMeta(executionId, limit, signal);
  return imageUrls;
};

export const fetchWorkflowPreviewMediaWithMeta = async (
  executionId: string,
  mediaKind: WorkflowHistoryMediaKind,
  limit?: number,
  signal?: AbortSignal
): Promise<WorkflowHistoryMediaPreviewMeta> => {
  const safeExecutionId = String(executionId || '').trim();
  const safeMediaKind = normalizeWorkflowMediaKind(mediaKind);
  if (!safeExecutionId || !safeMediaKind) {
    return {
      mediaType: safeMediaKind || 'audio',
      items: [],
      skippedCount: 0,
      count: 0,
    };
  }

  const safeLimit = normalizePreviewLimit(limit);
  const query = safeLimit ? `?limit=${safeLimit}` : '';
  let payload: WorkflowMediaPreviewPayload;
  try {
    payload = await requestJson<WorkflowMediaPreviewPayload>(
      `/api/workflows/history/${encodeURIComponent(safeExecutionId)}/${safeMediaKind}/preview${query}`,
      {
        credentials: 'include',
        signal,
        timeoutMs: 0,
        withAuth: true,
      }
    );
  } catch (error) {
    throw remapRequestFailedError(error, MEDIA_PREVIEW_FETCH_FAILED_MESSAGE);
  }

  const items = extractPreviewMediaItems(payload);
  const payloadMediaKind = normalizeWorkflowMediaKind(payload?.mediaType) || safeMediaKind;
  return {
    mediaType: payloadMediaKind,
    items,
    skippedCount: toNonNegativeInteger(payload?.skippedCount, 0),
    count: toNonNegativeInteger(payload?.count, items.length),
  };
};
