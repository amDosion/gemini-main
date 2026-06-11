import { useCallback, useEffect, useMemo, useRef } from 'react';
import type { Attachment } from '../types/types';
import { getPreferredImageAttachmentUrl } from '../utils/attachmentUrl';
import { createManagedMediaObjectUrl, revokeManagedMediaObjectUrl } from '../services/mediaCache';

export type GetStableAttachmentImageUrl = (attachment: Attachment) => string | null;

interface UseStableAttachmentImageUrlOptions {
  retainedObjectUrl?: string | null;
  createFileObjectUrls?: boolean;
}

const EMPTY_ATTACHMENTS: Attachment[] = [];

// render 期解析的非 active 文件 URL 可能被消费方 useMemo 长期持有，无法精确判定何时失效；
// 用按最近使用排序的容量上限兜底，防止画布类视图切换图片时 blob 字节无限累积。
const MAX_RENDER_SCOPED_FILE_URLS = 8;

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

  const getStableAttachmentImageUrl = useCallback(
    (attachment: Attachment): string | null => {
      const preferredUrl = getPreferredImageAttachmentUrl(attachment);
      if (preferredUrl) return preferredUrl;

      if (attachment.file) {
        if (!createFileObjectUrls) return null;
        const file = attachment.file;
        const cachedUrl = objectUrlByFileRef.current.get(file);
        if (activeFilesRef.current.has(file)) {
          renderScopedFilesRef.current.delete(file);
        } else if (isRenderPhaseRef.current) {
          // delete 后再 add，让 Set 的插入序近似最近使用序，供容量回收按旧到新淘汰
          renderScopedFilesRef.current.delete(file);
          renderScopedFilesRef.current.add(file);
        }
        if (cachedUrl) return cachedUrl;

        const objectUrl = createManagedMediaObjectUrl(file);
        if (!objectUrl) return null;
        objectUrlByFileRef.current.set(file, objectUrl);
        return objectUrl;
      }

      return null;
    },
    [createFileObjectUrls]
  );

  useEffect(() => {
    isRenderPhaseRef.current = false;

    // 容量回收：render 期产生的非 active URL 超过上限时，从最旧的开始回收，
    // 跳过仍 active 或被 retainedObjectUrl 保护的条目
    const renderScopedFiles = renderScopedFilesRef.current;
    if (renderScopedFiles.size <= MAX_RENDER_SCOPED_FILE_URLS) return;
    const objectUrls = objectUrlByFileRef.current;
    for (const file of renderScopedFiles) {
      if (renderScopedFiles.size <= MAX_RENDER_SCOPED_FILE_URLS) break;
      if (activeFilesRef.current.has(file)) continue;
      const objectUrl = objectUrls.get(file);
      if (objectUrl === retainedObjectUrl) continue;
      renderScopedFiles.delete(file);
      if (objectUrl) {
        revokeManagedMediaObjectUrl(objectUrl);
        objectUrls.delete(file);
      }
    }
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
