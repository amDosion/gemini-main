// @vitest-environment jsdom

import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CachedImageProps } from '../../common/CachedImage';
import { MaskEditSidebar } from './MaskEditSidebar';
import { Attachment, Message, Role } from '../../../types/types';

const cachedImageSpy = vi.fn();

vi.mock('../../common/CachedImage', () => ({
  CachedImage: (props: CachedImageProps) => {
    cachedImageSpy(props);
    return <img alt={props.alt || ''} src={props.src || ''} />;
  },
}));

describe('MaskEditSidebar cache-safe thumbnails', () => {
  beforeEach(() => {
    cachedImageSpy.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders and selects file-only history attachments through the shared local-blob preview path', () => {
    const file = new File(['mask-file-only'], 'mask-file-only.png', { type: 'image/png' });
    const setActiveImageUrl = vi.fn();
    const setActiveAttachments = vi.fn();
    const message: Message = {
      id: 'mask-message-file-only',
      role: Role.USER,
      content: 'mask source',
      timestamp: Date.now(),
      mode: 'image-mask-edit',
      attachments: [
        {
          id: 'att-mask-file-only',
          name: 'mask-file-only.png',
          mimeType: 'image/png',
          file,
          uploadStatus: 'pending',
        } as Attachment,
      ],
    };

    render(
      <MaskEditSidebar
        scrollRef={{ current: null }}
        messages={[message]}
        loadingState="idle"
        activeImageUrl={null}
        setActiveImageUrl={setActiveImageUrl}
        setActiveAttachments={setActiveAttachments}
        displayedThinkingContent=""
        isThinkingOpen={false}
        setIsThinkingOpen={vi.fn()}
      />
    );

    const thumbnailProps = cachedImageSpy.mock.calls[0]?.[0] as CachedImageProps;
    expect(thumbnailProps.src).toBe('local-blob:att-mask-file-only');
    expect(thumbnailProps.source).toMatchObject({
      attachmentId: 'att-mask-file-only',
      file,
      mimeType: 'image/png',
      name: 'mask-file-only.png',
    });

    fireEvent.click(screen.getByAltText('thumbnail').closest('.cursor-pointer')!);

    expect(setActiveImageUrl).toHaveBeenCalledWith('local-blob:att-mask-file-only');
    expect(setActiveAttachments).toHaveBeenCalledWith([
      expect.objectContaining({
        id: 'att-mask-file-only',
        file,
      }),
    ]);
  });
});
