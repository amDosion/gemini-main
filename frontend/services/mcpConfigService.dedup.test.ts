import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientGetMock = vi.hoisted(() => vi.fn());
const apiClientPutMock = vi.hoisted(() => vi.fn());

vi.mock('./apiClient', () => ({
  default: {
    get: apiClientGetMock,
    put: apiClientPutMock,
  },
}));

import mcpConfigService, { type McpConfigPayload } from './mcpConfigService';

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
};

const createDeferred = <T>(): Deferred<T> => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });

  return { promise, resolve, reject };
};

const CONFIG_CACHE_TTL_MS = 5 * 60 * 1000;

const resetServiceCache = (): void => {
  const serviceState = mcpConfigService as unknown as {
    getConfigInFlight: Promise<McpConfigPayload> | null;
    cachedConfig: McpConfigPayload | null;
    cachedAt: number;
    cacheEpoch: number;
  };

  serviceState.getConfigInFlight = null;
  serviceState.cachedConfig = null;
  serviceState.cachedAt = 0;
  serviceState.cacheEpoch = 0;
};

describe('mcpConfigService.getConfig session cache and in-flight deduplication', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    apiClientGetMock.mockReset();
    apiClientPutMock.mockReset();
    resetServiceCache();
  });

  it('shares one request for same-tick concurrent getConfig calls', async () => {
    const deferred = createDeferred<Record<string, unknown>>();
    apiClientGetMock.mockReturnValueOnce(deferred.promise);

    const first = mcpConfigService.getConfig();
    const second = mcpConfigService.getConfig();

    expect(apiClientGetMock).toHaveBeenCalledTimes(1);
    expect(apiClientGetMock).toHaveBeenCalledWith('/api/mcp/config');

    const rawPayload = {
      configJson: '{"mcpServers":{"demo":{}}}',
      updatedAt: '2026-06-14T10:00:00Z',
    };
    deferred.resolve(rawPayload);

    const [firstResult, secondResult] = await Promise.all([first, second]);
    expect(firstResult).toBe(secondResult);
    expect(firstResult).toEqual(rawPayload);
  });

  it('serves sequential getConfig calls from the completed session cache', async () => {
    const rawPayload = { configJson: '{"version":1}', updatedAt: 'first' };
    apiClientGetMock.mockResolvedValueOnce(rawPayload);

    const first = await mcpConfigService.getConfig();
    const second = await mcpConfigService.getConfig();

    expect(apiClientGetMock).toHaveBeenCalledTimes(1);
    expect(second).toBe(first);
    expect(second).toEqual(rawPayload);
  });

  it('updates the session cache after saveConfig so later getConfig does not GET', async () => {
    const savedConfigJson = '{"mcpServers":{"saved":{}}}';
    const savedPayload = {
      configJson: savedConfigJson,
      updatedAt: '2026-06-14T11:00:00Z',
    };
    apiClientPutMock.mockResolvedValueOnce(savedPayload);

    const saved = await mcpConfigService.saveConfig(savedConfigJson);
    const fetched = await mcpConfigService.getConfig();

    expect(apiClientPutMock).toHaveBeenCalledTimes(1);
    expect(apiClientPutMock).toHaveBeenCalledWith('/api/mcp/config', {
      config_json: savedConfigJson,
      configJson: savedConfigJson,
    });
    expect(apiClientGetMock).not.toHaveBeenCalled();
    expect(fetched).toBe(saved);
    expect(fetched.configJson).toBe(savedConfigJson);
  });

  it('does not let an older in-flight getConfig overwrite the cache after saveConfig', async () => {
    const getDeferred = createDeferred<Record<string, unknown>>();
    const savedConfigJson = '{"mcpServers":{"saved":{}}}';
    const savedPayload = {
      configJson: savedConfigJson,
      updatedAt: '2026-06-14T11:00:00Z',
    };
    apiClientGetMock.mockReturnValueOnce(getDeferred.promise);
    apiClientPutMock.mockResolvedValueOnce(savedPayload);

    const staleGet = mcpConfigService.getConfig();
    const saved = await mcpConfigService.saveConfig(savedConfigJson);

    getDeferred.resolve({ configJson: '{"mcpServers":{"stale":{}}}', updatedAt: 'stale' });
    await expect(staleGet).resolves.toEqual({
      configJson: '{"mcpServers":{"stale":{}}}',
      updatedAt: 'stale',
    });

    const fetched = await mcpConfigService.getConfig();
    expect(apiClientGetMock).toHaveBeenCalledTimes(1);
    expect(fetched).toBe(saved);
    expect(fetched.configJson).toBe(savedConfigJson);
  });

  it('rejects all concurrent callers on failure and allows a later retry', async () => {
    const failedDeferred = createDeferred<Record<string, unknown>>();
    const retryDeferred = createDeferred<Record<string, unknown>>();
    apiClientGetMock.mockReturnValueOnce(failedDeferred.promise).mockReturnValueOnce(retryDeferred.promise);

    const first = mcpConfigService.getConfig();
    const second = mcpConfigService.getConfig();
    const error = new Error('config unavailable');

    expect(apiClientGetMock).toHaveBeenCalledTimes(1);
    failedDeferred.reject(error);

    await expect(first).rejects.toThrow('config unavailable');
    await expect(second).rejects.toThrow('config unavailable');

    const retry = mcpConfigService.getConfig();
    expect(apiClientGetMock).toHaveBeenCalledTimes(2);

    retryDeferred.resolve({ configJson: '{"ok":true}', updatedAt: null });
    await expect(retry).resolves.toEqual({ configJson: '{"ok":true}', updatedAt: null });
  });

  it('does not cache a failed getConfig request and retries on the next call', async () => {
    const error = new Error('config unavailable');
    apiClientGetMock
      .mockRejectedValueOnce(error)
      .mockResolvedValueOnce({ configJson: '{"retry":true}', updatedAt: null });

    await expect(mcpConfigService.getConfig()).rejects.toThrow('config unavailable');
    expect(apiClientGetMock).toHaveBeenCalledTimes(1);

    await expect(mcpConfigService.getConfig()).resolves.toEqual({
      configJson: '{"retry":true}',
      updatedAt: null,
    });
    expect(apiClientGetMock).toHaveBeenCalledTimes(2);
  });

  it('refreshes config after the session cache TTL expires', async () => {
    let now = 1_000;
    vi.spyOn(Date, 'now').mockImplementation(() => now);
    apiClientGetMock
      .mockResolvedValueOnce({ configJson: '{"version":1}', updatedAt: 'first' })
      .mockResolvedValueOnce({ configJson: '{"version":2}', updatedAt: 'second' });

    await expect(mcpConfigService.getConfig()).resolves.toEqual({
      configJson: '{"version":1}',
      updatedAt: 'first',
    });
    expect(apiClientGetMock).toHaveBeenCalledTimes(1);

    now += CONFIG_CACHE_TTL_MS + 1;

    await expect(mcpConfigService.getConfig()).resolves.toEqual({
      configJson: '{"version":2}',
      updatedAt: 'second',
    });
    expect(apiClientGetMock).toHaveBeenCalledTimes(2);
  });
});
