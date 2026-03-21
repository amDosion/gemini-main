export interface StoragePreviewSource {
  url?: string | null;
  previewUrl?: string | null;
}

const STORAGE_PREVIEW_PROXY_PATH = '/api/storage/preview';

export const isSafeStoragePreviewCandidateUrl = (value: string): boolean => {
  const normalizedValue = String(value || '').trim();
  if (!normalizedValue) return false;
  const lowered = normalizedValue.toLowerCase();
  const isPathRelative = normalizedValue.startsWith('/') && !normalizedValue.startsWith('//');
  return (
    isPathRelative ||
    lowered.startsWith('https://') ||
    lowered.startsWith('http://')
  );
};

export const isStoragePreviewProxyUrl = (url: string): boolean => {
  const value = String(url || '').trim();
  if (!value) return false;
  return value.startsWith(STORAGE_PREVIEW_PROXY_PATH) || value.includes(STORAGE_PREVIEW_PROXY_PATH);
};

export const injectStoragePreviewRevision = (
  url: string,
  storageRevision?: number | null
): string => {
  const rawUrl = String(url || '').trim();
  if (!rawUrl) return rawUrl;
  if (!isStoragePreviewProxyUrl(rawUrl)) return rawUrl;
  if (storageRevision === null || storageRevision === undefined) return rawUrl;

  const [base, query = ''] = rawUrl.split('?');
  const params = new URLSearchParams(query);
  params.set('rev', String(storageRevision));
  const nextQuery = params.toString();
  return nextQuery ? `${base}?${nextQuery}` : base;
};

export const buildStoragePreviewCandidates = (
  item: StoragePreviewSource,
  storageRevision?: number | null
): string[] => {
  const candidates: string[] = [];
  const directUrl = typeof item.url === 'string' ? item.url.trim() : '';
  const proxyUrlRaw = typeof item.previewUrl === 'string' ? item.previewUrl.trim() : '';
  const proxyUrl = proxyUrlRaw ? injectStoragePreviewRevision(proxyUrlRaw, storageRevision) : '';

  if (proxyUrl && isSafeStoragePreviewCandidateUrl(proxyUrl)) {
    candidates.push(proxyUrl);
  }
  if (directUrl && directUrl !== proxyUrl && isSafeStoragePreviewCandidateUrl(directUrl)) {
    candidates.push(directUrl);
  }
  return candidates;
};

const findNextAvailablePreviewIndex = (
  candidates: string[],
  failedPreviewUrls: Set<string>,
  currentIndex: number
): number => {
  for (let idx = currentIndex + 1; idx < candidates.length; idx += 1) {
    const candidate = candidates[idx];
    if (!failedPreviewUrls.has(candidate)) {
      return idx;
    }
  }
  return -1;
};

export const getInitialStoragePreviewIndex = (
  candidates: string[],
  failedPreviewUrls: Set<string>
): { index: number; exhausted: boolean } => {
  const nextIndex = findNextAvailablePreviewIndex(candidates, failedPreviewUrls, -1);
  if (nextIndex >= 0) {
    return { index: nextIndex, exhausted: false };
  }
  return { index: 0, exhausted: true };
};

export const getNextStoragePreviewIndex = (
  candidates: string[],
  currentIndex: number,
  failedPreviewUrls: Set<string>
): { index: number; exhausted: boolean } => {
  const nextIndex = findNextAvailablePreviewIndex(candidates, failedPreviewUrls, currentIndex);
  if (nextIndex >= 0) {
    return { index: nextIndex, exhausted: false };
  }
  return { index: 0, exhausted: true };
};
