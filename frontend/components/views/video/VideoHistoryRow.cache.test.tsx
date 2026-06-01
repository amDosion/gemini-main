// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { VideoHistoryRow } from './VideoHistoryRow';
import { Role, type Message } from '../../../types/types';

vi.mock('../../common/CachedImage', () => ({
  CachedImage: ({
    src,
    source,
    alt,
    preferMemoryCache,
    replaceCachedObjectUrl,
    rawFallbackDelayMs: _rawFallbackDelayMs,
    ...props
  }: any) => (
    <img
      data-testid="cached-video-history-image"
      data-source-url={source?.url || ''}
      data-prefer-memory-cache={String(preferMemoryCache)}
      data-replace-cached-object-url={String(replaceCachedObjectUrl)}
      src={`cached:${src}`}
      alt={alt}
      {...props}
    />
  ),
}));

vi.mock('../../common/RetainedMedia', () => ({
  RetainedVideo: ({ src, ...props }: any) => (
    <video data-testid="retained-video-history-video" src={src || ''} {...props} />
  ),
}));

const baseProps = {
  isSelected: false,
  favorited: false,
  isActionMenuOpen: false,
  openActionMenu: null,
  historyItemRefs: { current: {} },
  showHoverPreview: vi.fn(),
  scheduleHideHoverPreview: vi.fn(),
  activateHistoryMessage: vi.fn(),
  setIsMobileHistoryOpen: vi.fn(),
  closeActionMenu: vi.fn(),
  closeHoverPreview: vi.fn(),
  openActionMenuBase: vi.fn(),
};

describe('VideoHistoryRow media cache integration', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders image-only video history previews through CachedImage', () => {
    const msg: Message = {
      id: 'video-history-image-row',
      role: Role.MODEL,
      content: 'use this image as the first frame',
      timestamp: Date.now(),
      mode: 'video-gen',
      attachments: [
        {
          id: 'reference-image',
          name: 'first-frame.png',
          mimeType: 'image/png',
          url: '/api/storage/local-files/video/first-frame.png',
        },
      ],
    };

    render(<VideoHistoryRow {...baseProps} msg={msg} />);

    const image = screen.getByTestId('cached-video-history-image');
    expect(image.getAttribute('src')).toBe(
      'cached:/api/storage/local-files/video/first-frame.png'
    );
    expect(image.getAttribute('data-source-url')).toBe(
      '/api/storage/local-files/video/first-frame.png'
    );
    expect(image.getAttribute('data-prefer-memory-cache')).toBe('true');
    expect(image.getAttribute('data-replace-cached-object-url')).toBe('false');
    expect(image.hasAttribute('loading')).toBe(false);
  });

  it('uses a durable cloudUrl when the attachment has no url field yet', () => {
    const msg: Message = {
      id: 'video-history-cloud-image-row',
      role: Role.MODEL,
      content: 'cloud preview image',
      timestamp: Date.now(),
      mode: 'video-gen',
      attachments: [
        {
          id: 'cloud-reference-image',
          name: 'cloud-frame.png',
          mimeType: 'image/png',
          cloudUrl: '/api/storage/local-files/video/cloud-frame.png',
          uploadStatus: 'completed',
        },
      ],
    };

    render(<VideoHistoryRow {...baseProps} msg={msg} />);

    const image = screen.getByTestId('cached-video-history-image');
    expect(image.getAttribute('src')).toBe(
      'cached:/api/storage/local-files/video/cloud-frame.png'
    );
  });

  it('renders file-only image previews through CachedImage instead of dropping the poster', () => {
    const file = new File(['video-poster-file-only'], 'video-poster-file-only.png', {
      type: 'image/png',
    });
    const msg: Message = {
      id: 'video-history-file-only-image-row',
      role: Role.MODEL,
      content: 'file-only first frame',
      timestamp: Date.now(),
      mode: 'video-gen',
      attachments: [
        {
          id: 'file-only-reference-image',
          name: 'video-poster-file-only.png',
          mimeType: 'image/png',
          file,
        },
      ],
    };

    render(<VideoHistoryRow {...baseProps} msg={msg} />);

    const image = screen.getByTestId('cached-video-history-image');
    expect(image.getAttribute('src')).toBe('cached:local-blob:file-only-reference-image');
    expect(image.getAttribute('data-source-url')).toBe('local-blob:file-only-reference-image');
  });

  it('uses a durable video cloudUrl instead of a stale blob video url', () => {
    const msg: Message = {
      id: 'video-history-stale-video-row',
      role: Role.MODEL,
      content: 'generated video',
      timestamp: Date.now(),
      mode: 'video-gen',
      attachments: [
        {
          id: 'generated-video',
          name: 'generated.mp4',
          mimeType: 'video/mp4',
          url: 'blob:https://gemini.dicry.cn:18443/stale-video-preview',
          cloudUrl: '/api/storage/local-files/video/generated.mp4',
        },
      ],
    };

    render(<VideoHistoryRow {...baseProps} msg={msg} />);

    expect(screen.getByTestId('retained-video-history-video').getAttribute('src')).toBe(
      '/api/storage/local-files/video/generated.mp4'
    );
  });

  it('does not render stale blob video previews without durable storage or a live file', () => {
    const msg: Message = {
      id: 'video-history-stale-blob-only',
      role: Role.MODEL,
      content: 'old generated video',
      timestamp: Date.now(),
      mode: 'video-gen',
      attachments: [
        {
          id: 'stale-video-only',
          name: 'stale.mp4',
          mimeType: 'video/mp4',
          url: 'blob:https://gemini.dicry.cn:18443/stale-video-only',
        },
      ],
    };

    render(<VideoHistoryRow {...baseProps} msg={msg} />);

    expect(screen.queryByTestId('retained-video-history-video')).toBeNull();
  });
});
