// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ImageGenView } from './ImageGenView';
import { Role, type Attachment, type Message } from '../../types/types';

const controlsStateMock = vi.hoisted(() => ({
  enableThinking: false,
  aspectRatio: '1:1',
  resolution: '1K',
  numberOfImages: 1,
  style: 'None',
  negativePrompt: '',
  seed: -1,
  outputMimeType: 'image/jpeg',
  outputCompressionQuality: 65,
  enhancePrompt: true,
  enhancePromptModel: '',
  promptExtend: false,
  addMagicSuffix: false,
  setStyle: vi.fn(),
  setNumberOfImages: vi.fn(),
  setAspectRatio: vi.fn(),
  setResolution: vi.fn(),
  setNegativePrompt: vi.fn(),
  setSeed: vi.fn(),
  setOutputMimeType: vi.fn(),
  setOutputCompressionQuality: vi.fn(),
  setEnhancePrompt: vi.fn(),
}));

const schemaWithoutOutputMime = vi.hoisted(() => ({
  defaults: {
    aspect_ratio: '1:1',
    resolution: '1K',
    number_of_images: 1,
  },
  constraints: {
    max_image_count: 10,
  },
  aspectRatios: [{ label: '1:1 Square', value: '1:1' }],
  resolutionTiers: [{ label: '1K Standard', value: '1K', baseResolution: '1024×1024' }],
  resolutionMap: {
    '1K': { '1:1': '1024*1024' },
  },
  paramOptions: {
    number_of_images: [{ label: '1', value: 1 }],
  },
}));

vi.mock('../../hooks/useControlsState', () => ({
  useControlsState: () => controlsStateMock,
}));

vi.mock('../../hooks/useModeControlsSchema', () => ({
  useModeControlsSchema: () => ({ schema: schemaWithoutOutputMime, loading: false, error: null }),
  getPixelResolutionFromSchema: (schema: any, aspectRatio: string, resolution: string) =>
    schema?.resolutionMap?.[resolution]?.[aspectRatio] ?? null,
}));

vi.mock('../../coordinators/ModeControlsCoordinator', () => ({
  ModeControlsCoordinator: () => <div data-testid="mode-controls" />,
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
  useHistoryListActions: ({ items }: { items: unknown[] }) => ({
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

afterEach(() => {
  cleanup();
});

describe('ImageGenView output MIME request params', () => {
  it('does not send output MIME params when the active schema does not support them', async () => {
    const onSend = vi.fn();

    render(
      <ImageGenView
        messages={[]}
        setAppMode={vi.fn()}
        onImageClick={vi.fn()}
        loadingState="idle"
        onSend={onSend}
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
        initialPrompt="summer product poster"
        providerId="google"
        sessionId="session-1"
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /生成图片/ }));

    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));
    const sentOptions = onSend.mock.calls[0][1];
    expect(sentOptions.outputMimeType).toBeUndefined();
    expect(sentOptions.outputCompressionQuality).toBeUndefined();
  });

  it('uses the shared image history sidebar with attachment prompt preview', async () => {
    const messages: Message[] = [
      {
        id: 'model-1',
        role: Role.MODEL,
        content: '📝 summer product poster\n✨ optimized summer product poster prompt',
        timestamp: 1,
        attachments: [
          makeAttachment('result-1', '/result-1.png'),
          makeAttachment('result-2', '/result-2.png'),
          makeAttachment('result-3', '/result-3.png'),
          makeAttachment('result-4', '/result-4.png'),
        ],
      },
    ];

    render(
      <ImageGenView
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
        providerId="google"
        sessionId="session-1"
      />
    );

    expect(screen.getByText('仅收藏')).toBeInTheDocument();
    expect(screen.getByText('含增强提示词')).toBeInTheDocument();

    const historyItem = screen.getByText('summer product poster').closest('[class*="cursor-pointer"]');
    expect(historyItem).toBeInTheDocument();

    fireEvent.mouseEnter(historyItem!);

    await waitFor(() => {
      expect(screen.getByText('增强提示词')).toBeInTheDocument();
      expect(screen.getByText('optimized summer product poster prompt')).toBeInTheDocument();
      expect(screen.getByText('附图')).toBeInTheDocument();
    });

    const attachmentGrid = document.querySelector('[data-history-attachment-grid]');
    expect(attachmentGrid).toHaveClass('grid-cols-4');

    const attachmentImages = screen.getAllByAltText('History attachment');
    expect(attachmentImages).toHaveLength(4);
    attachmentImages.forEach((image) => {
      expect(image).toHaveClass('object-contain');
      expect(image).not.toHaveClass('object-cover');
    });
  });
});
