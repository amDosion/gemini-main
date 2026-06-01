// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MessageItem from './MessageItem';
import { Role, type Message } from '../../types/types';

const { downloadBlobInBrowserMock } = vi.hoisted(() => ({
  downloadBlobInBrowserMock: vi.fn(),
}));

vi.mock('../../services/downloadService', () => ({
  downloadBlobInBrowser: downloadBlobInBrowserMock,
}));

vi.mock('../../hooks/useMessageProcessor', () => ({
  useMessageProcessor: () => ({
    isUser: false,
    displayContent: 'downloadable markdown',
    thinkingContent: '',
    isThinkingOpen: false,
    setIsThinkingOpen: vi.fn(),
    isThinkingComplete: true,
    showSearch: false,
    searchQueries: [],
    searchEntryPoint: null,
    hasGroundingChunks: false,
    groundingChunks: [],
    hasUrlContext: false,
    urlContextMetadata: null,
  }),
}));

vi.mock('./MarkdownRenderer', () => ({
  default: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock('../message/ThinkingBlock', () => ({
  ThinkingBlock: () => null,
}));

vi.mock('../message/SearchProcess', () => ({
  SearchProcess: () => null,
}));

vi.mock('../message/GroundingSources', () => ({
  GroundingSources: () => null,
}));

vi.mock('../message/UrlContextStatus', () => ({
  UrlContextStatus: () => null,
}));

vi.mock('../message/AttachmentGrid', () => ({
  AttachmentGrid: () => null,
}));

vi.mock('../message/BrowserProgressIndicator', () => ({
  BrowserProgressIndicator: () => null,
}));

vi.mock('./ToolCallDisplay', () => ({
  default: () => null,
}));

vi.mock('../research/ResearchProgressIndicator', () => ({
  default: () => null,
}));

vi.mock('../research/ResearchRequiredActionCard', () => ({
  default: () => null,
}));

describe('MessageItem markdown download', () => {
  beforeEach(() => {
    downloadBlobInBrowserMock.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('routes markdown downloads through the shared browser download service', async () => {
    const message: Message = {
      id: 'message-download',
      role: Role.MODEL,
      content: 'downloadable markdown',
      timestamp: Date.now(),
    };

    render(<MessageItem message={message} />);
    fireEvent.click(screen.getByTitle('Download as Markdown'));

    await waitFor(() => {
      expect(downloadBlobInBrowserMock).toHaveBeenCalledTimes(1);
    });

    const options = downloadBlobInBrowserMock.mock.calls[0]?.[0];
    expect(options.fileName).toMatch(/^message-.+\.md$/);
    expect(options.blob).toBeInstanceOf(Blob);
    expect(options.blob.type).toBe('text/markdown');
    await expect(options.blob.text()).resolves.toBe('downloadable markdown');
  });
});
