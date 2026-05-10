// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';

const schemaMock = vi.hoisted(() => ({
  defaults: {
    aspect_ratio: '1:1',
    resolution: '1K',
    number_of_images: 1,
  },
  constraints: {
    max_image_count: 10,
  },
  aspectRatios: [{ label: '1:1 Square', value: '1:1' }],
  resolutionTiers: [
    { label: '1K Standard', value: '1K', baseResolution: '1024×1024' },
    { label: '4K Ultra', value: '4K', baseResolution: '4096×4096' },
  ],
  resolutionMap: {
    '1K': { '1:1': '1024*1024' },
    '4K': { '1:1': '4096*4096' },
  },
  paramOptions: {
    number_of_images: Array.from({ length: 10 }, (_, index) => ({
      label: String(index + 1),
      value: index + 1,
    })),
    output_mime_type: [{ label: 'PNG', value: 'image/png' }],
  },
}));

vi.mock('../../../hooks/useModeControlsSchema', () => ({
  useModeControlsSchema: () => ({ schema: schemaMock, loading: false, error: null }),
  getPixelResolutionFromSchema: (schema: any, aspectRatio: string, resolution: string) =>
    schema?.resolutionMap?.[resolution]?.[aspectRatio] ?? null,
}));

vi.mock('../../../hooks/useEnhancePromptModels', () => ({
  useEnhancePromptModels: () => [],
}));

import { ImageEditControls } from './ImageEditControls';

describe('Google ImageEditControls', () => {
  it('uses a slider and warns that recontext may return fewer images than requested', () => {
    const setNumberOfImages = vi.fn();

    render(
      <ImageEditControls
        providerId="google"
        mode="image-recontext"
        numberOfImages={3}
        setNumberOfImages={setNumberOfImages}
        aspectRatio="1:1"
        setAspectRatio={vi.fn()}
        resolution="1K"
        setResolution={vi.fn()}
      />
    );

    expect(screen.getByText('生成数量')).toBeInTheDocument();
    expect(screen.getByText('模型可能不会返回需求数量的图片')).toBeInTheDocument();

    const slider = screen.getByRole('slider');
    expect(slider).toHaveAttribute('min', '1');
    expect(slider).toHaveAttribute('max', '10');
    expect(slider).toHaveValue('3');

    fireEvent.change(slider, { target: { value: '7' } });
    expect(setNumberOfImages).toHaveBeenCalledWith(7);
  });
});
