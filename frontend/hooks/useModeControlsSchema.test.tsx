// @vitest-environment jsdom
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/authTokenStore', () => ({
  withAuthorization: (headers: HeadersInit = {}) => new Headers(headers),
}));

import { useModeControlsSchema } from './useModeControlsSchema';

function Probe() {
  const { schema, loading, error } = useModeControlsSchema('google', 'video-gen', 'veo-3-fast');

  return (
    <div>
      <div data-testid="loading">{String(loading)}</div>
      <div data-testid="error">{error || ''}</div>
      <div data-testid="resolution">{schema?.defaults?.resolution || ''}</div>
      <div data-testid="enhance-mandatory">{String(schema?.videoContract?.fieldPolicies?.enhancePrompt?.mandatory ?? false)}</div>
      <div data-testid="extension-base-8-counts">
        {schema?.videoContract?.extensionDurationMatrix?.find((entry) => entry.baseSeconds === '8')?.options.length ?? 0}
      </div>
    </div>
  );
}

describe('useModeControlsSchema', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('requests provider mode controls from backend api', async () => {
    fetchMock.mockResolvedValueOnce(
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
              resolution: '720p',
              seconds: '8',
            },
            aspect_ratios: [{ label: '16:9', value: '16:9' }],
            resolution_tiers: [{ label: '720p', value: '720p', baseResolution: '1280x720' }],
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
      )
    );

    render(<Probe />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/modes/google/video-gen/controls?model_id=veo-3-fast',
        expect.objectContaining({
          credentials: 'include',
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
});
