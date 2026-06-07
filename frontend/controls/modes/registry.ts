/**
 * 模式控件注册表
 *
 * 设计目标：
 * - 通用实现只维护一份（当前为 google 目录）
 * - provider 只声明差异控件（override）
 * - 分发入口统一为 providerId + mode
 */
import React from 'react';
import { AppMode, ModelConfig } from '../../types/types';
import type {
  ChatControlsProps,
  ImageGenControlsProps,
  ImageEditControlsProps,
  ImageMaskEditControlsProps,
  ImageOutpaintControlsProps,
  VideoGenControlsProps,
  AudioGenControlsProps,
  VirtualTryOnControlsProps,
  PdfExtractControlsProps,
  MultiAgentControlsProps,
} from '../types';
import * as CommonControls from './google';
import { ImageEditControls as OpenAIImageEditControls } from './openai/ImageEditControls';
import { ImageGenControls as OpenAIImageGenControls } from './openai/ImageGenControls';
import { ImageMaskEditControls as OpenAIImageMaskEditControls } from './openai/ImageMaskEditControls';
import { ImageOutpaintControls as OpenAIImageOutpaintControls } from './openai/ImageOutpaintControls';
import { VirtualTryOnControls as OpenAIVirtualTryOnControls } from './openai/VirtualTryOnControls';
import { ImageEditControls as TongYiImageEditControls } from './tongyi/ImageEditControls';
import { ImageGenControls as TongYiImageGenControls } from './tongyi/ImageGenControls';
import { ImageGenControls as GrokImageGenControls } from './grok/ImageGenControls';
import { VideoGenControls as GrokVideoGenControls } from './grok/VideoGenControls';

// Extra props the ModeControlsCoordinator supplies uniformly to the image-edit /
// outpaint / virtual-try-on slots. The shared OpenAIImageControls-based override
// components require a `mode` prop and accept `currentModel` / `availableModels` /
// `maxImageCount`, while the base interfaces in `../types` omit some of these.
// Modelling them here (all optional except `mode`, which the coordinator always
// passes) keeps the slots precise enough to accept both the common google
// components and the provider override components without falling back to `any`.
type ImageEditSlotExtras = {
  mode: AppMode | 'image-edit';
  currentModel?: ModelConfig;
  availableModels?: ModelConfig[];
  maxImageCount?: number;
};

// Each slot is parameterized with its concrete prop interface from `../types`, so
// the registry is type-checked without `any`. Slots whose provider overrides take
// the shared image-control props intersect the base interface with the extras
// the coordinator passes.
export type ProviderModeControls = {
  ChatControls: React.ComponentType<ChatControlsProps>;
  ImageGenControls: React.ComponentType<ImageGenControlsProps>;
  ImageEditControls: React.ComponentType<ImageEditControlsProps>;
  ImageMaskEditControls: React.ComponentType<ImageMaskEditControlsProps & ImageEditSlotExtras>;
  ImageOutpaintControls: React.ComponentType<ImageOutpaintControlsProps & ImageEditSlotExtras>;
  VideoGenControls: React.ComponentType<VideoGenControlsProps>;
  AudioGenControls: React.ComponentType<AudioGenControlsProps>;
  VirtualTryOnControls: React.ComponentType<VirtualTryOnControlsProps & ImageEditSlotExtras>;
  PdfExtractControls: React.ComponentType<PdfExtractControlsProps>;
  MultiAgentControls: React.ComponentType<MultiAgentControlsProps>;
};

const commonControls: ProviderModeControls = {
  ChatControls: CommonControls.ChatControls,
  ImageGenControls: CommonControls.ImageGenControls,
  ImageEditControls: CommonControls.ImageEditControls,
  ImageMaskEditControls: CommonControls.ImageMaskEditControls,
  ImageOutpaintControls: CommonControls.ImageOutpaintControls,
  VideoGenControls: CommonControls.VideoGenControls,
  AudioGenControls: CommonControls.AudioGenControls,
  VirtualTryOnControls: CommonControls.VirtualTryOnControls,
  PdfExtractControls: CommonControls.PdfExtractControls,
  MultiAgentControls: CommonControls.MultiAgentControls,
};

const providerOverrides: Record<string, Partial<ProviderModeControls>> = {
  openai: {
    ImageGenControls: OpenAIImageGenControls,
    ImageEditControls: OpenAIImageEditControls,
    ImageMaskEditControls: OpenAIImageMaskEditControls,
    ImageOutpaintControls: OpenAIImageOutpaintControls,
    VirtualTryOnControls: OpenAIVirtualTryOnControls,
  },
  tongyi: {
    ImageGenControls: TongYiImageGenControls,
    ImageEditControls: TongYiImageEditControls,
  },
  grok: {
    ImageGenControls: GrokImageGenControls,
    VideoGenControls: GrokVideoGenControls,
  },
};

const providerAliases: Record<string, string> = {
  'google-custom': 'google',
};

const mergedCache = new Map<string, ProviderModeControls>();

export function normalizeProviderId(providerId?: string): string {
  const normalized = (providerId || '').trim();
  if (!normalized) return 'google';
  return providerAliases[normalized] || normalized;
}

export function getProviderControls(providerId?: string): ProviderModeControls {
  const normalized = normalizeProviderId(providerId);
  const cached = mergedCache.get(normalized);
  if (cached) return cached;

  const merged: ProviderModeControls = {
    ...commonControls,
    ...(providerOverrides[normalized] || {}),
  };
  mergedCache.set(normalized, merged);
  return merged;
}

// Maps each AppMode to the corresponding ProviderModeControls slot key.
// Modes absent from this map intentionally have no side-panel control component:
//   'image-upscale'      — no parameters to configure; backend uses defaults
//   'image-segmentation' — selection is handled inline in the canvas, not in the panel
//   'product-recontext'  — uses the shared image-edit flow without a dedicated panel
const modeToControlKey: Partial<Record<AppMode, keyof ProviderModeControls>> = {
  chat: 'ChatControls',
  'image-gen': 'ImageGenControls',
  'image-chat-edit': 'ImageEditControls',
  'image-inpainting': 'ImageEditControls',
  'image-background-edit': 'ImageEditControls',
  'image-recontext': 'ImageEditControls',
  'image-mask-edit': 'ImageMaskEditControls',
  'image-outpainting': 'ImageOutpaintControls',
  'video-gen': 'VideoGenControls',
  'audio-gen': 'AudioGenControls',
  'pdf-extract': 'PdfExtractControls',
  'virtual-try-on': 'VirtualTryOnControls',
  'multi-agent': 'MultiAgentControls',
};

// The returned component is one of the registry slots; the exact slot is only
// known at runtime, so the union of all slot component types is the most precise
// statically-knowable return type.
export type AnyProviderControl = ProviderModeControls[keyof ProviderModeControls];

export function getProviderControlByMode(
  providerId: string | undefined,
  mode: AppMode
): AnyProviderControl | null {
  const controlKey = modeToControlKey[mode];
  if (!controlKey) return null;
  return getProviderControls(providerId)[controlKey];
}
