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
const CONTENT_DISPOSITION_FILENAME_STAR = /filename\*\s*=\s*([^;]+)/i;
const CONTENT_DISPOSITION_FILENAME = /filename\s*=\s*([^;]+)/i;

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
  const normalized = fileName.replace(FILE_NAME_SANITIZE_PATTERN, '_').trim();
  return normalized.length > 0 ? normalized : fallbackFileName;
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
    const encodedPart = rawValue.includes("''") ? rawValue.split("''").slice(1).join("''") : rawValue;
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
  const anchor = document.createElement('a');
  anchor.href = href;
  if (fileName) {
    anchor.download = fileName;
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
  const objectUrl = URL.createObjectURL(blob);
  triggerBrowserDownload({ href: objectUrl, fileName });
  window.setTimeout(() => {
    URL.revokeObjectURL(objectUrl);
  }, Math.max(0, revokeDelayMs));
};

const isBlobLikeSource = (sourceUrl: string): boolean =>
  sourceUrl.startsWith('data:') || sourceUrl.startsWith('blob:');

const isHttpSource = (sourceUrl: string): boolean =>
  sourceUrl.startsWith('http://') || sourceUrl.startsWith('https://');

const toStorageProxyUrl = (sourceUrl: string): string =>
  `/api/storage/download?url=${encodeURIComponent(sourceUrl)}`;

export const downloadSourceUrlInBrowser = async ({
  sourceUrl,
  fileName,
  blobRevokeDelayMs = 0,
}: SourceUrlDownloadOptions): Promise<void> => {
  if (isBlobLikeSource(sourceUrl)) {
    const response = await fetch(sourceUrl);
    const blob = await response.blob();
    downloadBlobInBrowser({
      blob,
      fileName,
      revokeDelayMs: blobRevokeDelayMs,
    });
    return;
  }

  if (isHttpSource(sourceUrl)) {
    triggerBrowserDownload({
      href: toStorageProxyUrl(sourceUrl),
      fileName,
    });
    return;
  }

  triggerBrowserDownload({
    href: sourceUrl,
    fileName,
  });
};
