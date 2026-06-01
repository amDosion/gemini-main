import { useCallback, useEffect, useMemo, useRef } from 'react';
import type { Attachment } from '../types/types';
import { getPreferredImageAttachmentUrl } from '../utils/attachmentUrl';
import {
  createManagedMediaObjectUrl,
  revokeManagedMediaObjectUrl,
} from '../services/mediaCache';

export type GetStableAttachmentImageUrl = (attachment: Attachment) => string | null;

interface UseStableAttachmentImageUrlOptions {
  retainedObjectUrl?: string | null;
  createFileObjectUrls?: boolean;
}

const EMPTY_ATTACHMENTS: Attachment[] = [];

export const useStableAttachmentImageUrl = (
  activeAttachments: Attachment[] = EMPTY_ATTACHMENTS,
  options: UseStableAttachmentImageUrlOptions = {}
): GetStableAttachmentImageUrl => {
  const objectUrlByFileRef = useRef<Map<File, string>>(new Map());
  const renderScopedFilesRef = useRef<Set<File>>(new Set());
  const activeFilesRef = useRef<Set<File>>(new Set());
  const isRenderPhaseRef = useRef(false);
  const retainedObjectUrl = options.retainedObjectUrl || null;
  const createFileObjectUrls = options.createFileObjectUrls ?? true;
  const activeFiles = useMemo(
    () =>
      new Set(
        activeAttachments
          .map((attachment) => attachment.file)
          .filter((file): file is File => Boolean(file))
      ),
    [activeAttachments]
  );
  activeFilesRef.current = activeFiles;
  isRenderPhaseRef.current = true;

  const getStableAttachmentImageUrl = useCallback((attachment: Attachment): string | null => {
    const preferredUrl = getPreferredImageAttachmentUrl(attachment);
    if (preferredUrl) return preferredUrl;

    if (attachment.file) {
      if (!createFileObjectUrls) return null;
      const file = attachment.file;
      const cachedUrl = objectUrlByFileRef.current.get(file);
      if (activeFilesRef.current.has(file)) {
        renderScopedFilesRef.current.delete(file);
      } else if (isRenderPhaseRef.current) {
        renderScopedFilesRef.current.add(file);
      }
      if (cachedUrl) return cachedUrl;

      const objectUrl = createManagedMediaObjectUrl(file);
      if (!objectUrl) return null;
      objectUrlByFileRef.current.set(file, objectUrl);
      return objectUrl;
    }

    return null;
  }, [createFileObjectUrls]);

  useEffect(() => {
    isRenderPhaseRef.current = false;
  });

  useEffect(() => {
    const objectUrls = objectUrlByFileRef.current;

    for (const [file, objectUrl] of objectUrls.entries()) {
      if (
        activeFiles.has(file) ||
        objectUrl === retainedObjectUrl ||
        renderScopedFilesRef.current.has(file)
      ) {
        continue;
      }
      revokeManagedMediaObjectUrl(objectUrl);
      objectUrls.delete(file);
      renderScopedFilesRef.current.delete(file);
    }
  }, [activeFiles, retainedObjectUrl]);

  useEffect(() => {
    return () => {
      for (const objectUrl of objectUrlByFileRef.current.values()) {
        revokeManagedMediaObjectUrl(objectUrl);
      }
      objectUrlByFileRef.current.clear();
      renderScopedFilesRef.current.clear();
    };
  }, []);

  return getStableAttachmentImageUrl;
};
