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
  quality: 'low',
  background: 'opaque',
  moderation: 'low',
  outputFormat: 'jpeg',
  enhancePrompt: true,
  enhancePromptModel: '',
  enhancePromptThinkingLevel: 'auto',
  promptExtend: false,
  addMagicSuffix: false,
  thinkingMode: true,
  setStyle: vi.fn(),
  setNumberOfImages: vi.fn(),
  setAspectRatio: vi.fn(),
  setResolution: vi.fn(),
  setNegativePrompt: vi.fn(),
  setSeed: vi.fn(),
  setOutputMimeType: vi.fn(),
  setOutputCompressionQuality: vi.fn(),
  setQuality: vi.fn(),
  setBackground: vi.fn(),
  setModeration: vi.fn(),
  setOutputFormat: vi.fn(),
  setEnhancePrompt: vi.fn(),
  setEnhancePromptModel: vi.fn(),
  setEnhancePromptThinkingLevel: vi.fn(),
  setPromptExtend: vi.fn(),
  setAddMagicSuffix: vi.fn(),
  setThinkingMode: vi.fn(),
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

const openAiGptImageSchema = vi.hoisted(() => ({
  defaults: {
    aspect_ratio: '1:1',
    resolution: '1K',
    number_of_images: 1,
    quality: 'high',
    output_format: 'png',
    enhance_prompt: false,
  },
  constraints: {
    max_image_count: 10,
  },
  aspectRatios: [
    { label: '1:1 Square', value: '1:1' },
    { label: '4:3 Landscape', value: '4:3' },
    { label: '3:4 Portrait', value: '3:4' },
    { label: '16:9 Widescreen', value: '16:9' },
    { label: '9:16 Vertical', value: '9:16' },
  ],
  resolutionTiers: [
    { label: 'Auto', value: 'auto', baseResolution: 'Model-selected' },
    { label: '1K', value: '1K', baseResolution: '1024×1024' },
    { label: '2K', value: '2K', baseResolution: '2048×2048' },
    { label: '4K', value: '4K', baseResolution: '3840×2160' },
  ],
  resolutionMap: {
    auto: { '1:1': 'auto', '4:3': 'auto', '3:4': 'auto', '16:9': 'auto', '9:16': 'auto' },
    '1K': { '1:1': '1024x1024', '4:3': '1152x864', '3:4': '864x1152', '16:9': '1280x720', '9:16': '720x1280' },
    '2K': { '1:1': '2048x2048', '4:3': '2048x1536', '3:4': '1536x2048', '16:9': '2048x1152', '9:16': '1152x2048' },
    '4K': { '1:1': '2880x2880', '4:3': '2880x2160', '3:4': '2160x2880', '16:9': '3840x2160', '9:16': '2160x3840' },
  },
  paramOptions: {
    number_of_images: [{ label: '1', value: 1 }],
    quality: [],
    background: [],
    moderation: [],
    output_format: [],
  },
  numericRanges: {
    output_compression_quality: null,
  },
}));

const tongyiWan27ImageSchema = vi.hoisted(() => ({
  defaults: {
    aspect_ratio: '1:1',
    resolution: '2K',
    number_of_images: 1,
    thinking_mode: true,
    prompt_extend: false,
    add_magic_suffix: false,
  },
  constraints: {
    max_image_count: 4,
    unsupported_params: ['negative_prompt', 'prompt_extend', 'add_magic_suffix', 'style'],
  },
  aspectRatios: [{ label: '1:1 Square', value: '1:1' }],
  resolutionTiers: [
    { label: '1K', value: '1K', baseResolution: '1024×1024' },
    { label: '2K', value: '2K', baseResolution: '2048×2048' },
    { label: '4K', value: '4K', baseResolution: '4096×4096' },
  ],
  resolutionMap: {
    '1K': { '1:1': '1024*1024' },
    '2K': { '1:1': '2048*2048' },
    '4K': { '1:1': '4096*4096' },
  },
  paramOptions: {
    number_of_images: [
      { label: '1', value: 1 },
      { label: '2', value: 2 },
      { label: '3', value: 3 },
      { label: '4', value: 4 },
    ],
    thinking_mode: [
      { label: '开启', value: true },
      { label: '关闭', value: false },
    ],
  },
}));

vi.mock('../../hooks/useControlsState', () => ({
  useControlsState: () => controlsStateMock,
}));

