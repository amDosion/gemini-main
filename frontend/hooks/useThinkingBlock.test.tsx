// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Message } from '../types/types';
import { useThinkingBlock } from './useThinkingBlock';

function makeModelMessage(opts: {
  thoughts?: Array<{ type: string; content: string }>;
  textResponse?: string;
}): Message {
  return {
    id: 'msg-1',
    role: 'model',
    parts: [],
    thoughts: opts.thoughts ?? [],
    textResponse: opts.textResponse,
  } as unknown as Message;
}

describe('useThinkingBlock', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns empty displayedContent when messages is empty', () => {
    const { result } = renderHook(() => useThinkingBlock([], 'idle'));
    expect(result.current.displayedContent).toBe('');
    expect(result.current.fullContent).toBe('');
    expect(result.current.isStreaming).toBe(false);
  });

  it('snaps to fullContent immediately when loadingState is idle', () => {
    const messages: Message[] = [
      makeModelMessage({
        thoughts: [{ type: 'text', content: 'analyzing prompt' }],
        textResponse: 'done',
      }),
    ];
    const { result } = renderHook(() => useThinkingBlock(messages, 'idle'));
    expect(result.current.displayedContent).toContain('analyzing prompt');
    expect(result.current.displayedContent).toContain('💬 AI 响应：\ndone');
    expect(result.current.isStreaming).toBe(false);
  });

  it('streams content in chunks while loading', async () => {
    const longText = 'abcdefghijklmnopqrst'; // 20 chars
    const messages: Message[] = [
      makeModelMessage({ thoughts: [{ type: 'text', content: longText }] }),
    ];

    const { result } = renderHook(() =>
      useThinkingBlock(messages, 'loading', { chunkSize: 5, delayMs: 30 }),
    );

    // Initial render: nothing displayed yet (timer pending)
    expect(result.current.displayedContent).toBe('');
    expect(result.current.isStreaming).toBe(true);

    // First chunk
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30);
    });
    expect(result.current.displayedContent).toBe('abcde');

    // Second chunk
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30);
    });
    expect(result.current.displayedContent).toBe('abcdefghij');

    // Drain remaining steps (3rd, 4th chunks): use a loop to follow React's async batching
    for (let i = 0; i < 10; i++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30);
      });
      if (!result.current.isStreaming) break;
    }
    expect(result.current.displayedContent).toBe(longText);
    expect(result.current.isStreaming).toBe(false);
  });

  it('renders [图片思考过程] placeholder for non-text thoughts', () => {
    const messages: Message[] = [
      makeModelMessage({
        thoughts: [
          { type: 'text', content: 'starting' },
          { type: 'image', content: '<binary>' },
        ],
      }),
    ];
    const { result } = renderHook(() => useThinkingBlock(messages, 'idle'));
    expect(result.current.fullContent).toContain('starting');
    expect(result.current.fullContent).toContain('[图片思考过程]');
  });

  it('cleans up pending timer on unmount (no setState-after-unmount warning)', () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const messages: Message[] = [
      makeModelMessage({ thoughts: [{ type: 'text', content: 'long content here' }] }),
    ];
    const { unmount } = renderHook(() =>
      useThinkingBlock(messages, 'loading', { chunkSize: 1, delayMs: 100 }),
    );

    // Timer is scheduled but not fired
    unmount();

    // Advance past when timer would have fired
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    // No 'setState on unmounted component' React warning
    expect(consoleErrorSpy).not.toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });

  it('isOpen defaults to true and respects autoOpen option', () => {
    const { result: r1 } = renderHook(() => useThinkingBlock([], 'idle'));
    expect(r1.current.isOpen).toBe(true);

    const { result: r2 } = renderHook(() => useThinkingBlock([], 'idle', { autoOpen: false }));
    expect(r2.current.isOpen).toBe(false);
  });
});
