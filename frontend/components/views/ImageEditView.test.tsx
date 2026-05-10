// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../contexts/ToastContext';
import { ImageEditView } from './ImageEditView';
import { Role, type Attachment, type Message } from '../../types/types';

vi.mock('../../coordinators/ModeControlsCoordinator', () => ({
  ModeControlsCoordinator: () => <div data-testid="mode-controls" />,
}));

vi.mock('../chat/ChatEditInputArea', () => ({
  default: () => <div data-testid="chat-edit-input" />,
}));

vi.mock('../common/GenViewLayout', () => ({
  GenViewLayout: ({ sidebar, main }: { sidebar: React.ReactNode; main: React.ReactNode }) => (
    <div>
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

const renderImageEditView = (messages: Message[]) => render(
  <ToastProvider>
    <ImageEditView
      messages={messages}
      setAppMode={vi.fn()}
      onImageClick={vi.fn()}
      loadingState="idle"
      onSend={vi.fn()}
      onStop={vi.fn()}
      activeModelConfig={{
        id: 'gemini-3.1-flash-image-preview',
        name: 'Gemini Image',
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

describe('ImageEditView', () => {
  beforeEach(() => {
    Element.prototype.scrollTo = vi.fn();
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
  });

  it('reuses carousel controls for multi-image chat-edit model results', async () => {
    const messages: Message[] = [
      {
        id: 'user-1',
        role: Role.USER,
        content: 'make product variants',
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

    renderImageEditView(messages);

    await waitFor(() => {
      expect(screen.getByText('1 / 3')).toBeInTheDocument();
    });

    expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', '/result-1.png');

    fireEvent.click(screen.getByTitle('切换到第 2 张'));

    await waitFor(() => {
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', '/result-2.png');
    });
  });

  it('compares a selected AI result with the preceding user-uploaded image', async () => {
    const messages: Message[] = [
      {
        id: 'user-1',
        role: Role.USER,
        content: 'source one',
        timestamp: 1,
        attachments: [makeAttachment('source-1', '/source-1.png')],
      },
      {
        id: 'model-1',
        role: Role.MODEL,
        content: 'done first',
        timestamp: 2,
        attachments: [makeAttachment('result-1', '/result-1.png')],
      },
      {
        id: 'user-2',
        role: Role.USER,
        content: 'source two',
        timestamp: 3,
        attachments: [makeAttachment('source-2', '/source-2.png')],
      },
      {
        id: 'model-2',
        role: Role.MODEL,
        content: 'done second',
        timestamp: 4,
        attachments: [makeAttachment('result-2', '/result-2.png')],
      },
    ];

    renderImageEditView(messages);

    fireEvent.click(screen.getByText('done first'));

    await waitFor(() => {
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', '/result-1.png');
    });

    fireEvent.click(screen.getByTitle('对比原图'));

    await waitFor(() => {
      expect(screen.getByAltText('原图')).toHaveAttribute('src', '/source-1.png');
    });
    expect(screen.getByAltText('编辑结果')).toHaveAttribute('src', '/result-1.png');
  });

  it('hides compare mode when the selected history item is the user source image', async () => {
    const messages: Message[] = [
      {
        id: 'user-1',
        role: Role.USER,
        content: 'source prompt',
        timestamp: 1,
        attachments: [makeAttachment('source', '/source.png')],
      },
      {
        id: 'model-1',
        role: Role.MODEL,
        content: 'done',
        timestamp: 2,
        attachments: [makeAttachment('result', '/result.png')],
      },
    ];

    renderImageEditView(messages);

    await waitFor(() => {
      expect(screen.getByTitle('对比原图')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('source prompt'));

    await waitFor(() => {
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', '/source.png');
    });
    expect(screen.queryByTitle('对比原图')).not.toBeInTheDocument();
  });

  it('hides the prompt preview while hovering the history action button', async () => {
    const messages: Message[] = [
      {
        id: 'user-1',
        role: Role.USER,
        content: 'source prompt',
        timestamp: 1,
        attachments: [makeAttachment('source', '/source.png')],
      },
      {
        id: 'model-1',
        role: Role.MODEL,
        content: '📝 original edit prompt\n✨ optimized edit prompt',
        timestamp: 2,
        attachments: [makeAttachment('result', '/result.png')],
      },
    ];

    renderImageEditView(messages);

    const historyItem = screen.getByText('original edit prompt').closest('[class*="cursor-pointer"]');
    expect(historyItem).toBeInTheDocument();

    fireEvent.mouseEnter(historyItem!);

    await waitFor(() => {
      expect(screen.getByText('原始提示词')).toBeInTheDocument();
      expect(screen.getByText('optimized edit prompt')).toBeInTheDocument();
    });

    const actionButton = document.querySelector('[data-history-action-trigger="model-1"]') as HTMLElement | null;
    expect(actionButton).toBeInTheDocument();
    fireEvent.mouseEnter(actionButton!);

    await waitFor(() => {
      expect(screen.queryByText('原始提示词')).not.toBeInTheDocument();
      expect(screen.queryByText('optimized edit prompt')).not.toBeInTheDocument();
    });
  });
});
