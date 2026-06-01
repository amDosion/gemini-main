// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

const schemaWithoutOutputMime = vi.hoisted(() => ({
  defaults: {
    style: 'None',
    aspect_ratio: '1:1',
    resolution: '1K',
    number_of_images: 1,
    seed: -1,
    enhance_prompt: false,
    negative_prompt: '',
  },
  constraints: {
    max_image_count: 10,
  },
  aspectRatios: [{ label: '1:1 Square', value: '1:1' }],
  resolutionTiers: [{ label: '1K Standard', value: '1K', baseResolution: '1024×1024' }],
  resolutionMap: {
    '1K': { '1:1': '1024*1024' },
  },
  paramOptions: {
    style: [{ label: 'None', value: 'None' }],
    number_of_images: [{ label: '1', value: 1 }],
  },
  numericRanges: {
    seed: { min: -1, max: 2147483647, step: 1 },
  },
}));

vi.mock('../../../hooks/useModeControlsSchema', () => ({
  useModeControlsSchema: () => ({ schema: schemaWithoutOutputMime, loading: false, error: null }),
  getPixelResolutionFromSchema: (schema: any, aspectRatio: string, resolution: string) =>
    schema?.resolutionMap?.[resolution]?.[aspectRatio] ?? null,
}));

vi.mock('../../../hooks/useEnhancePromptModels', () => ({
  useEnhancePromptModels: () => [],
}));

import { ImageGenControls } from './ImageGenControls';

afterEach(() => {
  cleanup();
});

describe('Google ImageGenControls', () => {
  it('hides output format controls when the schema does not support output MIME options', () => {
    const controls = {
      style: 'None',
      setStyle: vi.fn(),
      numberOfImages: 1,
      setNumberOfImages: vi.fn(),
      aspectRatio: '1:1',
      setAspectRatio: vi.fn(),
      resolution: '1K',
      setResolution: vi.fn(),
      showAdvanced: true,
      setShowAdvanced: vi.fn(),
      negativePrompt: '',
      setNegativePrompt: vi.fn(),
      seed: -1,
      setSeed: vi.fn(),
      outputMimeType: 'image/jpeg',
      setOutputMimeType: vi.fn(),
      outputCompressionQuality: 65,
      setOutputCompressionQuality: vi.fn(),
      enhancePrompt: false,
      setEnhancePrompt: vi.fn(),
      enhancePromptModel: '',
      setEnhancePromptModel: vi.fn(),
      enableThinking: false,
      setEnableThinking: vi.fn(),
    };

    render(
      <ImageGenControls
        providerId="google"
        currentModel={{
          id: 'gemini-2.5-flash-image',
          name: 'Gemini 2.5 Flash Image',
          description: '',
          capabilities: {
            vision: true,
            search: false,
            reasoning: true,
            coding: false,
          },
        }}
        controls={controls as any}
        maxImageCount={10}
      />
    );

    expect(screen.queryByText('输出格式')).not.toBeInTheDocument();
    expect(screen.queryByText('压缩质量')).not.toBeInTheDocument();
  });

  it('shows thinking level on the prompt enhancement model, not the generated image model', () => {
    const controls = {
      style: 'None',
      setStyle: vi.fn(),
      numberOfImages: 1,
      setNumberOfImages: vi.fn(),
      aspectRatio: '1:1',
      setAspectRatio: vi.fn(),
      resolution: '1K',
      setResolution: vi.fn(),
      showAdvanced: true,
      setShowAdvanced: vi.fn(),
      negativePrompt: '',
      setNegativePrompt: vi.fn(),
      seed: -1,
      setSeed: vi.fn(),
      outputMimeType: 'image/png',
      setOutputMimeType: vi.fn(),
      outputCompressionQuality: 100,
      setOutputCompressionQuality: vi.fn(),
      enhancePrompt: true,
      setEnhancePrompt: vi.fn(),
      enhancePromptModel: '',
      setEnhancePromptModel: vi.fn(),
      enhancePromptThinkingLevel: 'medium',
      setEnhancePromptThinkingLevel: vi.fn(),
      enableThinking: true,
      setEnableThinking: vi.fn(),
    };

    render(
      <ImageGenControls
        providerId="google"
        currentModel={{
          id: 'gemini-3-pro-image-preview',
          name: 'Gemini 3 Pro Image',
          description: '',
          capabilities: {
            vision: true,
            search: false,
            reasoning: true,
            coding: false,
          },
        }}
        controls={controls as any}
        maxImageCount={10}
      />
    );

    expect(screen.getByRole('switch', { name: '显示思考过程' })).toBeInTheDocument();
    expect(screen.getByLabelText('思考等级')).toHaveValue('medium');

    fireEvent.change(screen.getByLabelText('思考等级'), {
      target: { value: 'high' },
    });

    expect(controls.setEnhancePromptThinkingLevel).toHaveBeenCalledWith('high');
  });
});
