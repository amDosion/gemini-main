// @vitest-environment jsdom

import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../common/CachedImage', () => ({
  CachedImage: ({ src, source, alt, ...props }: any) => (
    <img
      data-testid="cached-reference-image"
      data-source-url={source?.url || ''}
      src={`cached:${src}`}
      alt={alt}
      {...props}
    />
  ),
}));

import {
  InlineReferenceImagePreview,
  isPreviewableReferenceImageUrl,
} from './InlineReferenceImagePreview';

describe('InlineReferenceImagePreview', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders data reference images through CachedImage and supports clearing', () => {
    const onClear = vi.fn();

    render(
      <InlineReferenceImagePreview
        imageUrl="data:image/png;base64,YWJj"
        borderClassName="border-purple-500/30"
        onClear={onClear}
      />
    );

    expect(screen.getByAltText('参考图片')).toHaveAttribute(
      'src',
      'cached:data:image/png;base64,YWJj'
    );
    fireEvent.click(screen.getByRole('button', { name: '清除参考图片' }));
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it('renders durable storage reference images through CachedImage', () => {
    render(
      <InlineReferenceImagePreview
        imageUrl="/api/storage/local-files/workflow/reference.png"
        borderClassName="border-indigo-500/30"
        onClear={vi.fn()}
      />
    );

    expect(screen.getByTestId('cached-reference-image')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/reference.png'
    );
  });

  it('renders same-origin blob reference images through CachedImage', () => {
    const blobUrl = `blob:${window.location.origin}/reference-preview`;

    render(
      <InlineReferenceImagePreview
        imageUrl={blobUrl}
        borderClassName="border-indigo-500/30"
        onClear={vi.fn()}
      />
    );

    expect(screen.getByTestId('cached-reference-image')).toHaveAttribute(
      'data-source-url',
      blobUrl
    );
  });

  it.each([
    ['cross-origin blob', 'blob:https://evil.example/reference-preview'],
    ['inline svg', 'data:image/svg+xml;base64,PHN2Zy8+'],
    ['non-base64 data image', 'data:image/png,<svg onload=alert(1)>'],
  ])('does not render unsafe %s URLs', (_label, imageUrl) => {
    const { container } = render(
      <InlineReferenceImagePreview
        imageUrl={imageUrl}
        borderClassName="border-purple-500/30"
        onClear={vi.fn()}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('does not render inline images over the upload size cap', () => {
    expect(isPreviewableReferenceImageUrl('data:image/png;base64,YWJjZA==', 3)).toBe(false);
  });

  it('does not render workflow template expressions as image URLs', () => {
    const { container } = render(
      <InlineReferenceImagePreview
        imageUrl="{{prev.output.imageUrl}}"
        borderClassName="border-purple-500/30"
        onClear={vi.fn()}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });
});
