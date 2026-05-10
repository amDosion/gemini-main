// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../contexts/ToastContext';
import { ImageRecontextView } from './ImageRecontextView';
import { Role, type Attachment, type Message } from '../../types/types';

vi.mock('../../coordinators/ModeControlsCoordinator', () => ({
  ModeControlsCoordinator: () => <div data-testid="mode-controls" />,
}));

vi.mock('../chat/ChatEditInputArea', () => ({
  default: () => <div data-testid="chat-edit-input" />,
}));

vi.mock('../common/GenViewLayout', () => ({
  GenViewLayout: ({
    sidebar,
    sidebarExtraHeader,
    main,
  }: {
    sidebar: React.ReactNode;
    sidebarExtraHeader?: React.ReactNode;
    main: React.ReactNode;
  }) => (
    <div>
      <div data-testid="sidebar-extra-header">{sidebarExtraHeader}</div>
      <aside>{sidebar}</aside>
      <main>{main}</main>
    </div>
  ),
}));

vi.mock('../../hooks/useHistoryListActions', () => ({
  useHistoryListActions: ({ items }: { items: Message[] }) => ({
    showFavoritesOnly: false,
    setShowFavoritesOnly: vi.fn(),
    filteredItems: items,
    favoriteCount: 0,
    isFavorite: vi.fn(() => false),
    isFavoritePending: vi.fn(() => false),
    toggleFavorite: vi.fn(),
    deleteItem: vi.fn(),
  }),
}));

const makeAttachment = (id: string, url: string): Attachment => ({
  id,
  name: `${id}.png`,
  mimeType: 'image/png',
  url,
  uploadStatus: 'completed',
});

const renderImageRecontextView = (messages: Message[]) => render(
  <ToastProvider>
    <ImageRecontextView
      messages={messages}
      setAppMode={vi.fn()}
      onImageClick={vi.fn()}
      loadingState="idle"
      onSend={vi.fn()}
      onStop={vi.fn()}
      activeModelConfig={{
        id: 'gemini-2.5-flash-image',
        name: 'Gemini 2.5 Flash Image',
        description: '',
        capabilities: {
          vision: true,
          search: false,
          reasoning: true,
          coding: false,
        },
      }}
      sessionId="session-1"
    />
  </ToastProvider>,
);

describe('ImageRecontextView', () => {
  beforeEach(() => {
    Element.prototype.scrollTo = vi.fn();
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
  });

  it('reuses carousel controls for multi-image recontext results', async () => {
    const messages: Message[] = [
      {
        id: 'user-1',
        role: Role.USER,
        content: 'put this product in summer scenes',
        timestamp: 1,
        attachments: [makeAttachment('source', '/source.png')],
      },
      {
        id: 'model-1',
        role: Role.MODEL,
        content: 'done',
        timestamp: 2,
        attachments: [
          makeAttachment('result-1', '/result-1.png'),
          makeAttachment('result-2', '/result-2.png'),
          makeAttachment('result-3', '/result-3.png'),
        ],
      },
    ];

    renderImageRecontextView(messages);

    await waitFor(() => {
      expect(screen.getByText('1 / 3')).toBeInTheDocument();
    });

    expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', '/result-1.png');

    fireEvent.click(screen.getByTitle('切换到第 2 张'));

    await waitFor(() => {
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', '/result-2.png');
    });
  });

  it('uses the compact edit-style history list with prompt preview and action menu', async () => {
    const messages: Message[] = [
      {
        id: 'user-1',
        role: Role.USER,
        content: 'source product photo',
        timestamp: 1,
        attachments: [makeAttachment('source', '/source.png')],
      },
      {
        id: 'model-1',
        role: Role.MODEL,
        content: '📝 put product in a premium boutique window\n✨ premium boutique window product recontext prompt',
        timestamp: 2,
        attachments: [makeAttachment('result', '/result.png')],
      },
    ];

    renderImageRecontextView(messages);

    expect(screen.getByText('仅收藏')).toBeInTheDocument();
    expect(screen.getByText('2/2')).toBeInTheDocument();
    expect(screen.getByText('用户输入')).toBeInTheDocument();
    expect(screen.getByText('AI 响应')).toBeInTheDocument();

    const actionButton = document.querySelector('[data-history-action-trigger="model-1"]');
    expect(actionButton).toBeInTheDocument();

    const historyItem = screen.getByText('put product in a premium boutique window').closest('[class*="cursor-pointer"]');
    expect(historyItem).toBeInTheDocument();

    fireEvent.mouseEnter(historyItem!);

    await waitFor(() => {
      expect(screen.getByText('原始提示词')).toBeInTheDocument();
      expect(screen.getByText('premium boutique window product recontext prompt')).toBeInTheDocument();
    });

    expect(screen.getByLabelText('拖动调整提示词预览大小')).toBeInTheDocument();
  });

});
