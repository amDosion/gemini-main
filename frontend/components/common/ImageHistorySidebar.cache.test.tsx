// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useImageHistorySidebar } from './ImageHistorySidebar';
import type { ImageHistoryListRowProps } from './ImageHistoryListRow';
import { extractImageHistoryPrompts } from './imageHistorySidebarHelpers';
import type { Attachment, Message } from '../../types/types';
import { Role } from '../../types/types';

const rowRenderStats = vi.hoisted(() => ({
  count: 0,
  messageIds: [] as string[],
}));

vi.mock('./ImageHistoryListRow', async () => {
  const ReactModule = await import('react');
  const MockImageHistoryListRow = ReactModule.memo((props: ImageHistoryListRowProps) => {
    rowRenderStats.count += 1;
    rowRenderStats.messageIds.push(props.message.id);

    return ReactModule.createElement(
      'button',
      {
        type: 'button',
        'data-testid': `history-row-${props.message.id}`,
        onMouseEnter: (event: React.MouseEvent<HTMLButtonElement>) => {
          props.showHoverPreview(
            event,
            props.message,
            props.message.content,
            '',
            props.getPreviewAttachments(props.message)
          );
        },
        onClick: () => {
          props.onSelectedMessageIdChange?.(props.message.id);
        },
      },
      props.message.content
    );
  });
  MockImageHistoryListRow.displayName = 'MockImageHistoryListRow';

  return { ImageHistoryListRow: MockImageHistoryListRow };
});

const HistoryHarness: React.FC<{
  items: Message[];
  onSelectItem: Parameters<typeof useImageHistorySidebar>[0]['onSelectItem'];
  fallbackSelection?: 'first' | 'last';
  disableFallbackSelection?: boolean;
}> = ({ items, onSelectItem, fallbackSelection, disableFallbackSelection }) => {
  const [selectedMessageId, setSelectedMessageId] = React.useState<string | null>(null);
  const getDisplayAttachments = React.useCallback(
    (attachments?: Attachment[]) => attachments || [],
    []
  );
  const getAttachmentUrl = React.useCallback((attachment: Attachment) => attachment.url || null, []);
  const { sidebarContent } = useImageHistorySidebar({
    items,
    sessionId: null,
    selectedMessageId,
    onSelectedMessageIdChange: setSelectedMessageId,
    fallbackSelection,
    disableFallbackSelection,
    getDisplayAttachments,
    getAttachmentUrl,
    extractPrompts: extractImageHistoryPrompts,
    onSelectItem,
  });

  return <>{sidebarContent}</>;
};

