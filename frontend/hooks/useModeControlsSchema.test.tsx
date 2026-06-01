// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cacheManager, CACHE_DOMAINS } from '../services/CacheManager';
import { clearPrivateMemoryCaches } from '../services/privateClientCache';
import {
  scopedPrivateCacheKey,
  setPrivateCacheUserScope,
} from '../services/privateCacheScope';

vi.mock('../services/authTokenStore', () => ({
  withAuthorization: (headers: HeadersInit = {}) => new Headers(headers),
}));

import { clearSchemaCacheForLogout, useModeControlsSchema } from './useModeControlsSchema';

function Probe({
  providerId = 'google',
  mode = 'video-gen',
  modelId = 'veo-3-fast',
}: {
  providerId?: string;
  mode?: string;
  modelId?: string;
}) {
  const { schema, loading, error } = useModeControlsSchema(providerId, mode, modelId);

  return (
    <div>
      <div data-testid="loading">{String(loading)}</div>
      <div data-testid="error">{error || ''}</div>
      <div data-testid="resolution">{String(schema?.defaults?.resolution || '')}</div>
      <div data-testid="enhance-mandatory">{String(schema?.videoContract?.fieldPolicies?.enhancePrompt?.mandatory ?? false)}</div>
      <div data-testid="extension-base-8-counts">
        {schema?.videoContract?.extensionDurationMatrix?.find((entry) => entry.baseSeconds === '8')?.options.length ?? 0}
      </div>
    </div>
  );
}

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('useModeControlsSchema', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    clearSchemaCacheForLogout();
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    clearSchemaCacheForLogout();
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
  });

  const mockControlsResponse = (resolution: string) =>
    new Response(
      JSON.stringify({
        success: true,
        provider: 'google',
        mode: 'video-gen',
        model_id: 'veo-3-fast',
        schema: {
          provider: 'google',
          mode: 'video-gen',
          defaults: {
            aspect_ratio: '16:9',
            resolution,
            seconds: '8',
          },
          aspect_ratios: [{ label: '16:9', value: '16:9' }],
          resolution_tiers: [{ label: resolution, value: resolution, baseResolution: '1280x720' }],
          param_options: {
            seconds: [{ label: '8s', value: '8' }],
          },
          video_contract: {
            field_policies: {
              enhance_prompt: {
                mandatory: true,
              },
            },
            extension_duration_matrix: [
              {
                base_seconds: '8',
                options: [
                  { count: 0, label: '8s (base)', total_seconds: 8 },
                  { count: 1, label: '15s (+1 extensions)', total_seconds: 15 },
                ],
              },
            ],
          },
        },
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );

  it('requests provider mode controls from backend api', async () => {
    fetchMock.mockResolvedValueOnce(mockControlsResponse('720p'));

    render(<Probe />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/modes/google/video-gen/controls?model_id=veo-3-fast',
        expect.objectContaining({
          method: 'GET',
          signal: expect.any(AbortSignal),
        })
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false');
      expect(screen.getByTestId('error')).toHaveTextContent('');
      expect(screen.getByTestId('resolution')).toHaveTextContent('720p');
      expect(screen.getByTestId('enhance-mandatory')).toHaveTextContent('true');
      expect(screen.getByTestId('extension-base-8-counts')).toHaveTextContent('2');
    });
  });

  it('does not reuse controls schema cache across private user scopes', async () => {
    setPrivateCacheUserScope('user-1');
    fetchMock.mockResolvedValueOnce(mockControlsResponse('720p'));

    const first = render(<Probe />);

    await waitFor(() => {
      expect(screen.getByTestId('resolution')).toHaveTextContent('720p');
    });
    first.unmount();

    setPrivateCacheUserScope('user-2');
    fetchMock.mockResolvedValueOnce(mockControlsResponse('1080p'));

    render(<Probe />);

    await waitFor(() => {
      expect(screen.getByTestId('resolution')).toHaveTextContent('1080p');
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('reloads mounted controls schema when private user scope changes', async () => {
    setPrivateCacheUserScope('user-1');
    fetchMock.mockResolvedValueOnce(mockControlsResponse('720p'));

    render(<Probe />);

    await waitFor(() => {
      expect(screen.getByTestId('resolution')).toHaveTextContent('720p');
    });

    fetchMock.mockResolvedValueOnce(mockControlsResponse('1080p'));
    act(() => {
      setPrivateCacheUserScope('user-2');
    });

    await waitFor(() => {
      expect(screen.getByTestId('resolution')).toHaveTextContent('1080p');
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('does not repopulate controls schema cache when an in-flight request resolves after cache clear', async () => {
    setPrivateCacheUserScope('user-1');
    const staleRequest = createDeferred<Response>();
    const currentRequest = createDeferred<Response>();
    fetchMock
      .mockReturnValueOnce(staleRequest.promise)
      .mockReturnValueOnce(currentRequest.promise);

    render(<Probe />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    setPrivateCacheUserScope('user-2');
    clearPrivateMemoryCaches();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    await act(async () => {
      staleRequest.resolve(mockControlsResponse('720p'));
      await staleRequest.promise;
    });

    await waitFor(() => {
      expect(screen.getByTestId('resolution')).toBeEmptyDOMElement();
    });
    expect(
      cacheManager.get(
        scopedPrivateCacheKey(
          CACHE_DOMAINS.MODE_CONTROLS_SCHEMA,
          'google::video-gen::veo-3-fast',
          'user-1'
        )
      )
    ).toBeNull();

    await act(async () => {
      currentRequest.resolve(mockControlsResponse('1080p'));
      await currentRequest.promise;
    });

    await waitFor(() => {
      expect(screen.getByTestId('resolution')).toHaveTextContent('1080p');
      expect(screen.getByTestId('loading')).toHaveTextContent('false');
    });
  });
});
