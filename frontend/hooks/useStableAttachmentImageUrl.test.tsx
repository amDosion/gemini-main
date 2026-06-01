// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, renderHook, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Attachment } from '../types/types';
import { useStableAttachmentImageUrl } from './useStableAttachmentImageUrl';
import {
  __resetMediaCacheForTest,
  releaseMediaObjectUrl,
  retainMediaObjectUrl,
} from '../services/mediaCache';

describe('useStableAttachmentImageUrl', () => {
  beforeEach(() => {
    __resetMediaCacheForTest();
    let objectUrlIndex = 0;
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => {
        objectUrlIndex += 1;
        return `blob:stable-attachment-${objectUrlIndex}`;
      }),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
    __resetMediaCacheForTest();
    vi.restoreAllMocks();
  });

  it('reuses one object url per active file attachment', () => {
    const file = new File(['image'], 'image.png', { type: 'image/png' });
    const attachment: Attachment = {
      id: 'file-att',
      name: 'image.png',
      mimeType: 'image/png',
      file,
    };

    const { result } = renderHook(() => useStableAttachmentImageUrl([attachment]));

    expect(result.current(attachment)).toBe('blob:stable-attachment-1');
    expect(result.current(attachment)).toBe('blob:stable-attachment-1');
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
  });

  it('revokes object urls for files no longer present in active attachments', () => {
    const keptFile = new File(['kept'], 'kept.png', { type: 'image/png' });
    const removedFile = new File(['removed'], 'removed.png', { type: 'image/png' });
    const keptAttachment: Attachment = {
      id: 'kept',
      name: 'kept.png',
      mimeType: 'image/png',
      file: keptFile,
    };
    const removedAttachment: Attachment = {
      id: 'removed',
      name: 'removed.png',
      mimeType: 'image/png',
      file: removedFile,
    };

    const { result, rerender } = renderHook(
      ({ attachments }) => useStableAttachmentImageUrl(attachments),
      { initialProps: { attachments: [keptAttachment, removedAttachment] } }
    );

    expect(result.current(keptAttachment)).toBe('blob:stable-attachment-1');
    expect(result.current(removedAttachment)).toBe('blob:stable-attachment-2');

    rerender({ attachments: [keptAttachment] });

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:stable-attachment-2');
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:stable-attachment-1');
  });

  it('revokes all retained object urls on unmount', () => {
    const file = new File(['image'], 'image.png', { type: 'image/png' });
    const attachment: Attachment = {
      id: 'file-att',
      name: 'image.png',
      mimeType: 'image/png',
      file,
    };

    const { result, unmount } = renderHook(() => useStableAttachmentImageUrl([attachment]));

    expect(result.current(attachment)).toBe('blob:stable-attachment-1');

    unmount();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:stable-attachment-1');
  });

  it('keeps an inactive file object url while it is still retained by the active canvas url', () => {
    const file = new File(['image'], 'image.png', { type: 'image/png' });
    const attachment: Attachment = {
      id: 'file-att',
      name: 'image.png',
      mimeType: 'image/png',
      file,
    };

    const { result, rerender } = renderHook(
      ({ retainedObjectUrl }) =>
        useStableAttachmentImageUrl([], { retainedObjectUrl }),
      { initialProps: { retainedObjectUrl: null as string | null } }
    );

    const objectUrl = result.current(attachment);
    rerender({ retainedObjectUrl: objectUrl });

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(objectUrl);

    rerender({ retainedObjectUrl: '/api/storage/local-files/generated/result.png' });

    expect(URL.revokeObjectURL).toHaveBeenCalledWith(objectUrl);
  });

  it('does not revoke a file object url while the shared media cache still retains it', () => {
    vi.useFakeTimers();
    const file = new File(['retained'], 'retained.png', { type: 'image/png' });
    const attachment: Attachment = {
      id: 'retained-file-att',
      name: 'retained.png',
      mimeType: 'image/png',
      file,
    };

    const { result, rerender } = renderHook(
      ({ attachments }) => useStableAttachmentImageUrl(attachments),
      { initialProps: { attachments: [attachment] } }
    );

    const objectUrl = result.current(attachment);
    retainMediaObjectUrl(objectUrl);

    rerender({ attachments: [] });

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(objectUrl);

    releaseMediaObjectUrl(objectUrl);

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(objectUrl);
    vi.runOnlyPendingTimers();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith(objectUrl);
    vi.useRealTimers();
  });

  it('does not revoke a file url created during render for history thumbnails', () => {
    const file = new File(['history'], 'history.png', { type: 'image/png' });
    const attachment: Attachment = {
      id: 'history-file-att',
      name: 'history.png',
      mimeType: 'image/png',
      file,
    };

    const HistoryThumbnail = () => {
      const getStableUrl = useStableAttachmentImageUrl([], { retainedObjectUrl: null });
      return <img alt="history thumbnail" src={getStableUrl(attachment) || ''} />;
    };

    const { unmount } = render(<HistoryThumbnail />);

    expect(screen.getByAltText('history thumbnail').getAttribute('src')).toBe(
      'blob:stable-attachment-1'
    );
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:stable-attachment-1');

    unmount();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:stable-attachment-1');
  });

  it('uses durable urls for non-file attachments', () => {
    const attachment: Attachment = {
      id: 'stored-att',
      name: 'stored.png',
      mimeType: 'image/png',
      url: 'blob:https://gemini.dicry.cn:18443/stale',
      cloudUrl: '/api/storage/local-files/2026/05/31/stored.png',
    };

    const { result } = renderHook(() => useStableAttachmentImageUrl([attachment]));

    expect(result.current(attachment)).toBe('/api/storage/local-files/2026/05/31/stored.png');
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('prefers a durable url over creating a new file object url for persisted attachments', () => {
    const file = new File(['persisted'], 'persisted.png', { type: 'image/png' });
    const attachment: Attachment = {
      id: 'persisted-file-att',
      name: 'persisted.png',
      mimeType: 'image/png',
      file,
      url: 'blob:https://gemini.dicry.cn:18443/stale-persisted-preview',
      cloudUrl: '/api/storage/local-files/2026/05/31/persisted.png',
    };

    const { result } = renderHook(() => useStableAttachmentImageUrl([attachment]));

    expect(result.current(attachment)).toBe('/api/storage/local-files/2026/05/31/persisted.png');
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('can avoid creating file object urls when callers render through shared media cache', () => {
    const file = new File(['shared-cache'], 'shared-cache.png', { type: 'image/png' });
    const attachment: Attachment = {
      id: 'shared-cache-file-att',
      name: 'shared-cache.png',
      mimeType: 'image/png',
      file,
    };

    const { result } = renderHook(() =>
      useStableAttachmentImageUrl([attachment], { createFileObjectUrls: false })
    );

    expect(result.current(attachment)).toBeNull();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
});
