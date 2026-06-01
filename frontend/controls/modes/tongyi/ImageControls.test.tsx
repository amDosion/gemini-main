// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

const wan27Schemas = vi.hoisted(() => {
  const generation = {
    defaults: {
      aspect_ratio: '1:1',
      resolution: '2K',
      number_of_images: 1,
      thinking_mode: true,
      enable_sequential: false,
      prompt_extend: false,
      add_magic_suffix: false,
      negative_prompt: '',
    },
    constraints: {
      max_image_count: 12,
      unsupported_params: ['negative_prompt', 'prompt_extend', 'add_magic_suffix'],
    },
    aspectRatios: [
      { label: '1:1 Square', value: '1:1' },
      { label: '16:9 Landscape', value: '16:9' },
    ],
    resolutionTiers: [
      { label: '1K', value: '1K', baseResolution: '1024×1024' },
      { label: '2K', value: '2K', baseResolution: '2048×2048' },
    ],
    resolutionMap: {
      '1K': { '1:1': '1024*1024', '16:9': '1280*720' },
      '2K': { '1:1': '2048*2048', '16:9': '2730*1536' },
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
        { label: '11', value: 11 },
        { label: '12', value: 12 },
      ],
      thinking_mode: [
        { label: '开启', value: true },
        { label: '关闭', value: false },
      ],
      enable_sequential: [
        { label: '开启', value: true },
        { label: '关闭', value: false },
      ],
    },
    numericRanges: {
      seed: { min: -1, max: 2147483647, step: 1 },
    },
  };

  return {
    generation,
    edit: {
      ...generation,
      defaults: {
        ...generation.defaults,
        thinking_mode: undefined,
      },
      constraints: {
        ...generation.constraints,
        unsupported_params: ['negative_prompt', 'prompt_extend', 'add_magic_suffix', 'thinking_mode'],
      },
      paramOptions: {
        number_of_images: generation.paramOptions.number_of_images,
      },
    },
  };
});

vi.mock('../../../hooks/useModeControlsSchema', () => ({
  useModeControlsSchema: (_providerId: string, mode: string) => ({
    schema: mode === 'image-gen' ? wan27Schemas.generation : wan27Schemas.edit,
    loading: false,
    error: null,
  }),
  getPixelResolutionFromSchema: (schema: any, aspectRatio: string, resolution: string) =>
    schema?.resolutionMap?.[resolution]?.[aspectRatio] ?? null,
}));

vi.mock('../../../hooks/useEnhancePromptModels', () => ({
  useEnhancePromptModels: () => [
    {
      id: 'qwen-vl-max',
      name: 'Qwen VL Max',
      description: 'Qwen VL Max',
      capabilities: { vision: true, search: true, reasoning: false, coding: false },
    },
  ],
}));

import { ImageGenControls } from './ImageGenControls';
import { ImageEditControls } from './ImageEditControls';

afterEach(() => {
  cleanup();
});

const makeControls = () => ({
  style: 'None',
  setStyle: vi.fn(),
  numberOfImages: 1,
  setNumberOfImages: vi.fn(),
  aspectRatio: '1:1',
  setAspectRatio: vi.fn(),
  resolution: '2K',
  setResolution: vi.fn(),
  showAdvanced: true,
  setShowAdvanced: vi.fn(),
  seed: -1,
  setSeed: vi.fn(),
  negativePrompt: 'bad text',
  setNegativePrompt: vi.fn(),
  promptExtend: true,
  setPromptExtend: vi.fn(),
  enhancePrompt: true,
  setEnhancePrompt: vi.fn(),
  enhancePromptModel: 'qwen-vl-max',
  setEnhancePromptModel: vi.fn(),
  enhancePromptThinkingLevel: 'auto',
  setEnhancePromptThinkingLevel: vi.fn(),
  addMagicSuffix: true,
  setAddMagicSuffix: vi.fn(),
  thinkingMode: true,
  setThinkingMode: vi.fn(),
  enableSequential: false,
  setEnableSequential: vi.fn(),
});

