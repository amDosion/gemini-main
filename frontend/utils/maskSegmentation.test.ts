import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchAutoMaskPreview } from './maskSegmentation';

// Mock collaborators so the test isolates fetchAutoMaskPreview's parse/narrow logic.
const requestMock = vi.fn();
vi.mock('../services/apiClient', () => ({
  apiClient: {
    request: (...args: unknown[]) => requestMock(...args),
  },
}));

vi.mock('../hooks/handlers/attachmentUtils', () => ({
  fileToBase64: vi.fn(async () => 'data:image/png;base64,QUJD'),
}));

const IMAGE_URL = 'blob:http://localhost/active-image';

beforeEach(() => {
  requestMock.mockReset();
  // Stub the image fetch (first network call inside fetchAutoMaskPreview).
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      status: 200,
      blob: async () => new Blob(['x'], { type: 'image/png' }),
    })) as unknown as typeof fetch
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('fetchAutoMaskPreview response narrowing', () => {
  it('returns maskUrl from a nested { data: { success, masks } } envelope', async () => {
    requestMock.mockResolvedValueOnce({
      success: true,
      data: { success: true, masks: [{ url: 'https://cdn/mask-1.png' }] },
    });

    const result = await fetchAutoMaskPreview(IMAGE_URL, 'google', 'MASK_MODE_BACKGROUND');

    expect(result).toEqual({ maskUrl: 'https://cdn/mask-1.png', notice: null, error: null });
  });

  it('returns maskUrl from a flat { success, masks } envelope (no data wrapper)', async () => {
    requestMock.mockResolvedValueOnce({
      success: true,
      masks: [{ url: 'https://cdn/mask-flat.png' }],
    });

    const result = await fetchAutoMaskPreview(IMAGE_URL, undefined, 'MASK_MODE_FOREGROUND');

    expect(result.maskUrl).toBe('https://cdn/mask-flat.png');
    expect(result.error).toBeNull();
  });

  it('does not treat a non-object response as a mask and falls back to an error', async () => {
    requestMock.mockResolvedValueOnce('totally not an envelope');

    const result = await fetchAutoMaskPreview(IMAGE_URL, 'google', 'MASK_MODE_SEMANTIC');

    expect(result.maskUrl).toBeNull();
    expect(result.notice).toBeNull();
    expect(result.error).toContain('Unknown error');
  });

  it('ignores masks when success is falsy and surfaces the envelope error', async () => {
    requestMock.mockResolvedValueOnce({
      success: false,
      masks: [{ url: 'https://cdn/should-be-ignored.png' }],
      error: 'segmentation failed',
    });

    const result = await fetchAutoMaskPreview(IMAGE_URL, 'google', 'MASK_MODE_BACKGROUND');

    expect(result.maskUrl).toBeNull();
    expect(result.error).toContain('segmentation failed');
  });

  it('maps an access-denied error to a notice rather than an error', async () => {
    requestMock.mockResolvedValueOnce({
      success: false,
      error: 'image-segmentation-001: model access denied',
    });

    const result = await fetchAutoMaskPreview(IMAGE_URL, 'google', 'MASK_MODE_SEMANTIC');

    expect(result.maskUrl).toBeNull();
    expect(result.error).toBeNull();
    expect(result.notice).not.toBeNull();
  });

  it('returns a retry error when the API call throws', async () => {
    requestMock.mockRejectedValueOnce(new Error('network down'));

    const result = await fetchAutoMaskPreview(IMAGE_URL, 'google', 'MASK_MODE_FOREGROUND');

    expect(result.maskUrl).toBeNull();
    expect(result.notice).toBeNull();
    expect(result.error).toContain('请重试');
  });
});
