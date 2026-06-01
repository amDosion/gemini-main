// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../contexts/ToastContext';
import { ImageEditView } from './ImageEditView';
import { Role, type Attachment, type Message } from '../../types/types';

const modeControlsCoordinatorMock = vi.hoisted(() => vi.fn());

vi.mock('../../coordinators/ModeControlsCoordinator', () => ({
  ModeControlsCoordinator: (props: {
    availableModels?: Array<{ id: string }>;
    providerId?: string;
  }) => {
    modeControlsCoordinatorMock(props);
    return (
      <div
        data-testid="mode-controls"
        data-provider-id={props.providerId}
        data-model-ids={(props.availableModels || []).map((model) => model.id).join(',')}
      />
    );
  },
}));

vi.mock('../../hooks/useCachedImageSrc', () => ({
  useCachedImageSrc: vi.fn((source, options) => ({
    src: source?.url || options?.fallbackSrc || null,
    status: 'persistent-hit',
    error: null,
    refresh: vi.fn(),
  })),
}));

vi.mock('../chat/ChatEditInputArea', () => ({
  default: ({
    onAttachmentsChange,
  }: {
    onAttachmentsChange: (attachments: Attachment[]) => void;
  }) => (
    <div>
      <button
        data-testid="chat-edit-input"
        onClick={() =>
          onAttachmentsChange([
            {
              id: 'new-source',
              name: 'new-source.png',
              mimeType: 'image/png',
              url: '/new-source.png',
              uploadStatus: 'completed',
            },
          ])
        }
      >
        Upload new source
      </button>
      <button data-testid="clear-attachments" onClick={() => onAttachmentsChange([])}>
        Clear attachments
      </button>
    </div>
  ),
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

const renderImageEditView = (
  messages: Message[],
  extraProps: Partial<React.ComponentProps<typeof ImageEditView>> = {}
) => {
  const renderView = (
    nextMessages: Message[],
    nextProps: Partial<React.ComponentProps<typeof ImageEditView>> = extraProps
  ) => (
    <ToastProvider>
      <ImageEditView
        messages={nextMessages}
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
        {...nextProps}
      />
    </ToastProvider>
  );
  const result = render(renderView(messages));
  return {
    ...result,
    rerenderWithMessages: (nextMessages: Message[]) => result.rerender(renderView(nextMessages)),
    rerenderWithProps: (nextProps: Partial<React.ComponentProps<typeof ImageEditView>>) =>
      result.rerender(renderView(messages, { ...extraProps, ...nextProps })),
  };
};

describe('ImageEditView', () => {
  beforeEach(() => {
    Element.prototype.scrollTo = vi.fn();
    Element.prototype.scrollIntoView = vi.fn();
    modeControlsCoordinatorMock.mockClear();
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

  it('keeps the latest AI result on the active canvas when a source image is still loaded', async () => {
    const source = makeAttachment('source', '/source.png');
    const messages: Message[] = [
      {
        id: 'user-1',
        role: Role.USER,
        content: 'edit this image',
        timestamp: 1,
        attachments: [source],
      },
      {
        id: 'model-1',
        role: Role.MODEL,
        content: 'done',
        timestamp: 2,
        attachments: [makeAttachment('result', '/result.png')],
      },
    ];

    renderImageEditView(messages, { initialAttachments: [source] });

    await waitFor(() => {
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', '/result.png');
    });
  });

  it('shows a newly uploaded attachment on the active canvas after a history result was selected', async () => {
    const messages: Message[] = [
      {
        id: 'user-1',
        role: Role.USER,
        content: 'source',
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
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', '/result.png');
    });

    fireEvent.click(screen.getByTestId('chat-edit-input'));

    await waitFor(() => {
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', '/new-source.png');
    });
  });

  it('shows an uploaded attachment first, then switches to the latest AI result after generation', async () => {
    const messages: Message[] = [
      {
        id: 'user-1',
        role: Role.USER,
        content: 'source',
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

    const { rerenderWithMessages } = renderImageEditView(messages);

    fireEvent.click(screen.getByTestId('chat-edit-input'));

    await waitFor(() => {
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', '/new-source.png');
    });

    fireEvent.click(screen.getByTestId('clear-attachments'));
    rerenderWithMessages([
      ...messages,
      {
        id: 'user-2',
        role: Role.USER,
        content: 'edit new source',
        timestamp: 3,
        attachments: [makeAttachment('new-source', '/new-source.png')],
      },
      {
        id: 'model-2',
        role: Role.MODEL,
        content: 'new result',
        timestamp: 4,
        attachments: [makeAttachment('new-result', '/new-result.png')],
      },
    ]);

    await waitFor(() => {
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', '/new-result.png');
    });
  });

  it('does not let history fallback change the canvas while waiting for generation', async () => {
    const source = makeAttachment('source', '/source.png');
    const messages: Message[] = [
      {
        id: 'user-1',
        role: Role.USER,
        content: 'source',
        timestamp: 1,
        attachments: [source],
      },
      {
        id: 'model-1',
        role: Role.MODEL,
        content: 'old result',
        timestamp: 2,
        attachments: [makeAttachment('old-result', '/old-result.png')],
      },
    ];

    renderImageEditView(messages, {
      initialAttachments: [source],
      loadingState: 'loading',
    });

    await waitFor(() => {
      expect(
        screen.getByText('对话式编辑中，AI 正在理解您的需求并生成图片...')
      ).toBeInTheDocument();
    });

    expect(screen.queryByAltText('Main Canvas')).not.toBeInTheDocument();
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

    const historyItem = screen
      .getByText('original edit prompt')
      .closest('[class*="cursor-pointer"]');
    expect(historyItem).toBeInTheDocument();

    fireEvent.mouseEnter(historyItem!);

    await waitFor(() => {
      expect(screen.getByText('原始提示词')).toBeInTheDocument();
      expect(screen.getByText('optimized edit prompt')).toBeInTheDocument();
    });

    const actionButton = document.querySelector(
      '[data-history-action-trigger="model-1"]'
    ) as HTMLElement | null;
    expect(actionButton).toBeInTheDocument();
    fireEvent.mouseEnter(actionButton!);

    await waitFor(() => {
      expect(screen.queryByText('原始提示词')).not.toBeInTheDocument();
      expect(screen.queryByText('optimized edit prompt')).not.toBeInTheDocument();
    });
  });

  it('refreshes the active canvas when an existing result attachment receives cloudUrl', async () => {
    const staleBlobUrl = 'blob:https://gemini.dicry.cn:18443/image-edit-stale-result';
    const durableUrl = '/api/storage/local-files/2026/05/31/image-edit-result.png';
    const messages: Message[] = [
      {
        id: 'user-1',
        role: Role.USER,
        content: 'source',
        timestamp: 1,
        attachments: [makeAttachment('source', '/source.png')],
      },
      {
        id: 'model-1',
        role: Role.MODEL,
        content: 'done',
        timestamp: 2,
        attachments: [makeAttachment('result', staleBlobUrl)],
      },
    ];

    const { rerenderWithMessages } = renderImageEditView(messages);

    await waitFor(() => {
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', staleBlobUrl);
    });

    messages[1].attachments![0].cloudUrl = durableUrl;
    rerenderWithMessages(messages);

    await waitFor(() => {
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', durableUrl);
    });
  });

  it('updates OpenAI chat-edit controls when the provider model list arrives after mount', async () => {
    const openAiImageModel = {
      id: 'gpt-image-2',
      name: 'GPT Image 2',
      description: '',
      capabilities: {
        vision: true,
        search: false,
        reasoning: false,
        coding: false,
      },
    };

    const { rerenderWithProps } = renderImageEditView([], {
      providerId: 'openai',
      activeModelConfig: openAiImageModel,
      allVisibleModels: [],
    });

    expect(screen.getByTestId('mode-controls')).toHaveAttribute('data-model-ids', '');

    rerenderWithProps({
      providerId: 'openai',
      activeModelConfig: openAiImageModel,
      allVisibleModels: [
        {
          id: 'gpt-5.5',
          name: 'GPT 5.5',
          description: '',
          capabilities: {
            vision: false,
            search: false,
            reasoning: true,
            coding: false,
          },
        },
        openAiImageModel,
      ],
    });

    await waitFor(() => {
      expect(screen.getByTestId('mode-controls')).toHaveAttribute(
        'data-model-ids',
        'gpt-5.5,gpt-image-2'
      );
    });
  });
});
