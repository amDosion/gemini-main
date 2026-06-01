// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CachedImageProps } from './CachedImage';
import { ImageHistoryHoverPreviewPanel } from './ImageHistoryHoverPreviewPanel';
import { ACCENT_CLASSES } from './imageHistorySidebarHelpers';
import { Attachment, Message, Role } from '../../types/types';

const cachedImageSpy = vi.fn();

vi.mock('./CachedImage', () => ({
  CachedImage: (props: CachedImageProps) => {
    cachedImageSpy(props);
    return <img alt={props.alt || ''} src={props.src || ''} />;
  },
}));

describe('ImageHistoryHoverPreviewPanel cache-safe attachments', () => {
  beforeEach(() => {
    cachedImageSpy.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders hover attachments from the same durable urls as the history row', () => {
    const message: Message = {
      id: 'hover-cache-message',
      role: Role.MODEL,
      content: 'generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-hover',
          name: 'hover.png',
          mimeType: 'image/png',
          url: 'blob:https://gemini.dicry.cn:18443/stale-hover-preview',
          cloudUrl: '/api/storage/local-files/2026/05/31/hover.png',
        },
      ],
    };

    render(
      <ImageHistoryHoverPreviewPanel
        hoverPreview={{
          messageId: message.id,
          role: Role.MODEL,
          authorLabel: 'AI',
          anchorX: 120,
          anchorY: 80,
          originalPrompt: 'prompt',
          enhancedPrompt: '',
          attachments: [
            {
              id: 'att-hover',
              url: 'blob:https://gemini.dicry.cn:18443/stale-hover-preview',
            },
          ],
        }}
        hoverPreviewPosition={{ top: 0, left: 0, arrowOffsetY: 12 }}
        hoverPreviewSize={null}
        hoverPreviewPanelRef={{ current: null }}
        clearHidePreviewTimer={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        tone={ACCENT_CLASSES.orange}
        secondaryPromptLabel="增强提示词"
        secondaryPromptMissingText="未返回增强提示词"
        secondaryPromptCopyTitle="复制增强提示词"
        copiedPreviewMessageId={null}
        handleCopyEnhancedPrompt={vi.fn()}
        activeImageUrl={null}
        items={[message]}
        onSelectedMessageIdChange={vi.fn()}
        getDisplayAttachments={(attachments) => attachments || []}
        onSelectItem={vi.fn()}
        handlePreviewResizeMouseDown={vi.fn()}
        isResizingPreview={false}
      />
    );

    const previewProps = cachedImageSpy.mock.calls[0]?.[0] as CachedImageProps;
    expect(previewProps.src).toBe('/api/storage/local-files/2026/05/31/hover.png');
    expect(previewProps.preferMemoryCache).toBe(true);
    expect(previewProps.replaceCachedObjectUrl).toBe(false);
  });

  it('uses the current durable attachment url when hover state contains an old stable preview url', () => {
    const onSelectPreviewAttachment = vi.fn();
    const durableUrl = '/api/storage/local-files/2026/05/31/hover-current.png';
    const message: Message = {
      id: 'hover-stale-stable-message',
      role: Role.MODEL,
      content: 'generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-hover-stale-stable',
          name: 'hover-current.png',
          mimeType: 'image/png',
          url: '/api/storage/local-files/2026/05/31/hover-old.png',
          cloud_url: durableUrl,
        } as unknown as Attachment,
      ],
    };

    render(
      <ImageHistoryHoverPreviewPanel
        hoverPreview={{
          messageId: message.id,
          role: Role.MODEL,
          authorLabel: 'AI',
          anchorX: 120,
          anchorY: 80,
          originalPrompt: 'prompt',
          enhancedPrompt: '',
          attachments: [
            {
              id: 'att-hover-stale-stable',
              url: '/api/storage/local-files/2026/05/31/hover-preview-stale.png',
            },
          ],
        }}
        hoverPreviewPosition={{ top: 0, left: 0, arrowOffsetY: 12 }}
        hoverPreviewSize={null}
        hoverPreviewPanelRef={{ current: null }}
        clearHidePreviewTimer={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        tone={ACCENT_CLASSES.orange}
        secondaryPromptLabel="增强提示词"
        secondaryPromptMissingText="未返回增强提示词"
        secondaryPromptCopyTitle="复制增强提示词"
        copiedPreviewMessageId={null}
        handleCopyEnhancedPrompt={vi.fn()}
        activeImageUrl={null}
        items={[message]}
        onSelectedMessageIdChange={vi.fn()}
        getDisplayAttachments={(attachments) => attachments || []}
        onSelectPreviewAttachment={onSelectPreviewAttachment}
        onSelectItem={vi.fn()}
        handlePreviewResizeMouseDown={vi.fn()}
        isResizingPreview={false}
      />
    );

    const previewProps = cachedImageSpy.mock.calls[0]?.[0] as CachedImageProps;
    expect(previewProps.src).toBe(durableUrl);
    expect(previewProps.source).toMatchObject({
      attachmentId: 'att-hover-stale-stable',
      url: durableUrl,
    });

    fireEvent.click(screen.getByTitle('在画布中查看该图片'));

    expect(onSelectPreviewAttachment.mock.calls[0]?.[0].attachment.url).toBe(durableUrl);
  });

  it('keeps the original file source for file-only local-blob hover attachments', () => {
    const file = new File(['file-only-hover'], 'file-only-hover.png', { type: 'image/png' });
    const message: Message = {
      id: 'hover-file-only-local-blob',
      role: Role.USER,
      content: 'uploaded image',
      timestamp: Date.now(),
      mode: 'image-chat-edit',
      attachments: [
        {
          id: 'att-file-only-hover',
          name: 'file-only-hover.png',
          mimeType: 'image/png',
          file,
        },
      ],
    };

    render(
      <ImageHistoryHoverPreviewPanel
        hoverPreview={{
          messageId: message.id,
          role: Role.USER,
          authorLabel: 'You',
          anchorX: 120,
          anchorY: 80,
          originalPrompt: 'prompt',
          enhancedPrompt: '',
          attachments: [
            {
              id: 'att-file-only-hover',
              url: 'local-blob:att-file-only-hover',
            },
          ],
        }}
        hoverPreviewPosition={{ top: 0, left: 0, arrowOffsetY: 12 }}
        hoverPreviewSize={null}
        hoverPreviewPanelRef={{ current: null }}
        clearHidePreviewTimer={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        tone={ACCENT_CLASSES.orange}
        secondaryPromptLabel="增强提示词"
        secondaryPromptMissingText="未返回增强提示词"
        secondaryPromptCopyTitle="复制增强提示词"
        copiedPreviewMessageId={null}
        handleCopyEnhancedPrompt={vi.fn()}
        activeImageUrl={null}
        items={[message]}
        onSelectedMessageIdChange={vi.fn()}
        getDisplayAttachments={(attachments) => attachments || []}
        onSelectItem={vi.fn()}
        handlePreviewResizeMouseDown={vi.fn()}
        isResizingPreview={false}
      />
    );

    const previewProps = cachedImageSpy.mock.calls[0]?.[0] as CachedImageProps;
    expect(previewProps.src).toBe('local-blob:att-file-only-hover');
    expect(previewProps.source).toMatchObject({
      attachmentId: 'att-file-only-hover',
      file,
      mimeType: 'image/png',
      name: 'file-only-hover.png',
    });
  });

  it('normalizes file-backed stale blob hover previews to internal local-blob urls', () => {
    const file = new File(['file-backed-stale-hover'], 'file-backed-stale-hover.png', {
      type: 'image/png',
    });
    const message: Message = {
      id: 'hover-file-backed-stale-blob',
      role: Role.USER,
      content: 'uploaded image',
      timestamp: Date.now(),
      mode: 'image-chat-edit',
      attachments: [
        {
          id: 'att-file-backed-stale-hover',
          name: 'file-backed-stale-hover.png',
          mimeType: 'image/png',
          file,
          url: 'blob:https://gemini.dicry.cn:18443/file-backed-stale-hover',
        },
      ],
    };

    render(
      <ImageHistoryHoverPreviewPanel
        hoverPreview={{
          messageId: message.id,
          role: Role.USER,
          authorLabel: 'You',
          anchorX: 120,
          anchorY: 80,
          originalPrompt: 'prompt',
          enhancedPrompt: '',
          attachments: [
            {
              id: 'att-file-backed-stale-hover',
              url: 'blob:https://gemini.dicry.cn:18443/file-backed-stale-hover',
            },
          ],
        }}
        hoverPreviewPosition={{ top: 0, left: 0, arrowOffsetY: 12 }}
        hoverPreviewSize={null}
        hoverPreviewPanelRef={{ current: null }}
        clearHidePreviewTimer={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        tone={ACCENT_CLASSES.orange}
        secondaryPromptLabel="增强提示词"
        secondaryPromptMissingText="未返回增强提示词"
        secondaryPromptCopyTitle="复制增强提示词"
        copiedPreviewMessageId={null}
        handleCopyEnhancedPrompt={vi.fn()}
        activeImageUrl={null}
        items={[message]}
        onSelectedMessageIdChange={vi.fn()}
        getDisplayAttachments={(attachments) => attachments || []}
        onSelectItem={vi.fn()}
        handlePreviewResizeMouseDown={vi.fn()}
        isResizingPreview={false}
      />
    );

    const previewProps = cachedImageSpy.mock.calls[0]?.[0] as CachedImageProps;
    expect(previewProps.src).toBe('local-blob:att-file-backed-stale-hover');
    expect(previewProps.source).toMatchObject({
      attachmentId: 'att-file-backed-stale-hover',
      file,
    });
  });
});
