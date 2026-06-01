// @vitest-environment jsdom

import React from 'react';
import { render, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mediaCacheMock = vi.hoisted(() => ({
  releaseMediaObjectUrl: vi.fn(),
  retainMediaObjectUrl: vi.fn(),
}));

vi.mock('../services/mediaCache', () => ({
  releaseMediaObjectUrl: mediaCacheMock.releaseMediaObjectUrl,
  retainMediaObjectUrl: mediaCacheMock.retainMediaObjectUrl,
}));

import { useRetainedBlobObjectUrl } from './useRetainedBlobObjectUrl';

describe('useRetainedBlobObjectUrl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('retains a blob object url while it is rendered and releases it on unmount', () => {
    const { unmount } = renderHook(() => useRetainedBlobObjectUrl('blob:visible-preview'));

    expect(mediaCacheMock.retainMediaObjectUrl).toHaveBeenCalledWith('blob:visible-preview');
    expect(mediaCacheMock.releaseMediaObjectUrl).not.toHaveBeenCalled();

    unmount();

    expect(mediaCacheMock.releaseMediaObjectUrl).toHaveBeenCalledWith('blob:visible-preview');
  });

  it('does not retain durable or data urls', () => {
    const { rerender, unmount } = renderHook(
      ({ objectUrl }) => useRetainedBlobObjectUrl(objectUrl),
      { initialProps: { objectUrl: '/api/storage/local-files/result.png' } }
    );

    rerender({ objectUrl: 'data:image/png;base64,abc' });
    unmount();

    expect(mediaCacheMock.retainMediaObjectUrl).not.toHaveBeenCalled();
    expect(mediaCacheMock.releaseMediaObjectUrl).not.toHaveBeenCalled();
  });

  it('releases the previous blob url when the visible preview changes', () => {
    const { rerender } = renderHook(
      ({ objectUrl }) => useRetainedBlobObjectUrl(objectUrl),
      { initialProps: { objectUrl: 'blob:first-preview' } }
    );

    rerender({ objectUrl: 'blob:second-preview' });

    expect(mediaCacheMock.retainMediaObjectUrl).toHaveBeenCalledWith('blob:first-preview');
    expect(mediaCacheMock.releaseMediaObjectUrl).toHaveBeenCalledWith('blob:first-preview');
    expect(mediaCacheMock.retainMediaObjectUrl).toHaveBeenCalledWith('blob:second-preview');
  });

  it('retains a blob object url before sibling layout effects can observe the rendered img', () => {
    const retainCountsAtLayout: number[] = [];

    const Probe = () => {
      useRetainedBlobObjectUrl('blob:layout-visible-thumbnail');
      React.useLayoutEffect(() => {
        retainCountsAtLayout.push(mediaCacheMock.retainMediaObjectUrl.mock.calls.length);
      }, []);

      return <img alt="Layout visible thumbnail" src="blob:layout-visible-thumbnail" />;
    };

    render(<Probe />);

    expect(retainCountsAtLayout[0]).toBeGreaterThan(0);
  });
});
