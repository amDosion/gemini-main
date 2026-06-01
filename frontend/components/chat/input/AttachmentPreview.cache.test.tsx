// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Attachment } from '../../../types/types';
import type { CachedImageProps } from '../../common/CachedImage';
import { AttachmentPreview } from './AttachmentPreview';

const cachedImageProps: CachedImageProps[] = [];

vi.mock('../../common/CachedImage', () => ({
  CachedImage: (props: CachedImageProps) => {
    cachedImageProps.push(props);
    const imageProps = props.src ? { src: props.src } : {};
    return (
      <img
        data-testid="attachment-preview-cached-image"
        {...imageProps}
        alt={props.alt || ''}
      />
    );
  },
}));

describe('AttachmentPreview', () => {
  beforeEach(() => {
    cachedImageProps.length = 0;
  });

  afterEach(() => {
    cleanup();
  });

  it('renders cloudUrl-only image attachments through CachedImage', () => {
    const attachments: Attachment[] = [
      {
        id: 'att-uploaded-image',
        name: 'uploaded.png',
        mimeType: 'image/png',
        cloudUrl: '/api/storage/local-files/2026/05/31/uploaded.png',
        uploadStatus: 'completed',
      },
    ];

    render(<AttachmentPreview attachments={attachments} removeAttachment={vi.fn()} />);

    expect(screen.getByTestId('attachment-preview-cached-image')).toBeTruthy();
    expect(cachedImageProps).toHaveLength(1);
    expect(cachedImageProps[0]).toMatchObject({
      src: '/api/storage/local-files/2026/05/31/uploaded.png',
      source: {
        id: 'att-uploaded-image',
        attachmentId: 'att-uploaded-image',
        url: '/api/storage/local-files/2026/05/31/uploaded.png',
        cloudUrl: '/api/storage/local-files/2026/05/31/uploaded.png',
        mimeType: 'image/png',
        name: 'uploaded.png',
      },
    });
  });

  it('renders file-only image attachments through CachedImage without a raw blob src', () => {
    const file = new File(['image'], 'local.png', { type: 'image/png' });
    const attachments: Attachment[] = [
      {
        id: 'att-local-file',
        name: 'local.png',
        mimeType: 'image/png',
        file,
      },
    ];

    render(<AttachmentPreview attachments={attachments} removeAttachment={vi.fn()} />);

    expect(screen.getByTestId('attachment-preview-cached-image')).toBeTruthy();
    expect(cachedImageProps).toHaveLength(1);
    expect(cachedImageProps[0]).toMatchObject({
      src: null,
      source: {
        id: 'att-local-file',
        attachmentId: 'att-local-file',
        mimeType: 'image/png',
        name: 'local.png',
        file,
      },
    });
  });
});
