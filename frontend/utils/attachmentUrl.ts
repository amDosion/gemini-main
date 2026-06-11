import type { Attachment } from '../types/types';
import { revokeManagedMediaObjectUrl } from '../services/mediaCache';

export type AttachmentUrlSource = Pick<Attachment, 'cloudUrl' | 'url' | 'tempUrl' | 'fileUri'> & {
  cloud_url?: string | null;
  temp_url?: string | null;
  file_uri?: string | null;
  file?: Blob | File | null;
};

const normalizeAttachmentUrl = (url: string | null | undefined): string | null => {
  const normalized = (url || '').trim();
  return normalized.length > 0 ? normalized : null;
};

export const isTemporaryAttachmentUrl = (url: string | null | undefined): boolean => {
  const normalized = normalizeAttachmentUrl(url)?.toLowerCase() || '';
  return (
    normalized.startsWith('blob:') ||
    normalized.startsWith('data:') ||
    normalized.startsWith('local-blob:')
  );
};

export const isBlobAttachmentUrl = (url: string | null | undefined): boolean => {
  const normalized = normalizeAttachmentUrl(url)?.toLowerCase() || '';
  return normalized.startsWith('blob:');
};

export const isDataAttachmentUrl = (url: string | null | undefined): boolean => {
  const normalized = normalizeAttachmentUrl(url)?.toLowerCase() || '';
  return normalized.startsWith('data:');
};

export const isLocalBlobAttachmentUrl = (url: string | null | undefined): boolean => {
  const normalized = normalizeAttachmentUrl(url)?.toLowerCase() || '';
  return normalized.startsWith('local-blob:');
};

export const getLocalBlobAttachmentId = (url: string | null | undefined): string | null => {
  const normalized = normalizeAttachmentUrl(url);
  if (!normalized || !isLocalBlobAttachmentUrl(normalized)) return null;
  const attachmentId = normalized.slice('local-blob:'.length).trim();
  return attachmentId || null;
};

export const isHttpAttachmentUrl = (url: string | null | undefined): boolean => {
  const normalized = normalizeAttachmentUrl(url)?.toLowerCase() || '';
  return normalized.startsWith('http://') || normalized.startsWith('https://');
};

const isLocalStorageAttachmentUrl = (url: string | null | undefined): boolean => {
  const normalized = normalizeAttachmentUrl(url)?.toLowerCase() || '';
  return (
    normalized.startsWith('/api/storage/') || /^https?:\/\/[^/]+\/api\/storage\//.test(normalized)
  );
};

export const getPreferredAttachmentUrl = (
  attachment: AttachmentUrlSource | null | undefined
): string | null => {
  if (!attachment) return null;
  const cloudUrl = normalizeAttachmentUrl(attachment.cloudUrl ?? attachment.cloud_url);
  const url = normalizeAttachmentUrl(attachment.url);
  const tempUrl = normalizeAttachmentUrl(attachment.tempUrl ?? attachment.temp_url);
  const fileUri = normalizeAttachmentUrl(attachment.fileUri ?? attachment.file_uri);
  const storageCandidates = [cloudUrl, url, fileUri, tempUrl].filter(
    (candidate): candidate is string => Boolean(candidate)
  );
  const displayCandidates = [cloudUrl, url, tempUrl, fileUri].filter(
    (candidate): candidate is string => Boolean(candidate)
  );

  return (
    storageCandidates.find(isLocalStorageAttachmentUrl) ||
    displayCandidates.find((candidate) => !isTemporaryAttachmentUrl(candidate)) ||
    displayCandidates[0] ||
    null
  );
};

export const getPreferredImageAttachmentUrl = getPreferredAttachmentUrl;

export const getRenderableAttachmentUrl = (
  attachment: AttachmentUrlSource | null | undefined
): string | null => {
  const preferredUrl = getPreferredAttachmentUrl(attachment);
  if (!preferredUrl) return null;
  if (isBlobAttachmentUrl(preferredUrl) && !attachment?.file) return null;
  return preferredUrl;
};

export const revokeAttachmentObjectUrls = (
  attachment: AttachmentUrlSource | null | undefined
): number => {
  if (!attachment) {
    return 0;
  }

  const objectUrls = new Set(
    [
      normalizeAttachmentUrl(attachment.url),
      normalizeAttachmentUrl(attachment.tempUrl ?? attachment.temp_url),
      normalizeAttachmentUrl(attachment.cloudUrl ?? attachment.cloud_url),
      normalizeAttachmentUrl(attachment.fileUri ?? attachment.file_uri),
    ].filter((url): url is string => Boolean(url && isBlobAttachmentUrl(url)))
  );

  objectUrls.forEach((objectUrl) => revokeManagedMediaObjectUrl(objectUrl));
  return objectUrls.size;
};
