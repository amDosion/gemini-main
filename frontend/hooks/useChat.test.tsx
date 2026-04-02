// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useChat } from './useChat';
import { AppMode, ChatOptions, Message, ModelConfig, Role } from '../types/types';

const {
  startNewChatMock,
  cancelCurrentStreamMock,
  preprocessorProcessMock,
  strategyGetHandlerMock,
  handlerExecuteMock,
} = vi.hoisted(() => ({
  startNewChatMock: vi.fn(),
  cancelCurrentStreamMock: vi.fn(),
  preprocessorProcessMock: vi.fn(),
  strategyGetHandlerMock: vi.fn(),
  handlerExecuteMock: vi.fn(),
}));

vi.mock('../services/llmService', () => ({
  llmService: {
    startNewChat: startNewChatMock,
    cancelCurrentStream: cancelCurrentStreamMock,
  },
}));

vi.mock('../services/storage/storageUpload', () => ({
  storageUpload: {},
}));

vi.mock('./handlers/strategyConfig', () => ({
  preprocessorRegistry: {
    process: preprocessorProcessMock,
  },
  strategyRegistry: {
    getHandler: strategyGetHandlerMock,
  },
}));

const DEFAULT_OPTIONS: ChatOptions = {
  enableSearch: false,
  enableThinking: false,
  enableCodeExecution: false,
  imageAspectRatio: '1:1',
  imageResolution: '1024x1024',
};

