// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { Message, Role } from '../../types/types';

const { attachmentGridSpy, toolCallDisplaySpy } = vi.hoisted(() => ({
  attachmentGridSpy: vi.fn(),
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

vi.mock('../message/AttachmentGrid', () => ({
  AttachmentGrid: (props: any) => {
    attachmentGridSpy(props);
    return (
      <div
        data-testid="attachment-grid"
        data-first-cloud-url={props.attachments?.[0]?.cloudUrl || ''}
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
    attachmentGridSpy.mockClear();
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

  it('rerenders attachments when an existing message receives a durable cloudUrl', () => {
    const message = createModelMessage({
      id: 'model-msg-mutated-attachment',
      attachments: [
        {
          id: 'att-mutated',
          name: 'generated.png',
          mimeType: 'image/png',
          url: 'blob:https://gemini.dicry.cn:18443/message-stale-object-url',
        },
      ],
    });
    const durableUrl = '/api/storage/local-files/2026/05/31/message-generated.png';

    const { rerender } = render(<MessageItem message={message} isStreaming={false} />);

    expect(screen.getByTestId('attachment-grid')).toHaveAttribute('data-first-cloud-url', '');

    message.attachments![0].cloudUrl = durableUrl;

    rerender(<MessageItem message={message} isStreaming={false} />);

    expect(screen.getByTestId('attachment-grid')).toHaveAttribute(
      'data-first-cloud-url',
      durableUrl
    );
    expect(attachmentGridSpy.mock.calls.at(-1)?.[0].attachments[0].cloudUrl).toBe(durableUrl);
  });
});
