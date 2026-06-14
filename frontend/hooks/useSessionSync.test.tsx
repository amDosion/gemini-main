// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSessionSync } from './useSessionSync';
import { ChatSession, Message, ModelConfig, Role } from '../types/types';
import { skipModeRestoreFlag } from '../contexts/SessionContext';
import { cacheManager } from '../services/CacheManager';
import { readCachedSessionsForMode, writeCachedSessionsForMode } from '../services/sessionCache';
import { setPrivateCacheUserScope } from '../services/privateCacheScope';
import { getModeMessages, resetModeMessages } from './modeMessageStore';

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
    cacheManager.clearAll();
    resetModeMessages();
    setPrivateCacheUserScope(null);
    skipModeRestoreFlag.current = false;
  });

  it('does not lazy-load session details when no current session is selected', () => {
    const setAppMode = vi.fn();

    renderHook(() =>
      useSessionSync({
        currentSessionId: null,
        sessions: [
          {
            id: 'latest-session',
            title: 'Latest',
            messages: [],
            createdAt: 2,
            mode: 'chat',
          },
        ],
        setAppMode,
      })
    );

    expect(apiGetMock).not.toHaveBeenCalled();
    expect(getModeMessages('chat')).toEqual([]);
    expect(setAppMode).not.toHaveBeenCalled();
  });

  it('ignores late /api/sessions response from previous session switch for messages and mode', async () => {
    const staleLoad = createDeferred<ChatSession>();
    apiGetMock.mockImplementation((url: string) => {
      if (url === '/api/sessions/session-a') {
        return staleLoad.promise;
      }
      throw new Error(`Unexpected URL: ${url}`);
    });

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
      expect(getModeMessages('chat')).toEqual([sessionBMessage]);
      expect(setAppMode).toHaveBeenCalledWith('chat');
    });

    const chatMessagesAfterSwitch = getModeMessages('chat');
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

    expect(getModeMessages('chat')).toBe(chatMessagesAfterSwitch);
    expect(getModeMessages('image-gen')).toEqual([]);
    expect(setAppMode).toHaveBeenCalledTimes(appModeCallCountAfterSwitch);
    expect(setAppMode).not.toHaveBeenCalledWith('image-gen');
  });

  it('ignores late lazy-loaded session details after the private user scope changes', async () => {
    const staleLoad = createDeferred<ChatSession>();
    apiGetMock.mockImplementation((url: string) => {
      if (url === '/api/sessions/shared-session') {
        return staleLoad.promise;
      }
      throw new Error(`Unexpected URL: ${url}`);
    });

    const setAppMode = vi.fn();
    const staleMessage: Message = {
      id: 'user-one-message',
      role: Role.MODEL,
      content: 'user one stale content',
      attachments: [],
      timestamp: Date.now(),
      mode: 'image-gen',
    };

    setPrivateCacheUserScope('user-1');
    renderHook(() =>
      useSessionSync({
        currentSessionId: 'shared-session',
        sessions: [
          {
            id: 'shared-session',
            title: 'Shared',
            messages: [],
            createdAt: 1,
            mode: 'image-gen',
          },
        ],
        setAppMode,
      })
    );

    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledWith(
        '/api/sessions/shared-session',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    setPrivateCacheUserScope('user-2');

    await act(async () => {
      staleLoad.resolve({
        id: 'shared-session',
        title: 'Shared full',
        createdAt: 1,
        mode: 'image-gen',
        messages: [staleMessage],
      });
      await staleLoad.promise;
      await Promise.resolve();
    });

    expect(getModeMessages('image-gen')).toEqual([]);
    expect(setAppMode).not.toHaveBeenCalledWith('image-gen');
    expect(readCachedSessionsForMode('image-gen')).toBeNull();
  });

  it('passes AbortSignal when lazy loading session details', async () => {
    apiGetMock.mockResolvedValue({
      id: 'session-x',
      title: 'X',
      createdAt: 1,
      mode: 'chat',
      messages: [],
    } as ChatSession);

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
        setAppMode,
      })
    );

    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalled();
    });

    const requestOptions = apiGetMock.mock.calls[0]?.[1] as { signal?: AbortSignal } | undefined;
    expect(requestOptions?.signal).toBeDefined();
  });

  it('lazy loads session details when the session list arrives after currentSessionId', async () => {
    const fullMessage: Message = {
      id: 'image-gen-msg',
      role: Role.MODEL,
      content: 'generated image history',
      attachments: [],
      timestamp: Date.now(),
      mode: 'image-gen',
    };
    apiGetMock.mockResolvedValue({
      id: 'image-gen-session',
      title: 'Image Gen',
      createdAt: 1,
      mode: 'image-gen',
      messages: [fullMessage],
    } as ChatSession);

    const setAppMode = vi.fn();

    const { rerender } = renderHook(
      ({ sessions }) =>
        useSessionSync({
          currentSessionId: 'image-gen-session',
          sessions,
          setAppMode,
        }),
      {
        initialProps: { sessions: [] as ChatSession[] },
      }
    );

    expect(apiGetMock).not.toHaveBeenCalled();

    rerender({
      sessions: [
        {
          id: 'image-gen-session',
          title: 'Image Gen',
          messages: [],
          createdAt: 1,
          mode: 'image-gen',
        },
      ],
    });

    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledWith(
        '/api/sessions/image-gen-session',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
    await waitFor(() => {
      expect(getModeMessages('image-gen')).toEqual([fullMessage]);
      expect(setAppMode).toHaveBeenCalledWith('image-gen');
    });
  });

  it('derives the target cell from message mode when session mode is missing', async () => {
    const imageMessage: Message = {
      id: 'image-message-without-session-mode',
      role: Role.MODEL,
      content: 'image message',
      attachments: [],
      timestamp: Date.now(),
      mode: 'image-gen',
    };
    const setAppMode = vi.fn();

    renderHook(() =>
      useSessionSync({
        currentSessionId: 'session-without-mode',
        sessions: [
          {
            id: 'session-without-mode',
            title: 'No stored mode',
            messages: [imageMessage],
            createdAt: 1,
          },
        ],
        setAppMode,
      })
    );

    await waitFor(() => {
      expect(getModeMessages('image-gen')).toEqual([imageMessage]);
    });
    expect(getModeMessages('chat')).toEqual([]);
    expect(setAppMode).toHaveBeenCalledWith('image-gen');
  });

  it('writes lazy-loaded full session messages back to the mode session cache', async () => {
    const fullMessage: Message = {
      id: 'session-x-msg',
      role: Role.MODEL,
      content: 'loaded',
      attachments: [],
      timestamp: Date.now(),
      mode: 'image-gen',
    };
    apiGetMock.mockResolvedValue({
      id: 'session-x',
      title: 'X',
      createdAt: 1,
      mode: 'image-gen',
      messages: [fullMessage],
    } as ChatSession);

    writeCachedSessionsForMode('image-gen', [
      {
        id: 'session-x',
        title: 'X',
        messages: [],
        createdAt: 1,
        mode: 'image-gen',
      },
    ]);

    const setAppMode = vi.fn();

    renderHook(() =>
      useSessionSync({
        currentSessionId: 'session-x',
        sessions: [
          {
            id: 'session-x',
            title: 'X',
            messages: [],
            createdAt: 1,
            mode: 'image-gen',
          },
        ],
        setAppMode,
      })
    );

    await waitFor(() => {
      expect(getModeMessages('image-gen')).toEqual([fullMessage]);
    });

    expect(readCachedSessionsForMode('image-gen')?.[0]?.messages).toEqual([
      fullMessage,
    ]);
  });

  it('does not pollute the chat mode cache when a lazy-loaded session belongs to another mode', async () => {
    const fullMessage: Message = {
      id: 'image-msg',
      role: Role.MODEL,
      content: 'image loaded',
      attachments: [],
      timestamp: Date.now(),
      mode: 'image-gen',
    };
    apiGetMock.mockResolvedValue({
      id: 'image-session',
      title: 'Image',
      createdAt: 2,
      mode: 'image-gen',
      messages: [fullMessage],
    } as ChatSession);

    const chatSession: ChatSession = {
      id: 'chat-session',
      title: 'Chat',
      messages: [],
      createdAt: 1,
      mode: 'chat',
    };
    writeCachedSessionsForMode('chat', [chatSession]);

    const setAppMode = vi.fn();

    renderHook(() =>
      useSessionSync({
        currentSessionId: 'image-session',
        sessions: [
          {
            id: 'image-session',
            title: 'Image',
            messages: [],
            createdAt: 2,
            mode: 'image-gen',
          },
        ],
        setAppMode,
      })
    );

    await waitFor(() => {
      expect(getModeMessages('image-gen')).toEqual([fullMessage]);
    });

    expect(readCachedSessionsForMode('chat')).toEqual([chatSession]);
    expect(readCachedSessionsForMode('image-gen')?.[0]?.messages).toEqual([fullMessage]);
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
      expect(getModeMessages('chat')).toEqual([sessionBMessage]);
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
      expect(getModeMessages('chat')).toEqual(loadedMessages);
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