const DEFAULT_MODEL: ModelConfig = {
  id: 'gemini-3.1-pro-preview',
  name: 'Gemini 3.1 Pro Preview',
  description: 'test model',
  capabilities: {
    vision: true,
    search: true,
    reasoning: true,
    coding: true,
  },
};

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('useChat race and rollback fixes', () => {
  beforeEach(() => {
    startNewChatMock.mockReset();
    cancelCurrentStreamMock.mockReset();
    preprocessorProcessMock.mockReset();
    strategyGetHandlerMock.mockReset();
    handlerExecuteMock.mockReset();

    preprocessorProcessMock.mockImplementation(async (context: unknown) => context);
    handlerExecuteMock.mockResolvedValue({
      content: 'model response',
      attachments: [],
    });
    strategyGetHandlerMock.mockReturnValue({ execute: handlerExecuteMock });
  });

  it('sends first message with explicit target session id even before currentSessionId sync', async () => {
    const updateSessionMessages = vi.fn();

    const { result } = renderHook(() =>
      useChat(null, updateSessionMessages)
    );

    await act(async () => {
      await result.current.sendMessage(
        'hello world',
        DEFAULT_OPTIONS,
        [],
        'chat',
        DEFAULT_MODEL,
        'google',
        'session-new'
      );
    });

    await waitFor(() => {
      expect(updateSessionMessages).toHaveBeenCalledWith(
        'session-new',
        expect.arrayContaining([
          expect.objectContaining({ role: Role.USER, content: 'hello world' }),
          expect.objectContaining({ role: Role.MODEL, content: 'model response' }),
        ])
      );
    });

    expect(result.current.messages).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ role: Role.USER, content: 'hello world' }),
        expect.objectContaining({ role: Role.MODEL, content: 'model response' }),
      ])
    );
  });

  it('does not let stale in-flight request overwrite messages after switching sessions', async () => {
    const updateSessionMessages = vi.fn();
    const pending = createDeferred<{ content: string; attachments: never[] }>();
    handlerExecuteMock.mockReturnValueOnce(pending.promise);

    const { result, rerender } = renderHook(
      ({ sessionId }) => useChat(sessionId, updateSessionMessages),
      { initialProps: { sessionId: 'session-a' as string | null } }
    );

    let sendPromise!: Promise<void>;
    act(() => {
      sendPromise = result.current.sendMessage(
        'from session a',
        DEFAULT_OPTIONS,
        [],
        'chat',
        DEFAULT_MODEL,
        'google'
      );
    });

    await waitFor(() => {
      expect(result.current.messages.some(msg => msg.content === 'from session a')).toBe(true);
    });

    const sessionBMessage: Message = {
      id: 'session-b-existing-msg',
      role: Role.MODEL,
      content: 'session b content',
      timestamp: Date.now(),
      attachments: [],
      mode: 'chat' as AppMode,
    };

    rerender({ sessionId: 'session-b' });
    act(() => {
      result.current.setMessages([sessionBMessage]);
    });

    await act(async () => {
      pending.resolve({ content: 'late session a response', attachments: [] });
      await sendPromise;
    });

    expect(result.current.messages).toEqual([sessionBMessage]);

    expect(updateSessionMessages).toHaveBeenCalledWith(
      'session-a',
      expect.arrayContaining([
        expect.objectContaining({ role: Role.USER, content: 'from session a' }),
        expect.objectContaining({ role: Role.MODEL, content: 'late session a response' }),
      ])
    );
  });

  it('keeps existing messages when preprocessing fails (no slice(0,-1) rollback)', async () => {
    const updateSessionMessages = vi.fn();
    preprocessorProcessMock.mockRejectedValueOnce(new Error('upload failed'));

    const { result } = renderHook(() =>
      useChat('session-1', updateSessionMessages)
    );

    const existingMessage: Message = {
      id: 'existing-msg',
      role: Role.USER,
      content: 'already there',
      timestamp: Date.now(),
      attachments: [],
      mode: 'chat',
    };

    act(() => {
      result.current.setMessages([existingMessage]);
    });

    await act(async () => {
      await result.current.sendMessage(
        'new message',
        DEFAULT_OPTIONS,
        [],
        'chat',
        DEFAULT_MODEL,
        'google'
      );
    });

    expect(result.current.messages).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: 'existing-msg', content: 'already there' }),
        expect.objectContaining({ role: Role.MODEL, content: expect.stringContaining('upload failed') }),
      ])
    );
    expect(result.current.messages).toHaveLength(2);
  });

  it('uses merge-by-id persistence strategy for delayed uploadTask writeback to avoid snapshot rollback', async () => {
    const uploadTaskDeferred = createDeferred<{ dbAttachments: never[]; dbUserAttachments: never[] }>();
    let executeCount = 0;
    handlerExecuteMock.mockImplementation(async () => {
      executeCount += 1;
      if (executeCount === 1) {
        return {
          content: 'first response',
          attachments: [],
          uploadTask: uploadTaskDeferred.promise,
        };
      }
      return {
        content: 'second response',
        attachments: [],
      };
    });

    const persistedBySession: Record<string, Message[]> = {};
    const updateSessionMessages = vi.fn((
      sessionId: string,
      nextMessages: Message[],
      options?: { strategy?: 'replace' | 'merge-by-id' },
    ) => {
      const previous = persistedBySession[sessionId] || [];
      if (options?.strategy === 'merge-by-id') {
        const incomingById = new Map(nextMessages.map(message => [message.id, message]));
        const existingIds = new Set(previous.map(message => message.id));
        const merged = previous.map(message => incomingById.get(message.id) || message);
        for (const message of nextMessages) {
          if (!existingIds.has(message.id)) {
            merged.push(message);
          }
        }
        persistedBySession[sessionId] = merged;
        return;
      }
      persistedBySession[sessionId] = nextMessages;
    });

    const { result } = renderHook(() =>
      useChat('session-1', updateSessionMessages)
    );

    await act(async () => {
      await result.current.sendMessage(
        'first question',
        DEFAULT_OPTIONS,
        [],
        'chat',
        DEFAULT_MODEL,
        'google',
      );
    });

    await act(async () => {
      await result.current.sendMessage(
        'second question',
        DEFAULT_OPTIONS,
        [],
        'chat',
        DEFAULT_MODEL,
        'google',
      );
    });

    const afterSecondPersist = persistedBySession['session-1'] || [];
    expect(afterSecondPersist).toHaveLength(4);
    expect(afterSecondPersist).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ role: Role.USER, content: 'first question' }),
        expect.objectContaining({ role: Role.MODEL, content: 'first response' }),
        expect.objectContaining({ role: Role.USER, content: 'second question' }),
        expect.objectContaining({ role: Role.MODEL, content: 'second response' }),
      ])
    );

    await act(async () => {
      uploadTaskDeferred.resolve({ dbAttachments: [], dbUserAttachments: [] });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(updateSessionMessages).toHaveBeenCalledWith(
        'session-1',
        expect.any(Array),
        { strategy: 'merge-by-id' },
      );
    });

    const afterUploadWriteback = persistedBySession['session-1'] || [];
    expect(afterUploadWriteback).toHaveLength(4);
    expect(afterUploadWriteback).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ role: Role.USER, content: 'first question' }),
        expect.objectContaining({ role: Role.MODEL, content: 'first response' }),
        expect.objectContaining({ role: Role.USER, content: 'second question' }),
        expect.objectContaining({ role: Role.MODEL, content: 'second response' }),
      ])
    );
  });

  it('batches high-frequency stream updates to reduce rerender pressure', async () => {
    const updateSessionMessages = vi.fn();
    const streamChunkCount = 20;

    handlerExecuteMock.mockImplementation(async (context: any) => {
      for (let idx = 0; idx < streamChunkCount; idx += 1) {
        await new Promise<void>((resolve) => setTimeout(resolve, 4));
        context.onStreamUpdate?.({ content: `chunk-${idx}` });
      }

      return {
        content: 'final stream response',
        attachments: [],
      };
    });

    let renderCount = 0;
    const { result } = renderHook(() => {
      renderCount += 1;
      return useChat('session-stream', updateSessionMessages);
    });

    await act(async () => {
      await result.current.sendMessage(
        'streaming test',
        DEFAULT_OPTIONS,
        [],
        'chat',
        DEFAULT_MODEL,
        'google'
      );
    });

    expect(result.current.messages).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ role: Role.USER, content: 'streaming test' }),
        expect.objectContaining({ role: Role.MODEL, content: 'final stream response' }),
      ])
    );

    // With batching, rerenders should be materially lower than per-chunk updates.
    expect(renderCount).toBeLessThan(streamChunkCount);
  });

  it('keeps required_action submit handler alive after sending a new message', async () => {
    const updateSessionMessages = vi.fn();
    const pendingDeepResearch = createDeferred<any>();
    const submitAwaitingAction = vi.fn(async () => undefined);
    const deepInteractionId = 'interaction-awaiting-action-1';

    const deepResearchExecute = vi.fn(async (context: any) => {
      context.registerResearchActionHandler?.(deepInteractionId, submitAwaitingAction);
      context.onStreamUpdate?.({
        responseKind: 'deep-research',
        researchInteractionId: deepInteractionId,
        researchStatus: {
          status: 'awaiting_action',
          progress: '等待动作确认',
          elapsedTime: 1,
        },
        researchRequiredAction: {
          act: { name: 'confirm_scope' },
          inputs: ['最近30天'],
        },
      });

      return pendingDeepResearch.promise;
    });

    const chatExecute = vi.fn(async () => ({
      content: 'second response',
      attachments: [],
    }));

    strategyGetHandlerMock.mockImplementation((mode: string) => ({
      execute: mode === 'deep-research' ? deepResearchExecute : chatExecute,
    }));

    const { result } = renderHook(() =>
      useChat('session-keep-required-action', updateSessionMessages)
    );

    const deepResearchOptions: ChatOptions = {
      ...DEFAULT_OPTIONS,
      enableDeepResearch: true,
      deepResearchAgentId: 'deep-research-pro-preview-12-2025',
    };

    let firstSendPromise!: Promise<void>;
    act(() => {
      firstSendPromise = result.current.sendMessage(
        'first deep research',
        deepResearchOptions,
        [],
        'chat',
        DEFAULT_MODEL,
        'google',
      );
    });

    await waitFor(() => {
      const deepMessage = result.current.messages.find(
        (message) => message.responseKind === 'deep-research' && message.researchRequiredAction
      );
      expect(deepMessage).toBeTruthy();
    });

    await act(async () => {
      await result.current.sendMessage(
        'follow-up chat message',
        DEFAULT_OPTIONS,
        [],
        'chat',
        DEFAULT_MODEL,
        'google',
      );
    });

    const awaitingActionMessage = result.current.messages.find(
      (message) =>
        message.responseKind === 'deep-research' &&
        message.researchInteractionId === deepInteractionId
    );
    expect(awaitingActionMessage).toBeTruthy();

    await act(async () => {
      await result.current.submitResearchAction(awaitingActionMessage!.id, '最近30天');
    });

    expect(submitAwaitingAction).toHaveBeenCalledWith('最近30天');

    await act(async () => {
      pendingDeepResearch.resolve({
        content: 'deep research completed',
        attachments: [],
      });
      await firstSendPromise;
    });
  });
});
