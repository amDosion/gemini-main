// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CachedImageProps } from '../common/CachedImage';
import { AttachmentGrid } from './AttachmentGrid';
import type { Attachment } from '../../types/types';

const cachedImageProps: CachedImageProps[] = [];

vi.mock('../common/CachedImage', () => ({
  CachedImage: (props: CachedImageProps) => {
    cachedImageProps.push(props);
    return <img data-testid="cached-image" src={props.src || ''} alt={props.alt || ''} />;
  },
}));

vi.mock('../common/RetainedMedia', () => ({
  RetainedAudio: ({ src, ...props }: any) => (
    <audio data-testid="retained-audio" src={src || ''} {...props} />
  ),
  RetainedVideo: ({ src, ...props }: any) => (
    <video data-testid="retained-video" src={src || ''} {...props} />
  ),
}));

describe('AttachmentGrid', () => {
  beforeEach(() => {
    cachedImageProps.length = 0;
  });

  afterEach(() => {
    cleanup();
  });

  it('renders message image attachments through CachedImage so they use the shared media cache', () => {
    const attachments: Attachment[] = [
      {
        id: 'att-message-image',
        name: 'generated.png',
        mimeType: 'image/png',
        url: '/api/storage/local-files/2026/05/31/generated.png',
        tempUrl: 'https://provider.example.com/generated-temp.png',
        cloudUrl: '/api/storage/local-files/2026/05/31/generated.png',
        uploadStatus: 'completed',
        createdAt: 1780220000000,
      },
    ];

    render(<AttachmentGrid attachments={attachments} />);

    expect(screen.getByTestId('cached-image')).toBeTruthy();
    expect(cachedImageProps).toHaveLength(1);
    expect(cachedImageProps[0]).toMatchObject({
      src: '/api/storage/local-files/2026/05/31/generated.png',
      source: {
        id: 'att-message-image',
        attachmentId: 'att-message-image',
        url: '/api/storage/local-files/2026/05/31/generated.png',
        tempUrl: 'https://provider.example.com/generated-temp.png',
        cloudUrl: '/api/storage/local-files/2026/05/31/generated.png',
        mimeType: 'image/png',
        name: 'generated.png',
        uploadStatus: 'completed',
        createdAt: 1780220000000,
      },
    });
  });

  it('renders cloudUrl-only image attachments through CachedImage', () => {
    const attachments: Attachment[] = [
      {
        id: 'att-cloud-only-image',
        name: 'cloud-only.png',
        mimeType: 'image/png',
        cloudUrl: '/api/storage/local-files/2026/05/31/cloud-only.png',
        uploadStatus: 'completed',
      },
    ];

    render(<AttachmentGrid attachments={attachments} />);

    expect(screen.getByTestId('cached-image')).toBeTruthy();
    expect(cachedImageProps).toHaveLength(1);
    expect(cachedImageProps[0]).toMatchObject({
      src: '/api/storage/local-files/2026/05/31/cloud-only.png',
      source: {
        id: 'att-cloud-only-image',
        attachmentId: 'att-cloud-only-image',
        url: '/api/storage/local-files/2026/05/31/cloud-only.png',
        cloudUrl: '/api/storage/local-files/2026/05/31/cloud-only.png',
      },
    });
  });

  it('prefers durable cloudUrl for non-image media when the display url is a stale blob', () => {
    const attachments: Attachment[] = [
      {
        id: 'att-video',
        name: 'clip.mp4',
        mimeType: 'video/mp4',
        url: 'blob:https://gemini.dicry.cn:18443/revoked-video',
        cloudUrl: '/api/storage/local-files/2026/05/31/clip.mp4',
        uploadStatus: 'completed',
      },
    ];

    render(<AttachmentGrid attachments={attachments} />);

    const video = document.querySelector('video') as HTMLVideoElement | null;

    expect(video).toBeTruthy();
    expect(video?.getAttribute('data-testid')).toBe('retained-video');
    expect(video?.getAttribute('src')).toBe('/api/storage/local-files/2026/05/31/clip.mp4');
  });

  it('does not render stale blob video attachments that have no durable url or live file', () => {
    const attachments: Attachment[] = [
      {
        id: 'att-stale-video',
        name: 'stale.mp4',
        mimeType: 'video/mp4',
        url: 'blob:https://gemini.dicry.cn:18443/revoked-video-only',
      },
    ];

    render(<AttachmentGrid attachments={attachments} />);

    expect(screen.queryByTestId('retained-video')).toBeNull();
  });

  it('renders live file-backed blob audio attachments through RetainedAudio', () => {
    const attachments: Attachment[] = [
      {
        id: 'att-live-audio',
        name: 'live.wav',
        mimeType: 'audio/wav',
        url: 'blob:https://gemini.dicry.cn:18443/live-audio',
        file: new File(['audio'], 'live.wav', { type: 'audio/wav' }),
      },
    ];

    render(<AttachmentGrid attachments={attachments} />);

    expect(screen.getByTestId('retained-audio').getAttribute('src')).toBe(
      'blob:https://gemini.dicry.cn:18443/live-audio'
    );
  });
});
