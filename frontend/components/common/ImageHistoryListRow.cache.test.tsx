// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CachedImageProps } from './CachedImage';
import { ImageHistoryListRow } from './ImageHistoryListRow';
import { ACCENT_CLASSES, extractImageHistoryPrompts } from './imageHistorySidebarHelpers';
import { Attachment, Message, Role } from '../../types/types';

const cachedImageSpy = vi.fn();

vi.mock('./CachedImage', () => ({
  CachedImage: (props: CachedImageProps) => {
    cachedImageSpy(props);
    return <img alt={props.alt || ''} src={props.src || ''} />;
  },
}));

describe('ImageHistoryListRow cache-safe thumbnails', () => {
  beforeEach(() => {
    cachedImageSpy.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders history thumbnails from durable attachment urls instead of stale blob urls', () => {
    const message: Message = {
      id: 'history-row-cache',
      role: Role.MODEL,
      content: 'generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-1',
          name: 'result.png',
          mimeType: 'image/png',
          url: 'blob:https://gemini.dicry.cn:18443/stale-row-preview',
          cloudUrl: '/api/storage/local-files/2026/05/31/result.png',
        },
      ],
    };

    render(
      <ImageHistoryListRow
        message={message}
        tone={ACCENT_CLASSES.orange}
        modelLabel="AI"
        secondaryPromptBadgeText="含增强提示词"
        selectedMessageId={null}
        activeImageUrl={null}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        isFavorite={() => false}
        getDisplayAttachments={(attachments) => attachments || []}
        getPreviewAttachments={() => [
          { id: 'att-1', url: 'blob:https://gemini.dicry.cn:18443/stale-row-preview' },
        ]}
        extractPrompts={extractImageHistoryPrompts}
        showHoverPreview={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        closeHoverPreviewOnly={vi.fn()}
        closeHoverPreview={vi.fn()}
        onSelectItem={vi.fn()}
        setOpenActionMenu={vi.fn()}
        setActionMenuPosition={vi.fn()}
      />
    );

    const thumbnailProps = cachedImageSpy.mock.calls[0]?.[0] as CachedImageProps;
    expect(thumbnailProps.src).toBe('/api/storage/local-files/2026/05/31/result.png');
    expect(thumbnailProps.loading).toBeUndefined();
  });

  it('reuses shared media cache object urls for durable history thumbnails while keeping delayed raw fallback', () => {
    const message: Message = {
      id: 'history-row-immediate-fallback',
      role: Role.MODEL,
      content: 'generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-immediate',
          name: 'immediate.png',
          mimeType: 'image/png',
          url: '/api/storage/local-files/2026/05/31/immediate.png',
        },
      ],
    };

    render(
      <ImageHistoryListRow
        message={message}
        tone={ACCENT_CLASSES.orange}
        modelLabel="AI"
        secondaryPromptBadgeText="含增强提示词"
        selectedMessageId={null}
        activeImageUrl={null}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        isFavorite={() => false}
        getDisplayAttachments={(attachments) => attachments || []}
        getPreviewAttachments={() => [
          { id: 'att-immediate', url: '/api/storage/local-files/2026/05/31/immediate.png' },
        ]}
        extractPrompts={extractImageHistoryPrompts}
        showHoverPreview={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        closeHoverPreviewOnly={vi.fn()}
        closeHoverPreview={vi.fn()}
        onSelectItem={vi.fn()}
        setOpenActionMenu={vi.fn()}
        setActionMenuPosition={vi.fn()}
      />
    );

    expect((cachedImageSpy.mock.calls.at(-1)?.[0] as CachedImageProps).rawFallbackDelayMs).toBe(
      300
    );
    expect(
      (cachedImageSpy.mock.calls.at(-1)?.[0] as CachedImageProps).preferMemoryCache
    ).toBe(true);
    expect(
      (cachedImageSpy.mock.calls.at(-1)?.[0] as CachedImageProps).replaceCachedObjectUrl
    ).toBe(false);
  });

  it('refreshes the thumbnail when an existing message attachment receives its durable url', () => {
    const message: Message = {
      id: 'history-row-mutated-cache',
      role: Role.MODEL,
      content: 'generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-mutated',
          name: 'mutated.png',
          mimeType: 'image/png',
          url: 'blob:https://gemini.dicry.cn:18443/stale-mutated-preview',
        },
      ],
    };
    const historyItemRefs = { current: {} };
    const noop = vi.fn();
    const getDisplayAttachments = (attachments?: Message['attachments']) => attachments || [];
    const getPreviewAttachments = () => [
      { id: 'att-mutated', url: 'blob:https://gemini.dicry.cn:18443/stale-mutated-preview' },
    ];
    const isFavorite = () => false;

    const { rerender } = render(
      <ImageHistoryListRow
        message={message}
        tone={ACCENT_CLASSES.orange}
        modelLabel="AI"
        secondaryPromptBadgeText="含增强提示词"
        selectedMessageId={null}
        activeImageUrl={null}
        openActionMenu={null}
        historyItemRefs={historyItemRefs}
        isFavorite={isFavorite}
        getDisplayAttachments={getDisplayAttachments}
        getPreviewAttachments={getPreviewAttachments}
        extractPrompts={extractImageHistoryPrompts}
        showHoverPreview={noop}
        scheduleHideHoverPreview={noop}
        closeHoverPreviewOnly={noop}
        closeHoverPreview={noop}
        onSelectItem={noop}
        setOpenActionMenu={noop}
        setActionMenuPosition={noop}
      />
    );

    expect(cachedImageSpy).not.toHaveBeenCalled();

    const updatedMessage: Message = {
      ...message,
      attachments: [
        {
          ...message.attachments![0],
          cloudUrl: '/api/storage/local-files/2026/05/31/mutated.png',
        },
      ],
    };

    rerender(
      <ImageHistoryListRow
        message={updatedMessage}
        tone={ACCENT_CLASSES.orange}
        modelLabel="AI"
        secondaryPromptBadgeText="含增强提示词"
        selectedMessageId={null}
        activeImageUrl={null}
        openActionMenu={null}
        historyItemRefs={historyItemRefs}
        isFavorite={isFavorite}
        getDisplayAttachments={getDisplayAttachments}
        getPreviewAttachments={getPreviewAttachments}
        extractPrompts={extractImageHistoryPrompts}
        showHoverPreview={noop}
        scheduleHideHoverPreview={noop}
        closeHoverPreviewOnly={noop}
        closeHoverPreview={noop}
        onSelectItem={noop}
        setOpenActionMenu={noop}
        setActionMenuPosition={noop}
      />
    );

    expect((cachedImageSpy.mock.calls.at(-1)?.[0] as CachedImageProps).src).toBe(
      '/api/storage/local-files/2026/05/31/mutated.png'
    );
  });

  it('matches preview attachments by id before falling back to a stale preview url', () => {
    const message: Message = {
      id: 'history-row-id-match',
      role: Role.MODEL,
      content: 'generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-id-match',
          name: 'id-match.png',
          mimeType: 'image/png',
          url: '/api/storage/local-files/2026/05/31/id-match.png',
        },
      ],
    };

    render(
      <ImageHistoryListRow
        message={message}
        tone={ACCENT_CLASSES.orange}
        modelLabel="AI"
        secondaryPromptBadgeText="含增强提示词"
        selectedMessageId={null}
        activeImageUrl={null}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        isFavorite={() => false}
        getDisplayAttachments={(attachments) => attachments || []}
        getPreviewAttachments={() => [
          { id: 'att-id-match', url: 'blob:https://gemini.dicry.cn:18443/stale-id-preview' },
        ]}
        extractPrompts={extractImageHistoryPrompts}
        showHoverPreview={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        closeHoverPreviewOnly={vi.fn()}
        closeHoverPreview={vi.fn()}
        onSelectItem={vi.fn()}
        setOpenActionMenu={vi.fn()}
        setActionMenuPosition={vi.fn()}
      />
    );

    expect((cachedImageSpy.mock.calls.at(-1)?.[0] as CachedImageProps).src).toBe(
      '/api/storage/local-files/2026/05/31/id-match.png'
    );
  });

  it('renders history thumbnails from snake_case durable urls returned by history APIs', () => {
    const message: Message = {
      id: 'history-row-snake-case-cache',
      role: Role.MODEL,
      content: 'generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-snake-case',
          name: 'snake.png',
          mimeType: 'image/png',
          url: 'blob:https://gemini.dicry.cn:18443/stale-snake-preview',
          cloud_url: '/api/storage/local-files/2026/05/31/snake.png',
        } as unknown as Attachment,
      ],
    };

    render(
      <ImageHistoryListRow
        message={message}
        tone={ACCENT_CLASSES.orange}
        modelLabel="AI"
        secondaryPromptBadgeText="含增强提示词"
        selectedMessageId={null}
        activeImageUrl={null}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        isFavorite={() => false}
        getDisplayAttachments={(attachments) => attachments || []}
        getPreviewAttachments={() => [
          { id: 'att-snake-case', url: 'blob:https://gemini.dicry.cn:18443/stale-snake-preview' },
        ]}
        extractPrompts={extractImageHistoryPrompts}
        showHoverPreview={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        closeHoverPreviewOnly={vi.fn()}
        closeHoverPreview={vi.fn()}
        onSelectItem={vi.fn()}
        setOpenActionMenu={vi.fn()}
        setActionMenuPosition={vi.fn()}
      />
    );

    expect((cachedImageSpy.mock.calls.at(-1)?.[0] as CachedImageProps).src).toBe(
      '/api/storage/local-files/2026/05/31/snake.png'
    );
  });

  it('uses a later durable preview when the first preview is a stale blob-only attachment', () => {
    const onSelectItem = vi.fn();
    const message: Message = {
      id: 'history-row-first-stale-second-good',
      role: Role.MODEL,
      content: 'generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-stale-first',
          name: 'stale-first.png',
          mimeType: 'image/png',
          url: 'blob:https://gemini.dicry.cn:18443/stale-first-preview',
        },
        {
          id: 'att-durable-second',
          name: 'durable-second.png',
          mimeType: 'image/png',
          url: '/api/storage/local-files/2026/05/31/durable-second.png',
        },
      ],
    };

    render(
      <ImageHistoryListRow
        message={message}
        tone={ACCENT_CLASSES.orange}
        modelLabel="AI"
        secondaryPromptBadgeText="含增强提示词"
        selectedMessageId={null}
        activeImageUrl={null}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        isFavorite={() => false}
        getDisplayAttachments={(attachments) => attachments || []}
        getPreviewAttachments={() => [
          { id: 'att-stale-first', url: 'blob:https://gemini.dicry.cn:18443/stale-first-preview' },
          { id: 'att-durable-second', url: '/api/storage/local-files/2026/05/31/durable-second.png' },
        ]}
        extractPrompts={extractImageHistoryPrompts}
        showHoverPreview={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        closeHoverPreviewOnly={vi.fn()}
        closeHoverPreview={vi.fn()}
        onSelectItem={onSelectItem}
        setOpenActionMenu={vi.fn()}
        setActionMenuPosition={vi.fn()}
      />
    );

    expect((cachedImageSpy.mock.calls.at(-1)?.[0] as CachedImageProps).src).toBe(
      '/api/storage/local-files/2026/05/31/durable-second.png'
    );

    fireEvent.click(screen.getByAltText('History preview').closest('.cursor-pointer')!);

    expect(onSelectItem.mock.calls[0]?.[0].firstImage).toBe(
      '/api/storage/local-files/2026/05/31/durable-second.png'
    );
  });

  it('matches snake_case durable urls by attachment id when the preview url is stale but non-temporary', () => {
    const message: Message = {
      id: 'history-row-snake-case-id-stale-stable-url',
      role: Role.MODEL,
      content: 'generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-snake-id-stable',
          name: 'snake-id-stable.png',
          mimeType: 'image/png',
          url: '/api/storage/local-files/2026/05/31/old-snake-id-stable.png',
          cloud_url: '/api/storage/local-files/2026/05/31/new-snake-id-stable.png',
        } as unknown as Attachment,
      ],
    };

    render(
      <ImageHistoryListRow
        message={message}
        tone={ACCENT_CLASSES.orange}
        modelLabel="AI"
        secondaryPromptBadgeText="含增强提示词"
        selectedMessageId={null}
        activeImageUrl={null}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        isFavorite={() => false}
        getDisplayAttachments={(attachments) => attachments || []}
        getPreviewAttachments={() => [
          {
            id: 'att-snake-id-stable',
            url: '/api/storage/local-files/2026/05/31/stale-preview-url.png',
          },
        ]}
        extractPrompts={extractImageHistoryPrompts}
        showHoverPreview={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        closeHoverPreviewOnly={vi.fn()}
        closeHoverPreview={vi.fn()}
        onSelectItem={vi.fn()}
        setOpenActionMenu={vi.fn()}
        setActionMenuPosition={vi.fn()}
      />
    );

    expect((cachedImageSpy.mock.calls.at(-1)?.[0] as CachedImageProps).src).toBe(
      '/api/storage/local-files/2026/05/31/new-snake-id-stable.png'
    );
  });

  it('keeps the original file source for file-only local-blob history thumbnails', () => {
    const file = new File(['file-only-row'], 'file-only-row.png', { type: 'image/png' });
    const message: Message = {
      id: 'history-row-file-only-local-blob',
      role: Role.USER,
      content: 'uploaded image',
      timestamp: Date.now(),
      mode: 'image-chat-edit',
      attachments: [
        {
          id: 'att-file-only-row',
          name: 'file-only-row.png',
          mimeType: 'image/png',
          file,
        },
      ],
    };

    render(
      <ImageHistoryListRow
        message={message}
        tone={ACCENT_CLASSES.orange}
        modelLabel="AI"
        secondaryPromptBadgeText="含增强提示词"
        selectedMessageId={null}
        activeImageUrl={null}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        isFavorite={() => false}
        getDisplayAttachments={(attachments) => attachments || []}
        getPreviewAttachments={() => [
          { id: 'att-file-only-row', url: 'local-blob:att-file-only-row' },
        ]}
        extractPrompts={extractImageHistoryPrompts}
        showHoverPreview={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        closeHoverPreviewOnly={vi.fn()}
        closeHoverPreview={vi.fn()}
        onSelectItem={vi.fn()}
        setOpenActionMenu={vi.fn()}
        setActionMenuPosition={vi.fn()}
      />
    );

    const thumbnailProps = cachedImageSpy.mock.calls.at(-1)?.[0] as CachedImageProps;
    expect(thumbnailProps.src).toBe('local-blob:att-file-only-row');
    expect(thumbnailProps.source).toMatchObject({
      attachmentId: 'att-file-only-row',
      file,
      mimeType: 'image/png',
      name: 'file-only-row.png',
    });
  });

  it('normalizes file-backed stale blob previews to internal local-blob thumbnails', () => {
    const file = new File(['file-backed-stale-row'], 'file-backed-stale-row.png', {
      type: 'image/png',
    });
    const message: Message = {
      id: 'history-row-file-backed-stale-blob',
      role: Role.USER,
      content: 'uploaded image',
      timestamp: Date.now(),
      mode: 'image-chat-edit',
      attachments: [
        {
          id: 'att-file-backed-stale-row',
          name: 'file-backed-stale-row.png',
          mimeType: 'image/png',
          file,
          url: 'blob:https://gemini.dicry.cn:18443/file-backed-stale-row',
        },
      ],
    };

    render(
      <ImageHistoryListRow
        message={message}
        tone={ACCENT_CLASSES.orange}
        modelLabel="AI"
        secondaryPromptBadgeText="含增强提示词"
        selectedMessageId={null}
        activeImageUrl={null}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        isFavorite={() => false}
        getDisplayAttachments={(attachments) => attachments || []}
        getPreviewAttachments={() => [
          {
            id: 'att-file-backed-stale-row',
            url: 'blob:https://gemini.dicry.cn:18443/file-backed-stale-row',
          },
        ]}
        extractPrompts={extractImageHistoryPrompts}
        showHoverPreview={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        closeHoverPreviewOnly={vi.fn()}
        closeHoverPreview={vi.fn()}
        onSelectItem={vi.fn()}
        setOpenActionMenu={vi.fn()}
        setActionMenuPosition={vi.fn()}
      />
    );

    const thumbnailProps = cachedImageSpy.mock.calls.at(-1)?.[0] as CachedImageProps;
    expect(thumbnailProps.src).toBe('local-blob:att-file-backed-stale-row');
    expect(thumbnailProps.source).toMatchObject({
      attachmentId: 'att-file-backed-stale-row',
      file,
    });
  });
});
