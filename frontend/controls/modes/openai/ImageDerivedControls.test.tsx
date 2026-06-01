// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

const gptImageEditSchema = vi.hoisted(() => ({
  defaults: {
    aspect_ratio: '1:1',
    resolution: 'auto',
    number_of_images: 1,
    quality: 'high',
    output_format: 'png',
    enhance_prompt: false,
  },
  constraints: {
    max_image_count: 10,
  },
  aspectRatios: [
    { label: '1:1 Square', value: '1:1' },
    { label: '4:3 Landscape', value: '4:3' },
    { label: '3:4 Portrait', value: '3:4' },
    { label: '16:9 Widescreen', value: '16:9' },
    { label: '9:16 Vertical', value: '9:16' },
  ],
  resolutionTiers: [
    { label: 'Auto', value: 'auto', baseResolution: 'Model-selected' },
    { label: '1K', value: '1K', baseResolution: '1024x1024' },
    { label: '2K', value: '2K', baseResolution: '2048x2048' },
    { label: 'Max', value: 'max', baseResolution: 'Ratio-dependent maximum' },
  ],
  resolutionMap: {
    auto: { '1:1': 'auto', '4:3': 'auto', '3:4': 'auto', '16:9': 'auto', '9:16': 'auto' },
    '1K': { '1:1': '1024x1024', '4:3': '1152x864', '3:4': '864x1152', '16:9': '1280x720', '9:16': '720x1280' },
    '2K': { '1:1': '2048x2048', '4:3': '2048x1536', '3:4': '1536x2048', '16:9': '2048x1152', '9:16': '1152x2048' },
    max: { '1:1': '2880x2880', '4:3': '2880x2160', '3:4': '2160x2880', '16:9': '3840x2160', '9:16': '2160x3840' },
  },
  paramOptions: {
    number_of_images: [
      { label: '1', value: 1 },
      { label: '2', value: 2 },
      { label: '3', value: 3 },
      { label: '4', value: 4 },
      { label: '5', value: 5 },
      { label: '6', value: 6 },
      { label: '7', value: 7 },
      { label: '8', value: 8 },
      { label: '9', value: 9 },
      { label: '10', value: 10 },
    ],
    quality: [],
    background: [],
    moderation: [],
    output_format: [],
  },
  numericRanges: {
    output_compression_quality: null,
  },
}));

vi.mock('../../../hooks/useModeControlsSchema', () => ({
  useModeControlsSchema: () => ({ schema: gptImageEditSchema, loading: false, error: null }),
  getPixelResolutionFromSchema: (schema: any, aspectRatio: string, resolution: string) =>
    schema?.resolutionMap?.[resolution]?.[aspectRatio] ?? null,
}));

vi.mock('../../../hooks/useEnhancePromptModels', () => ({
  useEnhancePromptModels: () => [
    {
      id: 'gpt-5.4-mini',
      name: 'GPT 5.4 Mini',
      description: '',
      capabilities: { vision: false, search: false, reasoning: false, coding: false },
    },
  ],
}));

import { ImageMaskEditControls } from './ImageMaskEditControls';
import { ImageOutpaintControls } from './ImageOutpaintControls';
import { VirtualTryOnControls } from './VirtualTryOnControls';

afterEach(() => {
  cleanup();
});

const model = {
  id: 'gpt-image-2',
  name: 'GPT Image 2',
  description: '',
  capabilities: { vision: true, search: false, reasoning: false, coding: false },
};

const controls = {
  aspectRatio: '1:1',
  setAspectRatio: vi.fn(),
  resolution: 'auto',
  setResolution: vi.fn(),
  numberOfImages: 2,
  setNumberOfImages: vi.fn(),
  quality: 'auto',
  setQuality: vi.fn(),
  background: 'auto',
  setBackground: vi.fn(),
  moderation: 'auto',
  setModeration: vi.fn(),
  outputFormat: 'png',
  setOutputFormat: vi.fn(),
  outputCompressionQuality: 100,
  setOutputCompressionQuality: vi.fn(),
  enhancePrompt: true,
  setEnhancePrompt: vi.fn(),
  enhancePromptModel: 'gpt-5.4-mini',
  setEnhancePromptModel: vi.fn(),
  enhancePromptThinkingLevel: 'medium',
  setEnhancePromptThinkingLevel: vi.fn(),
};

describe('OpenAI derived image mode controls', () => {
  it('uses the shared GPT Image edit controls for mask edit', () => {
    render(
      <ImageMaskEditControls
        providerId="openai"
        mode="image-mask-edit"
        currentModel={model as any}
        controls={controls as any}
      />
    );

    expect(screen.getByText('图片比例')).toBeInTheDocument();
    expect(screen.getByRole('slider', { name: '生成数量' })).toHaveAttribute('max', '10');
    expect(screen.getByText('AI 增强提示词')).toBeInTheDocument();
    expect(screen.queryByText('编辑模式')).not.toBeInTheDocument();
    expect(screen.queryByText('掩码膨胀系数')).not.toBeInTheDocument();
  });

  it('uses the shared GPT Image edit controls for outpainting', () => {
    render(
      <ImageOutpaintControls
        providerId="openai"
        mode="image-outpainting"
        currentModel={model as any}
        controls={controls as any}
      />
    );

    expect(screen.getByText('图片比例')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Max/ })).toBeInTheDocument();
    expect(screen.queryByText('扩图模式')).not.toBeInTheDocument();
    expect(screen.queryByText('图片放大')).not.toBeInTheDocument();
  });

  it('uses the shared GPT Image edit controls for virtual try-on', () => {
    render(
      <VirtualTryOnControls
        providerId="openai"
        mode="virtual-try-on"
        currentModel={model as any}
        controls={controls as any}
      />
    );

    expect(screen.getByText('图片比例')).toBeInTheDocument();
    expect(screen.getByLabelText('思考等级')).toHaveValue('medium');
    expect(screen.queryByText('质量步数')).not.toBeInTheDocument();
  });
});
