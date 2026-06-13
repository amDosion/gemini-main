import {
  isSafeInlineAudioDataUrl,
  isSafeInlineImageDataUrl,
  isSafeInlineVideoDataUrl,
} from '../utils/safeMediaDataUrl';

const normalizeString = (value: unknown): string =>
  typeof value === 'string' ? value.trim() : '';

export const isBrowserLocalBlobUrl = (value: unknown): boolean =>
  normalizeString(value).toLowerCase().startsWith('blob:');

export const normalizeWorkflowPreviewUrlField = (value: unknown): string => {
  const normalized = normalizeString(value);
  return isBrowserLocalBlobUrl(normalized) ? '' : normalized;
};

export const isSafeWorkflowPreviewImageUrl = (value: unknown): value is string => {
  const trimmed = normalizeString(value);
  if (!trimmed || isBrowserLocalBlobUrl(trimmed)) return false;
  const lowered = trimmed.toLowerCase();
  return (
    (lowered.startsWith('data:image/') && isSafeInlineImageDataUrl(trimmed)) ||
    lowered.startsWith('/api/') ||
    lowered.startsWith('https://') ||
    lowered.startsWith('http://')
  );
};

export const normalizeWorkflowPreviewImageUrls = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const urls: string[] = [];
  value.forEach((candidate) => {
    if (!isSafeWorkflowPreviewImageUrl(candidate)) return;
    const normalized = normalizeString(candidate);
    if (seen.has(normalized)) return;
    seen.add(normalized);
    urls.push(normalized);
  });
  return urls;
};

export const isSafeWorkflowPreviewMediaUrl = (value: unknown): value is string => {
  const trimmed = normalizeString(value);
  if (!trimmed || isBrowserLocalBlobUrl(trimmed)) return false;
  const lowered = trimmed.toLowerCase();
  if (lowered.startsWith('data:audio/')) return isSafeInlineAudioDataUrl(trimmed);
  if (lowered.startsWith('data:video/')) return isSafeInlineVideoDataUrl(trimmed);
  return (
    lowered.startsWith('/api/') ||
    lowered.startsWith('https://') ||
    lowered.startsWith('http://')
  );
};