describe('useImageHistorySidebar cache-safe selection', () => {
  afterEach(() => {
    cleanup();
    rowRenderStats.count = 0;
    rowRenderStats.messageIds = [];
  });

  it('auto-selects the durable attachment url instead of a stale preview blob', async () => {
    const onSelectItem = vi.fn();
    const message: Message = {
      id: 'auto-select-durable-history',
      role: Role.MODEL,
      content: 'generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-auto-select-durable',
          name: 'generated.png',
          mimeType: 'image/png',
          url: 'blob:https://gemini.dicry.cn:18443/stale-auto-select',
          cloudUrl: '/api/storage/local-files/2026/06/01/generated.png',
        },
      ],
    };

    render(<HistoryHarness items={[message]} onSelectItem={onSelectItem} />);

    await waitFor(() => {
      expect(onSelectItem).toHaveBeenCalled();
    });

    expect(onSelectItem.mock.calls[0]?.[0].firstImage).toBe(
      '/api/storage/local-files/2026/06/01/generated.png'
    );
  });

  it('auto-selects the first renderable attachment when the first preview is stale blob-only', async () => {
    const onSelectItem = vi.fn();
    const message: Message = {
      id: 'auto-select-second-renderable-history',
      role: Role.MODEL,
      content: 'generated image batch',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-auto-select-stale-first',
          name: 'stale-first.png',
          mimeType: 'image/png',
          url: 'blob:https://gemini.dicry.cn:18443/auto-select-stale-first',
        },
        {
          id: 'att-auto-select-second',
          name: 'second.png',
          mimeType: 'image/png',
          url: '/api/storage/local-files/2026/06/01/second.png',
        },
      ],
    };

    render(<HistoryHarness items={[message]} onSelectItem={onSelectItem} />);

    await waitFor(() => {
      expect(onSelectItem).toHaveBeenCalled();
    });

    expect(onSelectItem.mock.calls[0]?.[0].firstImage).toBe(
      '/api/storage/local-files/2026/06/01/second.png'
    );
  });

  it('keeps file-only attachments in history preview candidates for the shared cache renderer', async () => {
    const onSelectItem = vi.fn();
    const file = new File(['file-only-history'], 'file-only.png', { type: 'image/png' });
    const message: Message = {
      id: 'auto-select-file-only-history',
      role: Role.MODEL,
      content: 'uploaded image',
      timestamp: Date.now(),
      mode: 'image-chat-edit',
      attachments: [
        {
          id: 'att-file-only-history',
          name: 'file-only.png',
          mimeType: 'image/png',
          file,
        },
      ],
    };

    render(<HistoryHarness items={[message]} onSelectItem={onSelectItem} />);

    await waitFor(() => {
      expect(onSelectItem).toHaveBeenCalled();
    });

    expect(onSelectItem.mock.calls[0]?.[0].previewAttachments).toEqual([
      {
        id: 'att-file-only-history',
        url: 'local-blob:att-file-only-history',
      },
    ]);
    expect(onSelectItem.mock.calls[0]?.[0].firstImage).toBe('local-blob:att-file-only-history');
  });

  it('does not persist view-created blob urls as file-only history preview urls', async () => {
    const onSelectItem = vi.fn();
    const file = new File(['file-only-view-blob-history'], 'view-blob.png', {
      type: 'image/png',
    });
    const message: Message = {
      id: 'auto-select-file-only-view-blob-history',
      role: Role.USER,
      content: 'uploaded image',
      timestamp: Date.now(),
      mode: 'image-chat-edit',
      attachments: [
        {
          id: 'att-file-only-view-blob-history',
          name: 'view-blob.png',
          mimeType: 'image/png',
          file,
        },
      ],
    };

    const HistoryWithViewBlobUrl: React.FC = () => {
      const [selectedMessageId, setSelectedMessageId] = React.useState<string | null>(null);
      const { sidebarContent } = useImageHistorySidebar({
        items: [message],
        sessionId: null,
        selectedMessageId,
        onSelectedMessageIdChange: setSelectedMessageId,
        getDisplayAttachments: (attachments?: Attachment[]) => attachments || [],
        getAttachmentUrl: () =>
          'blob:https://gemini.dicry.cn:18443/view-created-file-preview',
        extractPrompts: extractImageHistoryPrompts,
        onSelectItem,
      });

      return <>{sidebarContent}</>;
    };

    render(<HistoryWithViewBlobUrl />);

    await waitFor(() => {
      expect(onSelectItem).toHaveBeenCalled();
    });

    expect(onSelectItem.mock.calls[0]?.[0].previewAttachments).toEqual([
      {
        id: 'att-file-only-view-blob-history',
        url: 'local-blob:att-file-only-view-blob-history',
      },
    ]);
    expect(onSelectItem.mock.calls[0]?.[0].firstImage).toBe(
      'local-blob:att-file-only-view-blob-history'
    );
  });

  it('uses the durable attachment url when keyboard navigation selects another history item', async () => {
    const onSelectItem = vi.fn();
    const firstMessage: Message = {
      id: 'keyboard-history-first',
      role: Role.MODEL,
      content: 'first generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-keyboard-first',
          name: 'first.png',
          mimeType: 'image/png',
          url: 'blob:https://gemini.dicry.cn:18443/stale-keyboard-first',
          cloudUrl: '/api/storage/local-files/2026/06/01/first.png',
        },
      ],
    };
    const secondMessage: Message = {
      id: 'keyboard-history-second',
      role: Role.MODEL,
      content: 'second generated image',
      timestamp: Date.now() + 1,
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-keyboard-stale-first',
          name: 'stale-first.png',
          mimeType: 'image/png',
          url: 'blob:https://gemini.dicry.cn:18443/stale-keyboard-first',
        },
        {
          id: 'att-keyboard-second',
          name: 'second.png',
          mimeType: 'image/png',
          url: '/api/storage/local-files/2026/06/01/second.png',
        },
      ],
    };

    render(
      <HistoryHarness
        items={[firstMessage, secondMessage]}
        fallbackSelection="first"
        onSelectItem={onSelectItem}
      />
    );

    await waitFor(() => {
      expect(onSelectItem).toHaveBeenCalledTimes(1);
    });

    fireEvent.keyDown(window, { key: 'ArrowDown' });

    await waitFor(() => {
      expect(onSelectItem).toHaveBeenCalledTimes(2);
    });
    expect(onSelectItem.mock.calls[1]?.[0].firstImage).toBe(
      '/api/storage/local-files/2026/06/01/second.png'
    );
  });

  it('does not re-render visible rows when hover preview state changes', async () => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      writable: true,
      value: 1024,
    });
    const onSelectItem = vi.fn();
    const firstMessage: Message = {
      id: 'hover-row-1',
      role: Role.MODEL,
      content: 'hover row one prompt',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'hover-row-1-att',
          name: 'hover-row-1.png',
          mimeType: 'image/png',
          url: '/api/storage/local-files/2026/06/01/hover-row-1.png',
        },
      ],
    };
    const secondMessage: Message = {
      id: 'hover-row-2',
      role: Role.MODEL,
      content: 'hover row two prompt',
      timestamp: Date.now() + 1,
      mode: 'image-gen',
      attachments: [
        {
          id: 'hover-row-2-att',
          name: 'hover-row-2.png',
          mimeType: 'image/png',
          url: '/api/storage/local-files/2026/06/01/hover-row-2.png',
        },
      ],
    };

    render(
      <HistoryHarness
        items={[firstMessage, secondMessage]}
        onSelectItem={onSelectItem}
        disableFallbackSelection
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('history-row-hover-row-1')).toBeTruthy();
      expect(screen.getByTestId('history-row-hover-row-2')).toBeTruthy();
    });
    const renderCountAfterMount = rowRenderStats.count;

    fireEvent.mouseEnter(screen.getByTestId('history-row-hover-row-1'));

    await waitFor(() => {
      expect(screen.getByText('原始提示词')).toBeTruthy();
    });
    expect(rowRenderStats.count).toBe(renderCountAfterMount);

    fireEvent.click(screen.getByTestId('history-row-hover-row-2'));

    await waitFor(() => {
      expect(rowRenderStats.count).toBeGreaterThan(renderCountAfterMount);
    });
  });
});
