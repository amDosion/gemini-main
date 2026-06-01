import { useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import type React from 'react';
import type { AppMode, Attachment } from '../types/types';
import { createManagedMediaObjectUrl } from '../services/mediaCache';
import { getAcceptedTypes, validateFiles } from '../utils/fileValidation';

const MIME_EXTENSION: Record<string, string> = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/jpg': 'jpg',
  'image/webp': 'webp',
  'image/gif': 'gif',
  'video/mp4': 'mp4',
  'video/webm': 'webm',
  'audio/mpeg': 'mp3',
  'audio/mp3': 'mp3',
  'audio/wav': 'wav',
  'application/pdf': 'pdf',
  'text/plain': 'txt',
  'text/csv': 'csv',
  'application/json': 'json',
};

interface UseClipboardAttachmentsOptions {
  mode: AppMode;
  attachments: Attachment[];
  onAttachmentsChange: (attachments: Attachment[]) => void;
  maxAttachments?: number;
  acceptedTypes?: string[] | string;
  disabled?: boolean;
  replaceExisting?: boolean;
  createObjectUrl?: boolean;
  onError?: (message: string) => void;
  idFactory?: (file: File, index: number) => string;
}

interface AppendFilesOptions {
  preventDuplicate?: boolean;
}

export interface UseClipboardAttachmentsResult {
  handlePaste: (event: React.ClipboardEvent<HTMLElement>) => void;
  appendFiles: (files: File[] | FileList, options?: AppendFilesOptions) => boolean;
}

function getPasteFilePrefix(mimeType: string): string {
  if (mimeType.startsWith('image/')) return 'pasted-image';
  if (mimeType.startsWith('video/')) return 'pasted-video';
  if (mimeType.startsWith('audio/')) return 'pasted-audio';
  if (mimeType === 'application/pdf') return 'pasted-document';
  return 'pasted-file';
}

function getPasteFileExtension(mimeType: string): string {
  return MIME_EXTENSION[mimeType] || 'bin';
}

function normalizePastedFileName(file: File, index: number): File {
  if (file.name.trim()) {
    return file;
  }

  const mimeType = file.type || 'application/octet-stream';
  const timestamp = Date.now();
  const filename = `${getPasteFilePrefix(mimeType)}-${timestamp}-${index + 1}.${getPasteFileExtension(mimeType)}`;

  return new File([file], filename, {
    type: mimeType,
    lastModified: file.lastModified || timestamp,
  });
}

function getFileKey(file: File): string {
  return `${file.name}|${file.type}|${file.size}|${file.lastModified}`;
}

function normalizeAcceptedTypes(acceptedTypes?: string[] | string): string[] {
  if (Array.isArray(acceptedTypes)) {
    return acceptedTypes.map((type) => type.trim()).filter(Boolean);
  }
  if (typeof acceptedTypes === 'string') {
    return acceptedTypes
      .split(',')
      .map((type) => type.trim())
      .filter(Boolean);
  }
  return [];
}

export function extractFilesFromClipboardData(clipboardData: DataTransfer | null): File[] {
  if (!clipboardData) {
    return [];
  }

  const files: File[] = [];

  if (clipboardData.items && clipboardData.items.length > 0) {
    Array.from(clipboardData.items).forEach((item) => {
      if (item.kind !== 'file') return;
      const file = item.getAsFile();
      if (file) files.push(file);
    });
  }

  if (files.length === 0 && clipboardData.files && clipboardData.files.length > 0) {
    files.push(...Array.from(clipboardData.files));
  }

  const seen = new Set<string>();
  return files.filter((file) => {
    const key = getFileKey(file);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function createAttachmentFromFile(
  file: File,
  index: number,
  options: {
    createObjectUrl?: boolean;
    idFactory?: (file: File, index: number) => string;
  } = {},
): Attachment {
  const createObjectUrl = options.createObjectUrl ?? false;
  const url = createObjectUrl ? createManagedMediaObjectUrl(file) || undefined : undefined;

  return {
    id: options.idFactory?.(file, index) || uuidv4(),
    name: file.name,
    mimeType: file.type || 'application/octet-stream',
    file,
    ...(url ? { url, tempUrl: url } : {}),
    uploadStatus: 'pending',
  };
}

export function useClipboardAttachments({
  mode,
  attachments,
  onAttachmentsChange,
  maxAttachments,
  acceptedTypes,
  disabled = false,
  replaceExisting = false,
  createObjectUrl = false,
  onError,
  idFactory,
}: UseClipboardAttachmentsOptions): UseClipboardAttachmentsResult {
  const appendFiles = useCallback(
    (incomingFiles: File[] | FileList, options: AppendFilesOptions = {}) => {
      if (disabled) {
        return false;
      }

      const files = Array.from(incomingFiles).map(normalizePastedFileName);
      if (files.length === 0) {
        return false;
      }

      const effectiveAcceptedTypes = normalizeAcceptedTypes(acceptedTypes);
      const modeAcceptedTypes =
        effectiveAcceptedTypes.length > 0 ? effectiveAcceptedTypes : getAcceptedTypes(mode);

      if (modeAcceptedTypes.length === 0) {
        onError?.('当前模式不支持上传附件');
        return false;
      }

      const validation = validateFiles(files, modeAcceptedTypes);
      if (validation.errors.length > 0) {
        onError?.(validation.errors[0]);
      }

      let validFiles = validation.valid;
      if (options.preventDuplicate) {
        const existingKeys = new Set(
          attachments
            .map((attachment) => attachment.file)
            .filter((file): file is File => Boolean(file))
            .map(getFileKey),
        );
        validFiles = validFiles.filter((file) => !existingKeys.has(getFileKey(file)));
      }

      const normalizedMax = Number.isFinite(maxAttachments) ? Math.max(0, maxAttachments || 0) : Infinity;
      const availableSlots = replaceExisting
        ? normalizedMax
        : normalizedMax - attachments.length;

      if (availableSlots <= 0) {
        if (Number.isFinite(normalizedMax)) {
          onError?.(`最多只能上传 ${normalizedMax} 个附件`);
        }
        return false;
      }

      const filesToAdd = validFiles.slice(0, availableSlots);
      if (filesToAdd.length === 0) {
        return false;
      }

      if (validFiles.length > filesToAdd.length && Number.isFinite(normalizedMax)) {
        onError?.(`已添加 ${filesToAdd.length} 个附件，超出部分已忽略（最多 ${normalizedMax} 个）`);
      }

      const nextAttachments = filesToAdd.map((file, index) =>
        createAttachmentFromFile(file, index, { createObjectUrl, idFactory }),
      );

      onAttachmentsChange(replaceExisting ? nextAttachments : [...attachments, ...nextAttachments]);
      return true;
    },
    [
      acceptedTypes,
      attachments,
      createObjectUrl,
      disabled,
      idFactory,
      maxAttachments,
      mode,
      onAttachmentsChange,
      onError,
      replaceExisting,
    ],
  );

  const handlePaste = useCallback(
    (event: React.ClipboardEvent<HTMLElement>) => {
      const files = extractFilesFromClipboardData(event.clipboardData);
      if (files.length === 0) {
        return;
      }

      const added = appendFiles(files, { preventDuplicate: true });
      if (added) {
        event.preventDefault();
      }
    },
    [appendFiles],
  );

  return { handlePaste, appendFiles };
}
