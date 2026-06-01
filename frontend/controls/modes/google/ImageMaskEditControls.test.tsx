// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

const useModeControlsSchemaMock = vi.hoisted(() => vi.fn());

vi.mock('../../../hooks/useModeControlsSchema', () => ({
  useModeControlsSchema: useModeControlsSchemaMock,
}));

import { ImageMaskEditControls } from './ImageMaskEditControls';

const schemaWithMaskEditModes = {
  defaults: {
    edit_mode: 'EDIT_MODE_INPAINT_INSERTION',
    number_of_images: 1,
    output_mime_type: 'image/png',
    output_compression_quality: 100,
    mask_dilation: 0.06,
    guidance_scale: 15,
    negative_prompt: '',
  },
  paramOptions: {
    edit_mode: [
      { label: '插入内容', value: 'EDIT_MODE_INPAINT_INSERTION' },
      { label: '移除内容', value: 'EDIT_MODE_INPAINT_REMOVAL' },
    ],
    number_of_images: [{ label: '1', value: 1 }],
    output_mime_type: [{ label: 'PNG', value: 'image/png' }],
  },
  numericRanges: {
    mask_dilation: { min: 0, max: 1, step: 0.01 },
    guidance_scale: { min: 1, max: 20, step: 0.5 },
    output_compression_quality: { min: 1, max: 100, step: 1 },
  },
};

const schemaWithMaskCountOptions = {
  ...schemaWithMaskEditModes,
  paramOptions: {
    ...schemaWithMaskEditModes.paramOptions,
    number_of_images: [
      { label: '1', value: 1 },
      { label: '2', value: 2 },
      { label: '3', value: 3 },
      { label: '4', value: 4 },
    ],
  },
};

describe('Google ImageMaskEditControls', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders the mask edit modes supplied by the controls catalog', () => {
    useModeControlsSchemaMock.mockReturnValue({
      schema: schemaWithMaskEditModes,
      loading: false,
      error: null,
    });

    render(
      <ImageMaskEditControls
        providerId="google"
        editMode="EDIT_MODE_INPAINT_INSERTION"
        setEditMode={vi.fn()}
        numberOfImages={1}
        setNumberOfImages={vi.fn()}
        outputMimeType="image/png"
        setOutputMimeType={vi.fn()}
      />
    );

    const editModeSelect = screen.getByRole('combobox');
    expect(within(editModeSelect).getByRole('option', { name: '插入内容' })).toBeInTheDocument();
    expect(within(editModeSelect).getByRole('option', { name: '移除内容' })).toBeInTheDocument();
    expect(within(editModeSelect).queryByRole('option', { name: '扩展图像' })).not.toBeInTheDocument();
    expect(within(editModeSelect).queryByRole('option', { name: '背景替换' })).not.toBeInTheDocument();
  });

  it('normalizes an edit mode not present in the catalog back to the first catalog option', async () => {
    const setEditMode = vi.fn();
    useModeControlsSchemaMock.mockReturnValue({
      schema: schemaWithMaskEditModes,
      loading: false,
      error: null,
    });

    render(
      <ImageMaskEditControls
        providerId="google"
        editMode="UNSUPPORTED_EDIT_MODE"
        setEditMode={setEditMode}
        numberOfImages={1}
        setNumberOfImages={vi.fn()}
        outputMimeType="image/png"
        setOutputMimeType={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(setEditMode).toHaveBeenCalledWith('EDIT_MODE_INPAINT_INSERTION');
    });
  });

  it('uses the shared image count slider for mask generation count', () => {
    const setNumberOfImages = vi.fn();
    useModeControlsSchemaMock.mockReturnValue({
      schema: schemaWithMaskCountOptions,
      loading: false,
      error: null,
    });

    render(
      <ImageMaskEditControls
        providerId="google"
        editMode="EDIT_MODE_INPAINT_INSERTION"
        setEditMode={vi.fn()}
        numberOfImages={3}
        setNumberOfImages={setNumberOfImages}
        outputMimeType="image/png"
        setOutputMimeType={vi.fn()}
      />
    );

    const slider = screen.getByRole('slider', { name: '生成数量' });
    expect(slider).toHaveAttribute('min', '1');
    expect(slider).toHaveAttribute('max', '4');
    expect(slider).toHaveValue('3');

    fireEvent.change(slider, { target: { value: '4' } });
    expect(setNumberOfImages).toHaveBeenCalledWith(4);
  });
});
