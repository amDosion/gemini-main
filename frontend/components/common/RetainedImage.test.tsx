// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mediaCacheMock = vi.hoisted(() => ({
  releaseMediaObjectUrl: vi.fn(),
  retainMediaObjectUrl: vi.fn(),
}));

vi.mock('../../services/mediaCache', () => ({
  releaseMediaObjectUrl: mediaCacheMock.releaseMediaObjectUrl,
  retainMediaObjectUrl: mediaCacheMock.retainMediaObjectUrl,
}));

import { RetainedImage } from './RetainedImage';

describe('RetainedImage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('retains blob image urls for the rendered image lifetime', () => {
    const { unmount } = render(
      <RetainedImage
        src="blob:retained-image-preview"
        alt="Retained Preview"
        className="preview"
      />
    );

    expect(screen.getByAltText('Retained Preview').getAttribute('src')).toBe(
      'blob:retained-image-preview'
    );
    expect(mediaCacheMock.retainMediaObjectUrl).toHaveBeenCalledWith(
      'blob:retained-image-preview'
    );
    expect(mediaCacheMock.releaseMediaObjectUrl).not.toHaveBeenCalled();

    unmount();

    expect(mediaCacheMock.releaseMediaObjectUrl).toHaveBeenCalledWith(
      'blob:retained-image-preview'
    );
  });

  it('does not render internal local-blob image keys', () => {
    render(
      <RetainedImage
        src="local-blob:retained-file-only-image"
        alt="Internal Preview"
      />
    );

    expect(screen.queryByAltText('Internal Preview')).toBeNull();
    expect(mediaCacheMock.retainMediaObjectUrl).not.toHaveBeenCalled();
  });

  it('renders safe inline raster image data urls', () => {
    render(
      <RetainedImage
        src="data:image/png;base64,YWJj"
        alt="Inline Raster Preview"
      />
    );

    expect(screen.getByAltText('Inline Raster Preview').getAttribute('src')).toBe(
      'data:image/png;base64,YWJj'
    );
  });

  it('does not render inline svg image data urls', () => {
    render(
      <RetainedImage
        src="data:image/svg+xml;base64,PHN2Zy8+"
        alt="Inline Svg Preview"
      />
    );

    expect(screen.queryByAltText('Inline Svg Preview')).toBeNull();
  });

  it('lets callers recover failed retained image blobs before surfacing onError', () => {
    const onRecoverImageError = vi.fn(() => true);
    const onError = vi.fn();

    render(
      <RetainedImage
        src="blob:failed-retained-preview"
        alt="Recoverable Preview"
        onRecoverImageError={onRecoverImageError}
        onError={onError}
      />
    );

    fireEvent.error(screen.getByAltText('Recoverable Preview'));

    expect(onRecoverImageError).toHaveBeenCalledWith('blob:failed-retained-preview');
    expect(onError).not.toHaveBeenCalled();
  });

  it('stops rendering a retained image blob after caller recovery accepts the failure', () => {
    const onRecoverImageError = vi.fn(() => true);

    render(
      <RetainedImage
        src="blob:suppressed-retained-preview"
        alt="Suppressed Preview"
        onRecoverImageError={onRecoverImageError}
      />
    );

    fireEvent.error(screen.getByAltText('Suppressed Preview'));

    expect(screen.queryByAltText('Suppressed Preview')).toBeNull();
  });

  it('stops rendering a failed image blob after surfacing onError when no recovery is available', () => {
    const onError = vi.fn();

    render(
      <RetainedImage
        src="blob:unrecoverable-retained-preview"
        alt="Unrecoverable Preview"
        onError={onError}
      />
    );

    fireEvent.error(screen.getByAltText('Unrecoverable Preview'));

    expect(onError).toHaveBeenCalledTimes(1);
    expect(screen.queryByAltText('Unrecoverable Preview')).toBeNull();
  });

  it('stops rendering when the browser reports an equivalent resolved blob currentSrc', () => {
    const onError = vi.fn();

    render(
      <RetainedImage
        src="blob:https://gemini.dicry.cn:18443/equivalent-image"
        alt="Equivalent Blob Preview"
        onError={onError}
      />
    );

    const image = screen.getByAltText('Equivalent Blob Preview');
    Object.defineProperty(image, 'currentSrc', {
      configurable: true,
      value: 'blob:https://gemini.dicry.cn:18443/equivalent-image#resolved',
    });

    fireEvent.error(image);

    expect(onError).toHaveBeenCalledTimes(1);
    expect(screen.queryByAltText('Equivalent Blob Preview')).toBeNull();
  });

  it('keeps non-blob image urls mounted after surfacing onError', () => {
    const onError = vi.fn();

    render(
      <RetainedImage
        src="/api/storage/local-files/missing-image.png"
        alt="Missing Durable Preview"
        onError={onError}
      />
    );

    fireEvent.error(screen.getByAltText('Missing Durable Preview'));

    expect(onError).toHaveBeenCalledTimes(1);
    expect(screen.getByAltText('Missing Durable Preview')).not.toBeNull();
  });
});
