// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Role, type Message } from '../../../types/types';

const { mockUseCachedImageSrc } = vi.hoisted(() => ({
  mockUseCachedImageSrc: vi.fn(),
}));

vi.mock('../../../hooks/useCachedImageSrc', () => ({
  useCachedImageSrc: mockUseCachedImageSrc,
}));

import { ExpandHistoryRow } from './ExpandHistoryRow';

const message: Message = {
  id: 'msg-expand-1',
  role: Role.MODEL,
  content: 'expand',
  timestamp: Date.now(),
  attachments: [
    {
      id: 'att-expand-1',
      url: 'blob:https://gemini.dicry.cn:18443/revoked-preview',
      mimeType: 'image/png',
      name: 'expanded.png',
    },
  ],
};

describe('ExpandHistoryRow', () => {
  beforeEach(() => {
    mockUseCachedImageSrc.mockReset();
    mockUseCachedImageSrc.mockReturnValue({
      src: null,
      status: 'error',
      error: new Error('revoked blob'),
      refresh: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('does not render a raw temporary blob thumbnail when shared cache recovery fails', () => {
    render(
      <ExpandHistoryRow
        msg={message}
        firstImage={message.attachments?.[0]?.url}
        firstImageAttachment={message.attachments?.[0]}
        count={1}
        isSelected={false}
        originalPrompt="expand"
        optimizedPrompt=""
        favorited={false}
        isActionMenuOpen={false}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        showHoverPreview={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        setSelectedMsgId={vi.fn()}
        setIsMobileHistoryOpen={vi.fn()}
        closeHoverPreview={vi.fn()}
        closeActionMenu={vi.fn()}
        openActionMenuBase={vi.fn()}
      />
    );

    expect(screen.queryByAltText('Expanded image')).toBeNull();
  });

  it('renders a history thumbnail from cloudUrl when the attachment url is missing', () => {
    const durableUrl = '/api/storage/local-files/2026/05/31/expanded-result.png';
    const cloudOnlyMessage: Message = {
      ...message,
      id: 'msg-expand-cloud-only',
      attachments: [
        {
          id: 'att-expand-cloud-only',
          url: undefined,
          cloudUrl: durableUrl,
          mimeType: 'image/png',
          name: 'expanded-result.png',
        },
      ],
    };
    mockUseCachedImageSrc.mockReturnValue({
      src: durableUrl,
      status: 'persistent-hit',
      error: null,
      refresh: vi.fn(),
    });

    render(
      <ExpandHistoryRow
        msg={cloudOnlyMessage}
        firstImage={cloudOnlyMessage.attachments?.[0]?.url}
        firstImageAttachment={cloudOnlyMessage.attachments?.[0]}
        count={1}
        isSelected={false}
        originalPrompt="expand"
        optimizedPrompt=""
        favorited={false}
        isActionMenuOpen={false}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        showHoverPreview={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        setSelectedMsgId={vi.fn()}
        setIsMobileHistoryOpen={vi.fn()}
        closeHoverPreview={vi.fn()}
        closeActionMenu={vi.fn()}
        openActionMenuBase={vi.fn()}
      />
    );

    expect(screen.getByAltText('Expanded image').getAttribute('src')).toBe(durableUrl);
    expect(mockUseCachedImageSrc).toHaveBeenCalledWith(
      expect.objectContaining({
        attachmentId: 'att-expand-cloud-only',
        cloudUrl: durableUrl,
        url: durableUrl,
      }),
      expect.objectContaining({
        fallbackSrc: durableUrl,
        preferMemoryCache: true,
        replaceCachedObjectUrl: false,
      })
    );
  });

  it('passes file-only history thumbnails to CachedImage instead of dropping them', () => {
    const file = new File(['expanded-file-only'], 'expanded-file-only.png', {
      type: 'image/png',
    });
    const fileOnlyMessage: Message = {
      ...message,
      id: 'msg-expand-file-only',
      attachments: [
        {
          id: 'att-expand-file-only',
          mimeType: 'image/png',
          name: 'expanded-file-only.png',
          file,
        },
      ],
    };
    mockUseCachedImageSrc.mockReturnValue({
      src: 'blob:cached-expanded-file-only',
      status: 'memory-hit',
      error: null,
      refresh: vi.fn(),
    });

    render(
      <ExpandHistoryRow
        msg={fileOnlyMessage}
        firstImage={undefined}
        firstImageAttachment={fileOnlyMessage.attachments?.[0]}
        count={1}
        isSelected={false}
        originalPrompt="expand"
        optimizedPrompt=""
        favorited={false}
        isActionMenuOpen={false}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        showHoverPreview={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        setSelectedMsgId={vi.fn()}
        setIsMobileHistoryOpen={vi.fn()}
        closeHoverPreview={vi.fn()}
        closeActionMenu={vi.fn()}
        openActionMenuBase={vi.fn()}
      />
    );

    expect(screen.getByAltText('Expanded image').getAttribute('src')).toBe(
      'blob:cached-expanded-file-only'
    );
    expect(mockUseCachedImageSrc).toHaveBeenCalledWith(
      expect.objectContaining({
        attachmentId: 'att-expand-file-only',
        file,
        url: 'local-blob:att-expand-file-only',
      }),
      expect.objectContaining({
        fallbackSrc: 'local-blob:att-expand-file-only',
      })
    );
  });

  it('prefers cloudUrl over a stale blob url for history thumbnail fallback', () => {
    const durableUrl = '/api/storage/local-files/2026/05/31/expanded-stale-recovered.png';
    const staleBlobUrl = 'blob:https://gemini.dicry.cn:18443/revoked-preview-with-cloud';
    const recoveredMessage: Message = {
      ...message,
      id: 'msg-expand-stale-with-cloud',
      attachments: [
        {
          id: 'att-expand-stale-with-cloud',
          url: staleBlobUrl,
          cloudUrl: durableUrl,
          mimeType: 'image/png',
          name: 'expanded-stale-recovered.png',
        },
      ],
    };
    mockUseCachedImageSrc.mockReturnValue({
      src: durableUrl,
      status: 'persistent-hit',
      error: null,
      refresh: vi.fn(),
    });

    render(
      <ExpandHistoryRow
        msg={recoveredMessage}
        firstImage={recoveredMessage.attachments?.[0]?.url}
        firstImageAttachment={recoveredMessage.attachments?.[0]}
        count={1}
        isSelected={false}
        originalPrompt="expand"
        optimizedPrompt=""
        favorited={false}
        isActionMenuOpen={false}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        showHoverPreview={vi.fn()}
        scheduleHideHoverPreview={vi.fn()}
        setSelectedMsgId={vi.fn()}
        setIsMobileHistoryOpen={vi.fn()}
        closeHoverPreview={vi.fn()}
        closeActionMenu={vi.fn()}
        openActionMenuBase={vi.fn()}
      />
    );

    expect(mockUseCachedImageSrc).toHaveBeenCalledWith(
      expect.objectContaining({
        cloudUrl: durableUrl,
        url: durableUrl,
      }),
      expect.objectContaining({
        fallbackSrc: durableUrl,
      })
    );
  });

  it('rerenders when an existing attachment receives its durable cloudUrl', () => {
    const staleBlobUrl = 'blob:https://gemini.dicry.cn:18443/expand-stale-object-url';
    const durableUrl = '/api/storage/local-files/2026/05/31/expand-recovered.png';
    const mutableMessage: Message = {
      ...message,
      id: 'msg-expand-mutated-cloud',
      attachments: [
        {
          id: 'att-expand-mutated-cloud',
          url: staleBlobUrl,
          mimeType: 'image/png',
          name: 'expanded-mutated.png',
        },
      ],
    };
    const noop = vi.fn();
    mockUseCachedImageSrc.mockImplementation((source) => ({
      src: source?.url || null,
      status: 'persistent-hit',
      error: null,
      refresh: vi.fn(),
    }));

    const { rerender } = render(
      <ExpandHistoryRow
        msg={mutableMessage}
        firstImage={mutableMessage.attachments?.[0]?.url}
        firstImageAttachment={mutableMessage.attachments?.[0]}
        count={1}
        isSelected={false}
        originalPrompt="expand"
        optimizedPrompt=""
        favorited={false}
        isActionMenuOpen={false}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        showHoverPreview={noop}
        scheduleHideHoverPreview={noop}
        setSelectedMsgId={noop}
        setIsMobileHistoryOpen={noop}
        closeHoverPreview={noop}
        closeActionMenu={noop}
        openActionMenuBase={noop}
      />
    );

    expect(screen.queryByAltText('Expanded image')).toBeNull();

    mutableMessage.attachments![0].cloudUrl = durableUrl;

    rerender(
      <ExpandHistoryRow
        msg={mutableMessage}
        firstImage={mutableMessage.attachments?.[0]?.url}
        firstImageAttachment={mutableMessage.attachments?.[0]}
        count={1}
        isSelected={false}
        originalPrompt="expand"
        optimizedPrompt=""
        favorited={false}
        isActionMenuOpen={false}
        openActionMenu={null}
        historyItemRefs={{ current: {} }}
        showHoverPreview={noop}
        scheduleHideHoverPreview={noop}
        setSelectedMsgId={noop}
        setIsMobileHistoryOpen={noop}
        closeHoverPreview={noop}
        closeActionMenu={noop}
        openActionMenuBase={noop}
      />
    );

    expect(screen.getByAltText('Expanded image').getAttribute('src')).toBe(durableUrl);
  });
});
