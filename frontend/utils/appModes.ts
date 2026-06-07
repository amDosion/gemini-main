import { AppMode } from '../types/types';

/**
 * Studio (media-generation) app modes.
 *
 * 1:1 抽离自 `App.tsx`（< 800 行合规拆分）。所有 image/video/audio/pdf/try-on
 * 模式共享同一个 StudioView keep-alive 容器，因此用一个集合统一判定。
 */
export const STUDIO_APP_MODES = new Set<AppMode>([
  'image-gen',
  'image-chat-edit',
  'image-mask-edit',
  'image-inpainting',
  'image-background-edit',
  'image-recontext',
  'image-outpainting',
  'video-gen',
  'audio-gen',
  'pdf-extract',
  'virtual-try-on',
]);

export const isStudioAppMode = (mode: AppMode): boolean => STUDIO_APP_MODES.has(mode);
