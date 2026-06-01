// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useImageHistorySidebar } from './ImageHistorySidebar';
import { extractImageHistoryPrompts } from './imageHistorySidebarHelpers';
import type { Attachment, Message } from '../../types/types';
import { Role } from '../../types/types';

const HistoryHarness: React.FC<{
  items: Message[];
  onSelectItem: Parameters<typeof useImageHistorySidebar>[0]['onSelectItem'];
  fallbackSelection?: 'first' | 'last';
}> = ({ items, onSelectItem, fallbackSelection }) => {
  const [selectedMessageId, setSelectedMessageId] = React.useState<string | null>(null);
  const { sidebarContent } = useImageHistorySidebar({
    items,
    sessionId: null,
    selectedMessageId,
    onSelectedMessageIdChange: setSelectedMessageId,
    fallbackSelection,
    getDisplayAttachments: (attachments?: Attachment[]) => attachments || [],
    getAttachmentUrl: (attachment) => attachment.url || null,
    extractPrompts: extractImageHistoryPrompts,
    onSelectItem,
  });

  return <>{sidebarContent}</>;
};

describe('useImageHistorySidebar cache-safe selection', () => {
  afterEach(() => {
    cleanup();
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
});
