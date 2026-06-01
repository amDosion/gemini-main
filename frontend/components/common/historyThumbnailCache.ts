export const HISTORY_THUMBNAIL_RAW_FALLBACK_DELAY_MS = 300;

export const HISTORY_THUMBNAIL_CACHE_PROPS = {
  rawFallbackDelayMs: HISTORY_THUMBNAIL_RAW_FALLBACK_DELAY_MS,
  preferMemoryCache: true,
  replaceCachedObjectUrl: false,
} as const;
