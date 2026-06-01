// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ImageHistoryListRow } from './ImageHistoryListRow';
import {
  ACCENT_CLASSES,
  extractImageHistoryPrompts,
  resolveImageHistoryRowSourceAttachment,
} from './imageHistorySidebarHelpers';
import { Message, Role } from '../../types/types';

describe('ImageHistoryListRow model labels', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders the model label captured on the message instead of the currently selected model', () => {
    const message: Message = {
      id: 'model-message-1',
      role: Role.MODEL,
      content: 'generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      modelName: 'Model Used Then',
      modelId: 'model-used-then',
      attachments: [
        {
          id: 'att-1',
          name: 'result.png',
          mimeType: 'image/png',
          url: 'data:image/png;base64,test',
        },
      ],
    };

    render(
      <ImageHistoryListRow
        message={message}
        tone={ACCENT_CLASSES.orange}
        modelLabel="Current Selected Model"
        secondaryPromptBadgeText="含增强提示词"
        selectedMessageId={null}
        activeImageUrl={null}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        isFavorite={() => false}
        getDisplayAttachments={(attachments) => attachments || []}
        getPreviewAttachments={() => [{ id: 'att-1', url: 'data:image/png;base64,test' }]}
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

    expect(screen.getByText('Model Used Then')).toBeTruthy();
    expect(screen.queryByText('Current Selected Model')).toBeNull();
  });

  it('keeps legacy messages without model fields visible with a stable fallback label', () => {
    const message: Message = {
      id: 'legacy-model-message',
      role: Role.MODEL,
      content: 'legacy generated image',
      timestamp: Date.now(),
      mode: 'image-gen',
      attachments: [
        {
          id: 'att-legacy',
          name: 'legacy.png',
          mimeType: 'image/png',
          url: 'data:image/png;base64,legacy',
        },
      ],
    };

    render(
      <ImageHistoryListRow
        message={message}
        tone={ACCENT_CLASSES.orange}
        modelLabel="Current Selected Model"
        secondaryPromptBadgeText="含增强提示词"
        selectedMessageId={null}
        activeImageUrl={null}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        isFavorite={() => false}
        getDisplayAttachments={(attachments) => attachments || []}
        getPreviewAttachments={() => [{ id: 'att-legacy', url: 'data:image/png;base64,legacy' }]}
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

    expect(screen.getAllByText('AI').length).toBeGreaterThan(0);
    expect(screen.getByText('legacy generated image')).toBeTruthy();
    expect(screen.queryByText('Current Selected Model')).toBeNull();
  });

  it('does not attach unrelated display attachment file metadata to a preview-only result url', () => {
    const sourceFile = new File(['source-image'], 'source.png', { type: 'image/png' });
    const sourceAttachment = {
      id: 'source-att',
      name: 'source.png',
      mimeType: 'image/png',
      url: '/api/storage/local-files/source.png',
      file: sourceFile,
    };
    const previewAttachment = {
      id: 'result-att',
      url: '/api/storage/local-files/result.png',
    };

    expect(
      resolveImageHistoryRowSourceAttachment(
        [sourceAttachment],
        previewAttachment,
        previewAttachment.url
      )
    ).toBeNull();
  });

  it('does not prefer attachment id over mismatched preview url when resolving thumbnail metadata', () => {
    const staleFile = new File(['stale-source-image'], 'source.png', { type: 'image/png' });
    const attachmentWithSameId = {
      id: 'shared-att',
      name: 'source.png',
      mimeType: 'image/png',
      url: '/api/storage/local-files/source.png',
      file: staleFile,
    };
    const previewAttachment = {
      id: 'shared-att',
      url: '/api/storage/local-files/result.png',
    };

    expect(
      resolveImageHistoryRowSourceAttachment(
        [attachmentWithSameId],
        previewAttachment,
        previewAttachment.url
      )
    ).toBeNull();
  });
});
