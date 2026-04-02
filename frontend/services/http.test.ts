import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchWithTimeout, requestJson } from './http';

describe('http service utilities', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('injects Authorization header when withAuth is enabled', async () => {
    vi.stubGlobal('window', {
      localStorage: {
        getItem: vi.fn((key: string) => (key === 'access_token' ? 'token-123' : null)),
      },
    } as any);

    const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(
      async () =>
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
    );
    vi.stubGlobal('fetch', fetchMock);

    await requestJson<{ ok: boolean }>('/api/test', {
      method: 'GET',
      withAuth: true,
    });

    const requestInit = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(requestInit.headers);
    expect(headers.get('Authorization')).toBe('Bearer token-123');
  });

  it('throws stable timeout error when request exceeds timeoutMs', async () => {
    vi.useFakeTimers();

    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        const signal = init?.signal as AbortSignal | undefined;
        signal?.addEventListener(
          'abort',
          () => reject(new DOMException('Aborted', 'AbortError')),
          { once: true }
        );
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const pending = fetchWithTimeout('/api/slow', { timeoutMs: 25 });
    const assertion = expect(pending).rejects.toThrow('Request timeout after 25ms');
    await vi.advanceTimersByTimeAsync(30);
    await assertion;
  });

  it('parses JSON validation errors consistently', async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          detail: [{ loc: ['body', 'modelId'], msg: 'Field required', type: 'missing' }],
        }),
        {
          status: 422,
          headers: { 'content-type': 'application/json' },
        }
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(requestJson('/api/fail')).rejects.toThrow('body.modelId: Field required');
  });
});
