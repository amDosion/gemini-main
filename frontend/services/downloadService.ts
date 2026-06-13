import { createManagedMediaObjectUrl, revokeManagedMediaObjectUrl } from './mediaCache';
import { isLocalBlobAttachmentUrl } from '../utils/attachmentUrl';

interface BrowserDownloadOptions {
  href: string;
  fileName?: string;
}

interface BlobBrowserDownloadOptions {
  blob: Blob;
  fileName: string;
  revokeDelayMs?: number;
}

interface SourceUrlDownloadOptions {
  sourceUrl: string;
  fileName: string;
  blobRevokeDelayMs?: number;
}

const DEFAULT_OBJECT_URL_REVOKE_DELAY_MS = 2000;
const FILE_NAME_SANITIZE_PATTERN = /[\\/:*?"<>|]/g;
const CONTROL_CHAR_PATTERN = /[\x00-\x1f\x7f]/g;
const CONTENT_DISPOSITION_FILENAME_STAR = /filename\*\s*=\s*([^;]+)/i;
const CONTENT_DISPOSITION_FILENAME = /filename\s*=\s*([^;]+)/i;

const getBrowserOrigin = (): string =>
  typeof window !== 'undefined' && window.location?.origin
    ? window.location.origin
    : 'http://localhost';

const normalizeDownloadHref = (href: string): string => {
  const normalized = String(href || '').trim();
  if (!normalized) {
    throw new Error('Unsupported download URL scheme');
  }

  const lowered = normalized.toLowerCase();
  if (lowered.startsWith('data:') || lowered.startsWith('blob:')) {
    return normalized;
  }

  try {
    const parsed = new URL(normalized, getBrowserOrigin());
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return normalized;
    }
  } catch {
    // fall through to the shared unsupported-scheme error
  }

  throw new Error('Unsupported download URL scheme');
};

const trimWrappedQuotes = (value: string): string => {
  const trimmed = value.trim();
  if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
};

const decodeMaybe = (value: string): string => {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

const sanitizeFileName = (fileName: string, fallbackFileName: string): string => {
  const normalized = fileName
    .replace(CONTROL_CHAR_PATTERN, '_')
    .replace(FILE_NAME_SANITIZE_PATTERN, '_')
    .trim();
  if (normalized.length > 0) {
    return normalized;
  }

  const normalizedFallback = fallbackFileName
    .replace(CONTROL_CHAR_PATTERN, '_')
    .replace(FILE_NAME_SANITIZE_PATTERN, '_')
    .trim();
  return normalizedFallback.length > 0 ? normalizedFallback : 'download';
};

export const inferFileNameFromContentDisposition = (
  contentDisposition: string | null | undefined,
  fallbackFileName: string
): string => {
  const header = String(contentDisposition || '').trim();
  if (!header) {
    return fallbackFileName;
  }

  const starMatch = CONTENT_DISPOSITION_FILENAME_STAR.exec(header);
  if (starMatch?.[1]) {
    const rawValue = trimWrappedQuotes(starMatch[1]);
    const encodedPart = rawValue.includes("''")
      ? rawValue.split("''").slice(1).join("''")
      : rawValue;
    const decodedName = decodeMaybe(encodedPart);
    return sanitizeFileName(decodedName, fallbackFileName);
  }

  const regularMatch = CONTENT_DISPOSITION_FILENAME.exec(header);
  if (regularMatch?.[1]) {
    const decodedName = decodeMaybe(trimWrappedQuotes(regularMatch[1]));
    return sanitizeFileName(decodedName, fallbackFileName);
  }

  return fallbackFileName;
};

export const triggerBrowserDownload = ({ href, fileName }: BrowserDownloadOptions): void => {
  const safeHref = normalizeDownloadHref(href);
  const anchor = document.createElement('a');
  anchor.href = safeHref;
  if (fileName) {
    anchor.download = sanitizeFileName(fileName, 'download');
  }
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
};

export const downloadBlobInBrowser = ({
  blob,
  fileName,
  revokeDelayMs = DEFAULT_OBJECT_URL_REVOKE_DELAY_MS,
}: BlobBrowserDownloadOptions): void => {
  const objectUrl = createManagedMediaObjectUrl(blob);
  if (!objectUrl) {
    throw new Error('Object URL API is not available for browser downloads');
  }
  triggerBrowserDownload({ href: objectUrl, fileName });
  window.setTimeout(
    () => {
      revokeManagedMediaObjectUrl(objectUrl);
    },
    Math.max(0, revokeDelayMs)
  );
};

const isBlobLikeSource = (sourceUrl: string): boolean =>
  sourceUrl.startsWith('data:') || sourceUrl.startsWith('blob:');

const isHttpSource = (sourceUrl: string): boolean =>
  sourceUrl.startsWith('http://') || sourceUrl.startsWith('https://');

const isRelativeApiSource = (sourceUrl: string): boolean => sourceUrl.startsWith('/api/');

const toStorageProxyUrl = (sourceUrl: string): string =>
  `/api/storage/download?url=${encodeURIComponent(sourceUrl)}`;

export const downloadSourceUrlInBrowser = async ({
  sourceUrl,
  fileName,
  // Revoking on the next tick can abort large downloads before the browser
  // dereferences the object URL; keep the module-wide safety delay by default.
  blobRevokeDelayMs = DEFAULT_OBJECT_URL_REVOKE_DELAY_MS,
}: SourceUrlDownloadOptions): Promise<void> => {
  const safeSourceUrl = String(sourceUrl || '').trim();

  if (isLocalBlobAttachmentUrl(safeSourceUrl)) {
    return;
  }

  if (isBlobLikeSource(safeSourceUrl)) {
    const response = await fetch(safeSourceUrl);
    const blob = await response.blob();
    downloadBlobInBrowser({
      blob,
      fileName,
      revokeDelayMs: blobRevokeDelayMs,
    });
    return;
  }

  if (isHttpSource(safeSourceUrl)) {
    triggerBrowserDownload({
      href: toStorageProxyUrl(safeSourceUrl),
      fileName,
    });
    return;
  }

  if (isRelativeApiSource(safeSourceUrl)) {
    triggerBrowserDownload({
      href: safeSourceUrl,
      fileName,
    });
    return;
  }

  throw new Error('Unsupported download URL scheme');
};
