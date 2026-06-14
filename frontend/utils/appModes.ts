import { AppMode } from '../types/types';

export const APP_MODES = [
  'chat',
  'image-gen',
  'image-chat-edit',
  'image-mask-edit',
  'image-inpainting',
  'image-background-edit',
  'image-recontext',
  'video-gen',
  'audio-gen',
  'image-outpainting',
  'pdf-extract',
  'virtual-try-on',
  'multi-agent',
  'image-upscale',
  'image-segmentation',
  'product-recontext',
] as const satisfies readonly AppMode[];

const APP_MODE_SET = new Set<AppMode>(APP_MODES);

export const isAppMode = (mode: unknown): mode is AppMode =>
  typeof mode === 'string' && APP_MODE_SET.has(mode as AppMode);

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
