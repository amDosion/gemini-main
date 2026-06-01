import { beforeEach, describe, expect, it, vi } from 'vitest';

class MockBroadcastChannel {
  static instances: MockBroadcastChannel[] = [];

  readonly name: string;
  readonly postMessage = vi.fn();
  readonly listeners = new Map<string, (event: MessageEvent) => void>();

  constructor(name: string) {
    this.name = name;
    MockBroadcastChannel.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    this.listeners.set(type, listener);
  }
}

describe('authSync', () => {
  beforeEach(() => {
    vi.resetModules();
    MockBroadcastChannel.instances = [];
    vi.stubGlobal('BroadcastChannel', MockBroadcastChannel);
  });

  it('broadcasts token refresh as a cookie state signal without JS-visible tokens', async () => {
    const { broadcastTokenRefresh } = await import('./authSync');

    broadcastTokenRefresh();

    const channel = MockBroadcastChannel.instances[0];
    expect(channel.postMessage).toHaveBeenCalledWith(
      expect.not.objectContaining({
        accessToken: expect.any(String),
      })
    );
    expect(channel.postMessage).toHaveBeenCalledWith(
      expect.not.objectContaining({
        refreshToken: expect.any(String),
      })
    );
  });

  it('notifies token refresh listeners without passing token values through BroadcastChannel', async () => {
    const { listenTokenRefresh } = await import('./authSync');
    const listener = vi.fn();

    listenTokenRefresh(listener);
    const channel = MockBroadcastChannel.instances[0];
    channel.listeners.get('message')?.({
      data: {
        type: 'token_refreshed',
        accessToken: 'access-token',
        refreshToken: 'refresh-token',
      },
    } as MessageEvent);

    expect(listener).toHaveBeenCalledWith();
  });
});
