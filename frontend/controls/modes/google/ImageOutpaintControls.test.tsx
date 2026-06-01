// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';

const schemaMock = vi.hoisted(() => ({
  defaults: {
    aspect_ratio: '1:1',
    outpaint_mode: 'scale',
    number_of_images: 1,
    x_scale: 1.5,
    y_scale: 1.5,
    output_mime_type: 'image/png',
    output_compression_quality: 100,
    seed: -1,
  },
  constraints: {
    max_image_count: 4,
    outpaint_modes: ['ratio', 'scale', 'offset', 'upscale'],
  },
  aspectRatios: [{ label: '1:1 Square', value: '1:1' }],
  paramOptions: {
    outpaint_mode: [
      { label: '按比例', value: 'ratio' },
      { label: '等比缩放', value: 'scale' },
      { label: '像素偏移', value: 'offset' },
      { label: '图片放大', value: 'upscale' },
    ],
    upscale_factor: [
      { label: '2x', value: 'x2' },
      { label: '3x', value: 'x3' },
      { label: '4x', value: 'x4' },
    ],
    number_of_images: [
      { label: '1', value: 1 },
      { label: '2', value: 2 },
      { label: '3', value: 3 },
      { label: '4', value: 4 },
    ],
    output_mime_type: [{ label: 'PNG', value: 'image/png' }],
  },
  numericRanges: {
    x_scale: { min: 1, max: 4, step: 0.1 },
    y_scale: { min: 1, max: 4, step: 0.1 },
    left_offset: { min: 0, max: 2000, step: 64 },
    right_offset: { min: 0, max: 2000, step: 64 },
    top_offset: { min: 0, max: 2000, step: 64 },
    bottom_offset: { min: 0, max: 2000, step: 64 },
    seed: { min: -1, max: 2147483647, step: 1 },
  },
}));

vi.mock('../../../hooks/useModeControlsSchema', () => ({
  useModeControlsSchema: () => ({ schema: schemaMock, loading: false, error: null }),
}));

import { ImageOutpaintControls } from './ImageOutpaintControls';

describe('Google ImageOutpaintControls', () => {
  it('uses the shared image count slider for non-upscale outpainting', () => {
    const setNumberOfImages = vi.fn();

    render(
      <ImageOutpaintControls
        providerId="google"
        controls={{
          outpaintMode: 'scale',
          setOutpaintMode: vi.fn(),
          numberOfImages: 2,
          setNumberOfImages,
        } as any}
      />
    );

    const slider = screen.getByRole('slider', { name: '生成数量' });
    expect(slider).toHaveAttribute('min', '1');
    expect(slider).toHaveAttribute('max', '4');
    expect(slider).toHaveValue('2');

    fireEvent.change(slider, { target: { value: '4' } });
    expect(setNumberOfImages).toHaveBeenCalledWith(4);
  });
});