describe('Tongyi image controls', () => {
  it('renders wan2.7 generation image count as a slider capped to standard mode', () => {
    const controls = makeControls();
    render(
      <ImageGenControls
        providerId="tongyi"
        currentModel={{ id: 'wan2.7-image-pro', name: 'Wan 2.7 Image Pro' }}
        controls={controls as any}
      />
    );

    const slider = screen.getByRole('slider', { name: '图片数量' });
    expect(slider).toBeInTheDocument();
    expect(slider).toHaveAttribute('max', '4');
    fireEvent.change(slider, { target: { value: '4' } });
    expect(controls.setNumberOfImages).toHaveBeenCalledWith(4);
    expect(screen.queryByRole('button', { name: '4' })).not.toBeInTheDocument();
  });

  it('allows 12 wan2.7 generation images only when sequential mode is enabled', () => {
    const controls = {
      ...makeControls(),
      numberOfImages: 12,
      enableSequential: true,
    };

    render(
      <ImageGenControls
        providerId="tongyi"
        currentModel={{ id: 'wan2.7-image-pro', name: 'Wan 2.7 Image Pro' }}
        controls={controls as any}
      />
    );

    expect(screen.getByRole('switch', { name: '组图生成' })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('slider', { name: '图片数量' })).toHaveAttribute('max', '12');
    expect(screen.queryByText('思考模式')).not.toBeInTheDocument();
  });

  it('toggles wan2.7 sequential mode from the generation controls', () => {
    const controls = makeControls();
    render(
      <ImageGenControls
        providerId="tongyi"
        currentModel={{ id: 'wan2.7-image-pro', name: 'Wan 2.7 Image Pro' }}
        controls={controls as any}
      />
    );

    fireEvent.click(screen.getByRole('switch', { name: '组图生成' }));
    expect(controls.setEnableSequential).toHaveBeenCalledWith(true);
  });

  it('renders wan2.7 edit image count as the same slider control', () => {
    render(
      <ImageEditControls
        providerId="tongyi"
        currentModel={{ id: 'wan2.7-image-pro', name: 'Wan 2.7 Image Pro' } as any}
        controls={makeControls() as any}
      />
    );

    expect(screen.getByRole('slider', { name: '图片数量' })).toBeInTheDocument();
  });

  it('renders wan2.7 generation controls with local prompt enhancement but without unsupported DashScope fields', () => {
    render(
      <ImageGenControls
        providerId="tongyi"
        currentModel={{ id: 'wan2.7-image-pro', name: 'Wan 2.7 Image Pro' }}
        controls={makeControls() as any}
      />
    );

    expect(screen.getByText('思考模式')).toBeInTheDocument();
    expect(screen.queryByText('负向提示词')).not.toBeInTheDocument();
    expect(screen.getByText('AI 增强提示词')).toBeInTheDocument();
    expect(screen.getByLabelText('增强提示词模型')).toBeInTheDocument();
    expect(screen.getByLabelText('思考等级')).toBeInTheDocument();
    expect(screen.queryByText('魔法词组')).not.toBeInTheDocument();
  });

  it('renders wan2.7 edit controls with local prompt enhancement but without unsupported DashScope fields', () => {
    render(
      <ImageEditControls
        providerId="tongyi"
        currentModel={{ id: 'wan2.7-image-pro', name: 'Wan 2.7 Image Pro' } as any}
        controls={makeControls() as any}
      />
    );

    expect(screen.queryByText('思考模式')).not.toBeInTheDocument();
    expect(screen.queryByText('负面提示词')).not.toBeInTheDocument();
    expect(screen.getByText('AI 增强提示词')).toBeInTheDocument();
    expect(screen.getByLabelText('增强提示词模型')).toBeInTheDocument();
  });
});
