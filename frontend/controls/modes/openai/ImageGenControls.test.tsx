// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

const gptImageSchema = vi.hoisted(() => ({
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
    { label: 'Auto', value: 'auto', baseResolution: 'Auto' },
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
  useModeControlsSchema: () => ({ schema: gptImageSchema, loading: false, error: null }),
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
    {
      id: 'o4-mini',
      name: 'O4 Mini',
      description: '',
      capabilities: { vision: false, search: false, reasoning: true, coding: false },
    },
  ],
}));

import { ImageGenControls } from './ImageGenControls';

afterEach(() => {
  cleanup();
});

describe('OpenAI ImageGenControls', () => {
  it('renders GPT image generation params from backend schema', () => {
    const controls = {
      aspectRatio: '1:1',
      setAspectRatio: vi.fn(),
      resolution: 'auto',
      setResolution: vi.fn(),
      numberOfImages: 1,
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
      enhancePromptThinkingLevel: 'high',
      setEnhancePromptThinkingLevel: vi.fn(),
    };

    render(
      <ImageGenControls
        providerId="openai"
        currentModel={{
          id: 'gpt-image-2',
          name: 'GPT Image 2',
          description: '',
          capabilities: { vision: true, search: false, reasoning: false, coding: false },
        }}
        controls={controls as any}
      />
    );

    expect(screen.queryByText('图片质量')).not.toBeInTheDocument();
    expect(screen.queryByText('背景')).not.toBeInTheDocument();
    expect(screen.queryByText('审核')).not.toBeInTheDocument();
    expect(screen.queryByText('输出格式')).not.toBeInTheDocument();
    expect(screen.queryByText('压缩质量')).not.toBeInTheDocument();
    expect(screen.getByText('AI 增强提示词')).toBeInTheDocument();
    expect(screen.queryByText('OpenAI 图片接口')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Responses 模型')).not.toBeInTheDocument();
    expect(screen.getByText('增强提示词模型')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: '增强提示词模型' })).toHaveValue('gpt-5.4-mini');
    expect(screen.getByLabelText('思考等级')).toHaveValue('high');
    expect(screen.getByText('4:3')).toBeInTheDocument();
    expect(screen.getByText('3:4')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Max/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^4K/ })).not.toBeInTheDocument();
    expect(screen.queryByText('3:2')).not.toBeInTheDocument();
    expect(screen.queryByText('2:3')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('思考等级'), {
      target: { value: 'medium' },
    });
    expect(controls.setEnhancePromptThinkingLevel).toHaveBeenCalledWith('medium');

    fireEvent.click(screen.getByRole('switch', { name: 'AI 增强提示词' }));

    expect(controls.setEnhancePrompt).toHaveBeenCalledWith(false);
  });

  it('syncs GPT Image 2 controls to the official auto size default from schema', async () => {
    const controls = {
      aspectRatio: '1:1',
      setAspectRatio: vi.fn(),
      resolution: '1K',
      setResolution: vi.fn(),
      numberOfImages: 1,
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
      enhancePromptModel: '',
      setEnhancePromptModel: vi.fn(),
    };

    render(
      <ImageGenControls
        providerId="openai"
        currentModel={{
          id: 'gpt-image-2',
          name: 'GPT Image 2',
          description: '',
          capabilities: { vision: true, search: false, reasoning: false, coding: false },
        }}
        controls={controls as any}
      />
    );

    await waitFor(() => {
      expect(controls.setResolution).toHaveBeenCalledWith('auto');
    });
  });

  it('uses the shared slider pattern for GPT image quantity', () => {
    const controls = {
      aspectRatio: '1:1',
      setAspectRatio: vi.fn(),
      resolution: 'auto',
      setResolution: vi.fn(),
      numberOfImages: 3,
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
      enhancePromptModel: '',
      setEnhancePromptModel: vi.fn(),
    };

    render(
      <ImageGenControls
        providerId="openai"
        currentModel={{
          id: 'gpt-image-2',
          name: 'GPT Image 2',
          description: '',
          capabilities: { vision: true, search: false, reasoning: false, coding: false },
        }}
        controls={controls as any}
      />
    );

    const slider = screen.getByRole('slider', { name: '生成数量' });
    expect(slider).toHaveAttribute('min', '1');
    expect(slider).toHaveAttribute('max', '10');
    expect(slider).toHaveValue('3');

    fireEvent.change(slider, { target: { value: '7' } });

    expect(controls.setNumberOfImages).toHaveBeenCalledWith(7);
  });

  it('does not expose the implementation-level OpenAI image API selector', async () => {
    const controls = {
      aspectRatio: '1:1',
      setAspectRatio: vi.fn(),
      resolution: 'auto',
      setResolution: vi.fn(),
      numberOfImages: 1,
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
      enhancePromptModel: '',
      setEnhancePromptModel: vi.fn(),
    };

    render(
      <ImageGenControls
        providerId="openai"
        currentModel={{
          id: 'gpt-image-2',
          name: 'GPT Image 2',
          description: '',
          capabilities: { vision: true, search: false, reasoning: false, coding: false },
        }}
        controls={controls as any}
      />
    );

    expect(screen.queryByText('OpenAI 图片接口')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Responses 模型')).not.toBeInTheDocument();
  });
});
