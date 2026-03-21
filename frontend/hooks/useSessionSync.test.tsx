// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSessionSync } from './useSessionSync';
import { ChatSession, Message, ModelConfig, Role } from '../types/types';
import { skipModeRestoreFlag } from '../contexts/SessionContext';

const { apiGetMock, llmStartNewChatMock } = vi.hoisted(() => ({
  apiGetMock: vi.fn(),
  llmStartNewChatMock: vi.fn(),
}));

vi.mock('../services/apiClient', () => ({
  apiClient: {
    get: apiGetMock,
  },
}));

vi.mock('../services/llmService', () => ({
  llmService: {
    startNewChat: llmStartNewChatMock,
  },
}));

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('useSessionSync stale request protection', () => {
  beforeEach(() => {
    apiGetMock.mockReset();
    llmStartNewChatMock.mockReset();
    skipModeRestoreFlag.current = false;
  });

  it('ignores late /api/sessions response from previous session switch for messages and mode', async () => {
    const staleLoad = createDeferred<ChatSession>();
    apiGetMock.mockImplementation((url: string) => {
      if (url === '/api/sessions/session-a') {
        return staleLoad.promise;
      }
      throw new Error(`Unexpected URL: ${url}`);
    });

    const setMessages = vi.fn();
    const setAppMode = vi.fn();

    const sessionBMessage: Message = {
      id: 'session-b-msg',
      role: Role.MODEL,
      content: 'session b cached content',
      attachments: [],
      timestamp: Date.now(),
      mode: 'chat',
    };

    const sessions: ChatSession[] = [
      {
        id: 'session-a',
        title: 'A',
        messages: [],
        createdAt: 1,
      },
      {
        id: 'session-b',
        title: 'B',
        messages: [sessionBMessage],
        createdAt: 2,
        mode: 'chat',
      },
    ];

    const { rerender } = renderHook(
      ({ currentSessionId }) =>
        useSessionSync({
          currentSessionId,
          sessions,
          setMessages,
          setAppMode,
        }),
      {
        initialProps: { currentSessionId: 'session-a' as string | null },
      }
    );

    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledWith(
        '/api/sessions/session-a',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    rerender({ currentSessionId: 'session-b' });

    await waitFor(() => {
      expect(setMessages).toHaveBeenCalledWith([sessionBMessage]);
      expect(setAppMode).toHaveBeenCalledWith('chat');
    });

    const messageCallCountAfterSwitch = setMessages.mock.calls.length;
    const appModeCallCountAfterSwitch = setAppMode.mock.calls.length;

    await act(async () => {
      staleLoad.resolve({
        id: 'session-a',
        title: 'A full',
        createdAt: 1,
        mode: 'image-gen',
        messages: [
          {
            id: 'session-a-late-msg',
            role: Role.MODEL,
            content: 'late stale content',
            attachments: [],
            timestamp: Date.now(),
            mode: 'image-gen',
          },
        ],
      });
      await Promise.resolve();
    });

    expect(setMessages).toHaveBeenCalledTimes(messageCallCountAfterSwitch);
    expect(setAppMode).toHaveBeenCalledTimes(appModeCallCountAfterSwitch);
    expect(setAppMode).not.toHaveBeenCalledWith('image-gen');
  });

  it('passes AbortSignal when lazy loading session details', async () => {
    apiGetMock.mockResolvedValue({
      id: 'session-x',
      title: 'X',
      createdAt: 1,
      mode: 'chat',
      messages: [],
    } as ChatSession);

    const setMessages = vi.fn();
    const setAppMode = vi.fn();

    const sessions: ChatSession[] = [
      {
        id: 'session-x',
        title: 'X',
        messages: [],
        createdAt: 1,
      },
    ];

    renderHook(() =>
      useSessionSync({
        currentSessionId: 'session-x',
        sessions,
        setMessages,
        setAppMode,
      })
    );

    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalled();
    });

    const requestOptions = apiGetMock.mock.calls[0]?.[1] as { signal?: AbortSignal } | undefined;
    expect(requestOptions?.signal).toBeDefined();
  });

  it('retries lazy load when switching back quickly after aborting previous fetch', async () => {
    const firstSessionALoad = createDeferred<ChatSession>();
    const secondSessionALoad = createDeferred<ChatSession>();
    let sessionALoadCount = 0;

    apiGetMock.mockImplementation((url: string, options?: { signal?: AbortSignal }) => {
      if (url !== '/api/sessions/session-a') {
        throw new Error(`Unexpected URL: ${url}`);
      }

      sessionALoadCount += 1;
      if (sessionALoadCount === 1) {
        options?.signal?.addEventListener('abort', () => {
          const abortError = Object.assign(new Error('aborted'), { name: 'AbortError' });
          firstSessionALoad.reject(abortError);
        }, { once: true });
        return firstSessionALoad.promise;
      }

      return secondSessionALoad.promise;
    });

    const setMessages = vi.fn();
    const setAppMode = vi.fn();

    const sessionBMessage: Message = {
      id: 'session-b-msg',
      role: Role.MODEL,
      content: 'session b cached content',
      attachments: [],
      timestamp: Date.now(),
      mode: 'chat',
    };

    const sessions: ChatSession[] = [
      {
        id: 'session-a',
        title: 'A',
        messages: [],
        createdAt: 1,
      },
      {
        id: 'session-b',
        title: 'B',
        messages: [sessionBMessage],
        createdAt: 2,
        mode: 'chat',
      },
    ];

    const { rerender } = renderHook(
      ({ currentSessionId }) =>
        useSessionSync({
          currentSessionId,
          sessions,
          setMessages,
          setAppMode,
        }),
      {
        initialProps: { currentSessionId: 'session-a' as string | null },
      }
    );

    await waitFor(() => {
      expect(sessionALoadCount).toBe(1);
    });

    rerender({ currentSessionId: 'session-b' });
    await waitFor(() => {
      expect(setMessages).toHaveBeenCalledWith([sessionBMessage]);
    });

    // 切回 session-a 时，应立即重新发起一次加载请求，不能被上一轮 loading 标记卡住。
    rerender({ currentSessionId: 'session-a' });
    await waitFor(() => {
      expect(sessionALoadCount).toBe(2);
    });

    const loadedMessages: Message[] = [
      {
        id: 'session-a-loaded-msg',
        role: Role.MODEL,
        content: 'session a loaded content',
        attachments: [],
        timestamp: Date.now(),
        mode: 'chat',
      },
    ];

    await act(async () => {
      secondSessionALoad.resolve({
        id: 'session-a',
        title: 'A full',
        createdAt: 1,
        mode: 'chat',
        messages: loadedMessages,
      });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(setMessages).toHaveBeenCalledWith(loadedMessages);
    });
  });

  it('uses latest model config when lazy-loaded session resolves', async () => {
    const deferredLoad = createDeferred<ChatSession>();
    apiGetMock.mockImplementation((url: string) => {
      if (url === '/api/sessions/session-a') {
        return deferredLoad.promise;
      }
      throw new Error(`Unexpected URL: ${url}`);
    });

    const setMessages = vi.fn();
    const setAppMode = vi.fn();
    const oldModel: ModelConfig = {
      id: 'model-old',
      name: 'Model Old',
      description: 'old',
      capabilities: {
        vision: false,
        search: false,
        reasoning: true,
        coding: false,
      },
    };
    const newModel: ModelConfig = {
      id: 'model-new',
      name: 'Model New',
      description: 'new',
      capabilities: {
        vision: true,
        search: true,
        reasoning: true,
        coding: true,
      },
    };
    const loadedMessages: Message[] = [
      {
        id: 'loaded-msg',
        role: Role.MODEL,
        content: 'loaded content',
        attachments: [],
        timestamp: Date.now(),
        mode: 'chat',
      },
    ];

    const sessions: ChatSession[] = [
      {
        id: 'session-a',
        title: 'A',
        messages: [],
        createdAt: 1,
      },
    ];

    const { rerender } = renderHook(
      ({ model }) =>
        useSessionSync({
          currentSessionId: 'session-a',
          sessions,
          activeModelConfig: model,
          setMessages,
          setAppMode,
        }),
      {
        initialProps: { model: oldModel as ModelConfig | undefined },
      }
    );

    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledTimes(1);
    });

    rerender({ model: newModel });

    await act(async () => {
      deferredLoad.resolve({
        id: 'session-a',
        title: 'A full',
        createdAt: 1,
        mode: 'chat',
        messages: loadedMessages,
      });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(llmStartNewChatMock).toHaveBeenCalledWith(loadedMessages, newModel);
    });
    expect(llmStartNewChatMock).not.toHaveBeenCalledWith(loadedMessages, oldModel);
  });
});
