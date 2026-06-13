export const DEFAULT_SAFE_INLINE_IMAGE_MAX_BYTES = 8 * 1024 * 1024;
export const DEFAULT_SAFE_INLINE_MEDIA_DATA_URL_MAX_CHARS = 4096;

const SAFE_INLINE_IMAGE_MIME_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/webp',
  'image/gif',
  'image/bmp',
]);

const isValidBase64Payload = (payload: string): boolean =>
  Boolean(payload) && /^[A-Za-z0-9+/]+={0,2}$/.test(payload) && payload.length % 4 !== 1;

export const isSafeInlineImageDataUrl = (
  url: string,
  maxBytes = DEFAULT_SAFE_INLINE_IMAGE_MAX_BYTES
): boolean => {
  const match = /^data:([^;,]+);base64,([a-z0-9+/=\s]+)$/i.exec(url);
  if (!match?.[1] || !match[2]) return false;

  const mimeType = match[1].toLowerCase();
  if (!SAFE_INLINE_IMAGE_MIME_TYPES.has(mimeType)) return false;

  const payload = match[2].replace(/\s/g, '');
  if (!isValidBase64Payload(payload)) {
    return false;
  }

  const padding = payload.endsWith('==') ? 2 : payload.endsWith('=') ? 1 : 0;
  const estimatedBytes = Math.floor((payload.length * 3) / 4) - padding;
  if (estimatedBytes > maxBytes) return false;

  return true;
};

const isSafeInlineMediaDataUrl = (
  url: string,
  mediaFamily: 'audio' | 'video',
  maxChars = DEFAULT_SAFE_INLINE_MEDIA_DATA_URL_MAX_CHARS
): boolean => {
  const trimmed = String(url || '').trim();
  if (!trimmed || trimmed.length > maxChars) return false;

  const match = /^data:([^;,]+);base64,([a-z0-9+/=\s]+)$/i.exec(trimmed);
  if (!match?.[1] || !match[2]) return false;

  const mimeType = match[1].toLowerCase();
  if (!mimeType.startsWith(`${mediaFamily}/`)) return false;

  return isValidBase64Payload(match[2].replace(/\s/g, ''));
};

export const isSafeInlineAudioDataUrl = (
  url: string,
  maxChars = DEFAULT_SAFE_INLINE_MEDIA_DATA_URL_MAX_CHARS
): boolean => isSafeInlineMediaDataUrl(url, 'audio', maxChars);

export const isSafeInlineVideoDataUrl = (
  url: string,
  maxChars = DEFAULT_SAFE_INLINE_MEDIA_DATA_URL_MAX_CHARS
): boolean => isSafeInlineMediaDataUrl(url, 'video', maxChars);
