// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { Message, Role } from '../../types/types';

const { toolCallDisplaySpy } = vi.hoisted(() => ({
  toolCallDisplaySpy: vi.fn(),
}));

vi.mock('../../hooks/useMessageProcessor', () => ({
  useMessageProcessor: (message: any) => ({
    isUser: message.role === 'user',
    displayContent: message.content || '',
    thinkingContent: null,
    isThinkingOpen: false,
    setIsThinkingOpen: vi.fn(),
    isThinkingComplete: true,
    showSearch: false,
    searchQueries: [],
    searchEntryPoint: undefined,
    hasGroundingChunks: false,
    groundingChunks: [],
    hasUrlContext: false,
    urlContextMetadata: undefined,
  }),
}));

vi.mock('./MarkdownRenderer', () => ({
  default: ({ content }: { content: string }) => <div data-testid="markdown-content">{content}</div>,
}));

vi.mock('./ToolCallDisplay', () => ({
  default: (props: any) => {
    toolCallDisplaySpy(props);
    return (
      <div
        data-testid={`tool-call-display-${props.toolCall.id}`}
        data-result-call-id={props.toolResult?.callId || ''}
      />
    );
  },
}));

import MessageItem from './MessageItem';

const createModelMessage = (overrides: Partial<Message> = {}): Message => ({
  id: 'model-msg-1',
  role: Role.MODEL,
  content: 'assistant content',
  attachments: [],
  timestamp: Date.now(),
  mode: 'chat',
  ...overrides,
});

describe('MessageItem', () => {
  beforeEach(() => {
    toolCallDisplaySpy.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('shows message actions on mobile by default (not hover-only)', () => {
    render(<MessageItem message={createModelMessage()} isStreaming={false} />);

    const actions = screen.getByTestId('message-item-actions');
    expect(actions.className).toContain('opacity-100');
    expect(actions.className).toContain('md:opacity-0');
    expect(actions.className).toContain('md:group-hover:opacity-100');
    expect(screen.getByTitle('Copy text')).toBeInTheDocument();
  });

  it('matches tool results by callId even when results are out of order', () => {
    render(
      <MessageItem
        message={createModelMessage({
          toolCalls: [
            { id: 'call_1', type: 'function_call', name: 'tool_a', arguments: { q: 1 } },
            { id: 'call_2', type: 'function_call', name: 'tool_b', arguments: { q: 2 } },
          ],
          toolResults: [
            { callId: 'call_2', name: 'tool_b', result: 'result_b' },
            { callId: 'call_1', name: 'tool_a', result: 'result_a' },
          ],
        })}
        isStreaming={false}
      />
    );

    expect(toolCallDisplaySpy).toHaveBeenCalledTimes(2);

    const call1Props = toolCallDisplaySpy.mock.calls.find(
      ([props]) => props.toolCall.id === 'call_1'
    )?.[0];
    const call2Props = toolCallDisplaySpy.mock.calls.find(
      ([props]) => props.toolCall.id === 'call_2'
    )?.[0];

    expect(call1Props?.toolResult?.callId).toBe('call_1');
    expect(call2Props?.toolResult?.callId).toBe('call_2');
  });
});
