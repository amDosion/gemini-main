// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mediaCacheMock = vi.hoisted(() => ({
  releaseMediaObjectUrl: vi.fn(),
  retainMediaObjectUrl: vi.fn(),
}));

vi.mock('../../../services/mediaCache', () => ({
  releaseMediaObjectUrl: mediaCacheMock.releaseMediaObjectUrl,
  retainMediaObjectUrl: mediaCacheMock.retainMediaObjectUrl,
}));

import { MaskPreviewImage } from './MaskPreviewImage';

describe('MaskPreviewImage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('retains blob preview urls for the exact rendered image lifetime', () => {
    const { unmount } = render(
      <MaskPreviewImage
        src="blob:mask-preview-rendered"
        alt="Mask Preview"
        className="preview"
      />
    );

    expect(screen.getByAltText('Mask Preview').getAttribute('src')).toBe(
      'blob:mask-preview-rendered'
    );
    expect(mediaCacheMock.retainMediaObjectUrl).toHaveBeenCalledWith(
      'blob:mask-preview-rendered'
    );
    expect(mediaCacheMock.releaseMediaObjectUrl).not.toHaveBeenCalled();

    unmount();

    expect(mediaCacheMock.releaseMediaObjectUrl).toHaveBeenCalledWith(
      'blob:mask-preview-rendered'
    );
  });
});
