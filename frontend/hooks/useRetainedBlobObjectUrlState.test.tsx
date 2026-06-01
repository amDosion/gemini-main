// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mediaCacheMock = vi.hoisted(() => ({
  releaseMediaObjectUrl: vi.fn(),
  retainMediaObjectUrl: vi.fn(),
}));

vi.mock('../services/mediaCache', () => ({
  releaseMediaObjectUrl: mediaCacheMock.releaseMediaObjectUrl,
  retainMediaObjectUrl: mediaCacheMock.retainMediaObjectUrl,
}));

import { useRetainedBlobObjectUrlState } from './useRetainedBlobObjectUrlState';

describe('useRetainedBlobObjectUrlState', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('retains an initial blob object url before exposing it to render', async () => {
    const retainCountsAtBlobRender: number[] = [];

    const Probe = () => {
      const [src] = useRetainedBlobObjectUrlState('blob:initial-thumbnail');
      if (src === 'blob:initial-thumbnail') {
        retainCountsAtBlobRender.push(mediaCacheMock.retainMediaObjectUrl.mock.calls.length);
      }
      return src ? <img alt="Initial blob thumbnail" src={src} /> : null;
    };

    render(<Probe />);

    await waitFor(() => {
      expect(retainCountsAtBlobRender.length).toBeGreaterThan(0);
    });
    expect(retainCountsAtBlobRender[0]).toBeGreaterThan(0);
  });
});
