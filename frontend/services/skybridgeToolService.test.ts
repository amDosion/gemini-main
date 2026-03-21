// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  callSkybridgeTool,
  getSkybridgeHostType,
  isSkybridgeHostAvailable,
} from './skybridgeToolService';

const originalSkybridge = (window as any).skybridge;
const originalOpenai = (window as any).openai;
const originalParentDescriptor = Object.getOwnPropertyDescriptor(window, 'parent');

const restoreParentWindow = () => {
  if (originalParentDescriptor) {
    Object.defineProperty(window, 'parent', originalParentDescriptor);
    return;
  }
  Object.defineProperty(window, 'parent', {
    configurable: true,
    value: window,
  });
};

afterEach(() => {
  vi.restoreAllMocks();

  if (originalSkybridge === undefined) {
    delete (window as any).skybridge;
  } else {
    (window as any).skybridge = originalSkybridge;
  }

  if (originalOpenai === undefined) {
    delete (window as any).openai;
  } else {
    (window as any).openai = originalOpenai;
  }

  restoreParentWindow();
});

describe('skybridgeToolService', () => {
  it('returns unavailable when skybridge host is missing', () => {
    delete (window as any).skybridge;
    expect(getSkybridgeHostType()).toBeNull();
    expect(isSkybridgeHostAvailable()).toBe(false);
  });

  it('calls apps-sdk host tool via window.openai', async () => {
    (window as any).skybridge = { hostType: 'apps-sdk' };
    const callTool = vi.fn().mockResolvedValue({
      structuredContent: { ok: true },
      isError: false,
      result: 'ok',
    });
    (window as any).openai = { callTool };

    const result = await callSkybridgeTool('ping', {});

    expect(callTool).toHaveBeenCalledWith('ping', null);
    expect(result).toMatchObject({
      structuredContent: { ok: true },
      isError: false,
      result: 'ok',
    });
  });

  it('calls mcp-app host tool with JSON-RPC tools/call', async () => {
    (window as any).skybridge = { hostType: 'mcp-app' };

    const fakeParent = {
      postMessage: vi.fn((payload: any) => {
        window.dispatchEvent(
          new MessageEvent('message', {
            data: {
              jsonrpc: '2.0',
              id: payload.id,
              result: {
                content: [{ type: 'text', text: 'hello from mcp' }],
                structuredContent: { ok: true },
                isError: false,
                _meta: { requestId: 'req-1' },
              },
            },
          })
        );
      }),
    };

    Object.defineProperty(window, 'parent', {
      configurable: true,
      value: fakeParent,
    });

    const result = await callSkybridgeTool('lookup', { keyword: 'abc' });

    expect(fakeParent.postMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        jsonrpc: '2.0',
        method: 'tools/call',
        params: {
          name: 'lookup',
          arguments: { keyword: 'abc' },
        },
      }),
      '*'
    );
    expect(result.result).toBe('hello from mcp');
    expect(result.structuredContent).toEqual({ ok: true });
    expect(result.meta).toEqual({ requestId: 'req-1' });
  });

  it('throws when mcp-app returns JSON-RPC error', async () => {
    (window as any).skybridge = { hostType: 'mcp-app' };

    const fakeParent = {
      postMessage: vi.fn((payload: any) => {
        window.dispatchEvent(
          new MessageEvent('message', {
            data: {
              jsonrpc: '2.0',
              id: payload.id,
              error: {
                code: -32603,
                message: 'tool failed',
              },
            },
          })
        );
      }),
    };

    Object.defineProperty(window, 'parent', {
      configurable: true,
      value: fakeParent,
    });

    await expect(callSkybridgeTool('lookup', { keyword: 'abc' })).rejects.toThrow('tool failed');
  });
});