vi.mock('../../hooks/useModeControlsSchema', () => ({
  useModeControlsSchema: (providerId: string) => ({
    schema:
      providerId === 'openai'
        ? openAiGptImageSchema
        : providerId === 'tongyi'
          ? tongyiWan27ImageSchema
          : schemaWithoutOutputMime,
    loading: false,
    error: null,
  }),
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

vi.mock('../../hooks/useCachedImageSrc', () => ({
  useCachedImageSrc: (
    source: { url?: string; file?: File } | null | undefined,
    options: { fallbackSrc?: string | null } = {}
  ) => ({
    src: options.fallbackSrc || source?.url || (source?.file ? `cached-file:${source.file.name}` : null),
    status: 'raw-fallback',
    error: null,
    refresh: vi.fn(),
  }),
}));

const makeAttachment = (id: string, url: string): Attachment => ({
  id,
  name: `${id}.png`,
  mimeType: 'image/png',
  url,
  uploadStatus: 'completed',
});

function dispatchPaste(target: HTMLElement, files: File[]) {
  const event = new Event('paste', { bubbles: true, cancelable: true });
  Object.defineProperty(event, 'clipboardData', {
    value: {
      files,
      items: files.map((file) => ({
        kind: 'file',
        type: file.type,
        getAsFile: () => file,
      })),
    },
  });
  fireEvent(target, event);
}

afterEach(() => {
  cleanup();
  controlsStateMock.style = 'None';
  controlsStateMock.promptExtend = false;
  controlsStateMock.addMagicSuffix = false;
  controlsStateMock.thinkingMode = true;
  vi.unstubAllGlobals();
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

  it('passes pasted reference images with image generation requests', async () => {
    const onSend = vi.fn();

    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:image-gen-reference'),
    });

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
        initialPrompt="use this product reference"
        providerId="google"
        sessionId="session-1"
      />
    );

    const textarea = screen.getByPlaceholderText(/描述你想要生成的图片/i);
    dispatchPaste(textarea, [new File(['image'], 'reference.png', { type: 'image/png' })]);

    await waitFor(() => {
      expect(screen.getByTitle('reference.png')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /生成图片/ }));

    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));
    expect(onSend.mock.calls[0][2]).toEqual([
      expect.objectContaining({
        name: 'reference.png',
        mimeType: 'image/png',
      }),
    ]);
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

  it('renders historical generated images when the stored attachment url is empty but tempUrl is available', async () => {
    const messages: Message[] = [
      {
        id: 'model-temp-url',
        role: Role.MODEL,
        content: 'restored prompt',
        timestamp: 1,
        attachments: [
          {
            id: 'result-temp-url',
            name: 'result-temp-url.png',
            mimeType: 'image/png',
            url: '',
            tempUrl: '/api/storage/local-files/generated/restored.png',
            uploadStatus: 'completed',
          },
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

    expect(screen.getByText('restored prompt')).toBeInTheDocument();
    expect(screen.getByAltText('History preview')).toHaveAttribute(
      'src',
      '/api/storage/local-files/generated/restored.png'
    );
    expect(screen.getByAltText('生成图片 1')).toHaveAttribute(
      'src',
      '/api/storage/local-files/generated/restored.png'
    );
  });

  it('keeps file-only generated history attachments visible in the sidebar and result canvas', async () => {
    const file = new File(['generated-file-only'], 'generated-file-only.png', {
      type: 'image/png',
    });
    const messages: Message[] = [
      {
        id: 'model-file-only',
        role: Role.MODEL,
        content: 'file-only generated result',
        timestamp: 1,
        attachments: [
          {
            id: 'result-file-only',
            name: 'generated-file-only.png',
            mimeType: 'image/png',
            file,
            uploadStatus: 'pending',
          },
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

    expect(screen.getByText('file-only generated result')).toBeInTheDocument();
    expect(screen.getByAltText('History preview')).toHaveAttribute(
      'src',
      'local-blob:result-file-only'
    );
    expect(screen.getByAltText('生成图片 1')).toHaveAttribute(
      'src',
      'cached-file:generated-file-only.png'
    );
  });

  it('omits hidden GPT Image 2 advanced params and keeps prompt enhancement enabled', async () => {
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
          id: 'gpt-image-2',
          name: 'GPT Image 2',
          description: '',
          capabilities: {
            vision: true,
            search: false,
            reasoning: false,
            coding: false,
          },
        }}
        initialPrompt="cinematic product photo"
        providerId="openai"
        sessionId="session-1"
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /生成图片/ }));

    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));
    const sentOptions = onSend.mock.calls[0][1];
    expect(sentOptions).toMatchObject({
      imageAspectRatio: '1:1',
      imageResolution: '1K',
      numberOfImages: 1,
      enhancePrompt: true,
    });
    expect(sentOptions.quality).toBeUndefined();
    expect(sentOptions.background).toBeUndefined();
    expect(sentOptions.moderation).toBeUndefined();
    expect(sentOptions.outputFormat).toBeUndefined();
    expect(sentOptions.outputCompressionQuality).toBeUndefined();
  });

  it('uses Wan 2.7 schema to omit unsupported legacy Tongyi params and keep thinking mode', async () => {
    const onSend = vi.fn();
    controlsStateMock.style = 'Oil Painting';
    controlsStateMock.promptExtend = true;
    controlsStateMock.addMagicSuffix = true;
    controlsStateMock.thinkingMode = true;

    render(
      <ImageGenView
        messages={[]}
        setAppMode={vi.fn()}
        onImageClick={vi.fn()}
        loadingState="idle"
        onSend={onSend}
        onStop={vi.fn()}
        activeModelConfig={{
          id: 'wan2.7-image-pro',
          name: 'Wan 2.7 Image Pro',
          description: '',
          capabilities: {
            vision: true,
            search: false,
            reasoning: false,
            coding: false,
          },
        }}
        initialPrompt="高端运动鞋棚拍"
        providerId="tongyi"
        sessionId="session-1"
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /生成图片/ }));

    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));
    const sentOptions = onSend.mock.calls[0][1];
    expect(sentOptions).toMatchObject({
      imageAspectRatio: '1:1',
      imageResolution: '1K',
      numberOfImages: 1,
      thinkingMode: true,
    });
    expect(sentOptions.imageStyle).toBeUndefined();
    expect(sentOptions.promptExtend).toBeUndefined();
    expect(sentOptions.addMagicSuffix).toBeUndefined();
  });
});
