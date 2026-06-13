import { isSafeInlineAudioDataUrl } from './safeMediaDataUrl';

export interface SafeNewTabUrlOptions {
  allowBlob?: boolean;
  allowInlineAudioData?: boolean;
  allowRelative?: boolean;
}

export const getBrowserOrigin = (): string =>
  typeof window !== 'undefined' && window.location?.origin
    ? window.location.origin
    : 'http://localhost';

export const isSameOriginBlobUrl = (raw: string): boolean => {
  if (!raw.toLowerCase().startsWith('blob:')) {
    return false;
  }
  try {
    const innerUrl = new URL(raw.slice('blob:'.length));
    return innerUrl.origin === getBrowserOrigin();
  } catch {
    return false;
  }
};

export const toSafeNewTabUrl = (
  value: unknown,
  options: SafeNewTabUrlOptions = {}
): string | null => {
  const raw = typeof value === 'string' ? value.trim() : '';
  if (!raw) return null;

  const lowered = raw.toLowerCase();
  if (
    options.allowInlineAudioData &&
    lowered.startsWith('data:audio/') &&
    isSafeInlineAudioDataUrl(raw)
  ) {
    return raw;
  }
  if (options.allowBlob && isSameOriginBlobUrl(raw)) {
    return raw;
  }

  try {
    const parsed = options.allowRelative ? new URL(raw, getBrowserOrigin()) : new URL(raw);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
};

export const openSafeUrlInNewTab = (
  value: unknown,
  options: SafeNewTabUrlOptions = {}
): boolean => {
  const safeUrl = toSafeNewTabUrl(value, options);
  if (!safeUrl || typeof window === 'undefined' || typeof window.open !== 'function') {
    return false;
  }

  const openedWindow = window.open(safeUrl, '_blank', 'noopener,noreferrer');
  if (!openedWindow) {
    return false;
  }

  try {
    openedWindow.opener = null;
  } catch {
    // noopener should already sever opener; this is a defensive fallback.
  }

  return true;
};
