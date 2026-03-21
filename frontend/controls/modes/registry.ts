/**
 * 模式控件注册表
 *
 * 设计目标：
 * - 通用实现只维护一份（当前为 google 目录）
 * - provider 只声明差异控件（override）
 * - 分发入口统一为 providerId + mode
 */
import React from 'react';
import { AppMode } from '../../types/types';
import * as CommonControls from './google';
import { ImageGenControls as OpenAIImageGenControls } from './openai/ImageGenControls';
import { VideoGenControls as OpenAIVideoGenControls } from './openai/VideoGenControls';
import { ImageEditControls as TongYiImageEditControls } from './tongyi/ImageEditControls';
import { ImageGenControls as TongYiImageGenControls } from './tongyi/ImageGenControls';

export type ProviderModeControls = {
  ChatControls: React.ComponentType<any>;
  ImageGenControls: React.ComponentType<any>;
  ImageEditControls: React.ComponentType<any>;
  ImageMaskEditControls: React.ComponentType<any>;
  ImageOutpaintControls: React.ComponentType<any>;
  VideoGenControls: React.ComponentType<any>;
  AudioGenControls: React.ComponentType<any>;
  VirtualTryOnControls: React.ComponentType<any>;
  PdfExtractControls: React.ComponentType<any>;
  MultiAgentControls: React.ComponentType<any>;
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
    VideoGenControls: OpenAIVideoGenControls,
  },
  tongyi: {
    ImageGenControls: TongYiImageGenControls,
    ImageEditControls: TongYiImageEditControls,
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

export function getProviderControlByMode(providerId: string | undefined, mode: AppMode): React.ComponentType<any> | null {
  const controlKey = modeToControlKey[mode];
  if (!controlKey) return null;
  return getProviderControls(providerId)[controlKey];
}
