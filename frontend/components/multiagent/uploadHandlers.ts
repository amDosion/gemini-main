/**
 * Multi-agent 节点 inline 文件上传辅助工具集。
 *
 * 1:1 抽离自 `PropertiesPanel.tsx` L89-108
 * （JIRA-frontend-view-decomposition.md P0 #1 Step 3）。
 *
 * 用途：节点属性面板内的 inline 上传（图片/音频/视频/文件 → base64 数据 URL）。
 * 超过 8MB 上限的文件应改用可访问 URL（OSS / GCS / S3 等），由调用方决定如何处理。
 */

import { fileToBase64 } from '../../hooks/handlers/attachmentUtils';

/** Inline 上传文件大小上限（字节）。超过应改用 URL 形式。 */
export const INLINE_UPLOAD_MAX_BYTES = 8 * 1024 * 1024;

/** 上限字节的人类可读 label（用于错误消息） */
export const INLINE_UPLOAD_MAX_BYTES_LABEL = '8MB';

/**
 * 弹窗报告 inline 上传错误。
 * 优先使用 Error.message，否则用 fallback 字符串。
 *
 * 注：1:1 沿用 `window.alert` UI；后续 ticket 可统一替换为 toast。
 */
export function reportInlineUploadError(fallbackMessage: string, error: unknown): void {
  const message = error instanceof Error && error.message ? error.message : fallbackMessage;
  if (typeof window !== 'undefined' && typeof window.alert === 'function') {
    window.alert(message);
  }
}

/**
 * 将一组 File 读取为 base64 data URLs。任一文件超过上限时抛出错误（含 label）。
 */
export async function readInlineFilesAsDataUrls(
  files: File[],
  uploadLabel: string
): Promise<string[]> {
  for (const file of files) {
    if (file.size > INLINE_UPLOAD_MAX_BYTES) {
      throw new Error(
        `${uploadLabel} 超过 ${INLINE_UPLOAD_MAX_BYTES_LABEL} 内联上传上限，请改用可访问的 URL。`
      );
    }
  }
  return Promise.all(files.map((file) => fileToBase64(file)));
}
