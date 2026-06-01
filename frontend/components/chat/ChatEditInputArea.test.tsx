// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect, useState } from 'react';

vi.mock('../../hooks/handlers/attachmentUtils', () => ({
  processUserAttachments: vi.fn(
    async (attachments: Attachment[], activeImageUrl?: string | null) =>
      attachments.length > 0 || !activeImageUrl
        ? attachments
        : [
            {
              id: 'canvas-generated',
              mimeType: 'image/png',
              name: 'canvas.png',
              url: activeImageUrl,
            },
          ],
  ),
}));

import ChatEditInputArea from './ChatEditInputArea';
import { ToastProvider } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { processUserAttachments } from '../../hooks/handlers/attachmentUtils';
import type { AppMode, Attachment, Message } from '../../types/types';

function TestHarness({
  mode,
  onSend,
}: {
  mode: AppMode;
  onSend: (text: string, options: any, attachments: Attachment[], nextMode: AppMode) => void;
}) {
  const controls = useControlsState(mode);
  useEffect(() => {
    if (mode === 'video-gen') {
      controls.setAspectRatio('16:9');
      controls.setResolution('720p');
      controls.setVideoSeconds('8');
      controls.setVideoInputStrategy('text_to_video');
    }
  }, [controls, mode]);

  return (
    <ToastProvider>
      <ChatEditInputArea
        onSend={onSend}
        isLoading={false}
        mode={mode}
        activeAttachments={[]}
        onAttachmentsChange={vi.fn()}
        activeImageUrl={null}
        onActiveImageUrlChange={vi.fn()}
        messages={[] as Message[]}
        sessionId="session-test"
        controls={controls}
      />
    </ToastProvider>
  );
}

function ImageChatEditHarness({
  onSend,
}: {
  onSend: (text: string, options: any, attachments: Attachment[], nextMode: AppMode) => void;
}) {
  const controls = useControlsState('image-chat-edit');
  useEffect(() => {
    controls.setNumberOfImages(3);
  }, [controls]);

  return (
    <ToastProvider>
      <ChatEditInputArea
        onSend={onSend}
        isLoading={false}
        mode="image-chat-edit"
        activeAttachments={[]}
        onAttachmentsChange={vi.fn()}
        activeImageUrl="data:image/png;base64,aGVsbG8="
        onActiveImageUrlChange={vi.fn()}
        messages={[] as Message[]}
        sessionId="session-test"
        controls={controls}
      />
    </ToastProvider>
  );
}

const openAiImageEditSchema = {
  provider: 'openai',
  mode: 'image-edit',
  requestedMode: 'image-chat-edit',
  modelId: 'gpt-image-2',
  defaults: {
    aspect_ratio: '1:1',
    resolution: 'auto',
    number_of_images: 1,
    quality: 'high',
    output_format: 'png',
    enhance_prompt: true,
  },
  constraints: { max_image_count: 10 },
  aspectRatios: [{ label: '1:1 Square', value: '1:1' }],
  resolutionTiers: [{ label: 'Auto', value: 'auto', baseResolution: 'Model-selected' }],
  paramOptions: {
    quality: [],
    background: [],
    moderation: [],
    output_format: [],
  },
  numericRanges: {
    output_compression_quality: null,
  },
};

const tongyiWan27ImageEditSchema = {
  provider: 'tongyi',
  mode: 'image-edit',
  requestedMode: 'image-chat-edit',
  modelId: 'wan2.7-image-pro',
  defaults: {
    aspect_ratio: '1:1',
    resolution: '2K',
    number_of_images: 1,
  },
  constraints: {
    max_image_count: 4,
    unsupported_params: ['negative_prompt', 'prompt_extend', 'add_magic_suffix', 'style', 'thinking_mode'],
  },
  aspectRatios: [{ label: '1:1 Square', value: '1:1' }],
  resolutionTiers: [
    { label: '1K', value: '1K', baseResolution: '1024×1024' },
    { label: '2K', value: '2K', baseResolution: '2048×2048' },
  ],
  resolutionMap: {
    '1K': { '1:1': '1024*1024' },
    '2K': { '1:1': '2048*2048' },
  },
  paramOptions: {
    number_of_images: [
      { label: '1', value: 1 },
      { label: '2', value: 2 },
      { label: '3', value: 3 },
      { label: '4', value: 4 },
    ],
  },
};

function OpenAIImageChatEditHarness({
  onSend,
  activeCanvasResponseId,
}: {
  onSend: (text: string, options: any, attachments: Attachment[], nextMode: AppMode) => void;
  activeCanvasResponseId?: string;
}) {
  const controls = useControlsState('image-chat-edit');
  useEffect(() => {
    controls.setNumberOfImages(2);
    controls.setQuality('high');
    controls.setBackground('opaque');
    controls.setModeration('low');
    controls.setOutputFormat('webp');
    controls.setOutputCompressionQuality(64);
  }, [controls]);

  return (
    <ToastProvider>
      <ChatEditInputArea
        onSend={onSend}
        isLoading={false}
        mode="image-chat-edit"
        activeAttachments={[]}
        onAttachmentsChange={vi.fn()}
        activeImageUrl="data:image/png;base64,aGVsbG8="
        onActiveImageUrlChange={vi.fn()}
        activeCanvasAttachment={
          activeCanvasResponseId
            ? {
                id: 'canvas-response-image',
                mimeType: 'image/png',
                name: 'canvas-response-image.png',
                url: 'data:image/png;base64,aGVsbG8=',
                openaiResponseId: activeCanvasResponseId,
              }
            : null
        }
        messages={[] as Message[]}
        sessionId="session-test"
        providerId="openai"
        currentModel={{
          id: 'gpt-image-2',
          name: 'GPT Image 2',
          description: '',
          capabilities: { vision: true, search: false, reasoning: false, coding: false },
        }}
        controlsSchema={openAiImageEditSchema as any}
        controls={controls}
      />
    </ToastProvider>
  );
}

function TongyiImageChatEditHarness({
  onSend,
}: {
  onSend: (text: string, options: any, attachments: Attachment[], nextMode: AppMode) => void;
}) {
  const controls = useControlsState('image-chat-edit');
  useEffect(() => {
    controls.setPromptExtend(true);
  }, [controls]);

  return (
    <ToastProvider>
      <ChatEditInputArea
        onSend={onSend}
        isLoading={false}
        mode="image-chat-edit"
        activeAttachments={[]}
        onAttachmentsChange={vi.fn()}
        activeImageUrl="data:image/png;base64,aGVsbG8="
        onActiveImageUrlChange={vi.fn()}
        messages={[] as Message[]}
        sessionId="session-test"
        providerId="tongyi"
        currentModel={{
          id: 'qwen-image-edit-plus',
          name: 'Qwen Image Edit Plus',
          description: '',
          capabilities: { vision: true, search: false, reasoning: false, coding: false },
        }}
        controls={controls}
      />
    </ToastProvider>
  );
}

function TongyiWan27ImageChatEditHarness({
  onSend,
}: {
  onSend: (text: string, options: any, attachments: Attachment[], nextMode: AppMode) => void;
}) {
  const controls = useControlsState('image-chat-edit');
  useEffect(() => {
    controls.setPromptExtend(true);
    controls.setNegativePrompt('不要文字');
    controls.setThinkingMode(true);
  }, [controls]);

  return (
    <ToastProvider>
      <ChatEditInputArea
        onSend={onSend}
        isLoading={false}
        mode="image-chat-edit"
        activeAttachments={[]}
        onAttachmentsChange={vi.fn()}
        activeImageUrl="data:image/png;base64,aGVsbG8="
        onActiveImageUrlChange={vi.fn()}
        messages={[] as Message[]}
        sessionId="session-test"
        providerId="tongyi"
        currentModel={{
          id: 'wan2.7-image-pro',
          name: 'Wan 2.7 Image Pro',
          description: '',
          capabilities: { vision: true, search: false, reasoning: false, coding: false },
        }}
        controlsSchema={tongyiWan27ImageEditSchema as any}
        controls={controls}
      />
    </ToastProvider>
  );
}

function ImageRecontextHarness({
  onSend,
}: {
  onSend: (text: string, options: any, attachments: Attachment[], nextMode: AppMode) => void;
}) {
  const controls = useControlsState('image-recontext');
  useEffect(() => {
    controls.setOutputMimeType('image/jpeg');
    controls.setOutputCompressionQuality(65);
  }, [controls]);

  return (
    <ToastProvider>
      <ChatEditInputArea
        onSend={onSend}
        isLoading={false}
        mode="image-recontext"
        activeAttachments={[]}
        onAttachmentsChange={vi.fn()}
        activeImageUrl="data:image/png;base64,aGVsbG8="
        onActiveImageUrlChange={vi.fn()}
        messages={[] as Message[]}
        sessionId="session-test"
        controls={controls}
      />
    </ToastProvider>
  );
}

function ImageOutpaintingHarness({
  onSend,
}: {
  onSend: (text: string, options: any, attachments: Attachment[], nextMode: AppMode) => void;
}) {
  const controls = useControlsState('image-outpainting');
  useEffect(() => {
    controls.setOutpaintMode('upscale');
    controls.setUpscaleFactor('x3');
    controls.setNumberOfImages(4);
  }, [controls]);

  return (
    <ToastProvider>
      <ChatEditInputArea
        onSend={onSend}
        isLoading={false}
        mode="image-outpainting"
        activeAttachments={[]}
        onAttachmentsChange={vi.fn()}
        activeImageUrl="data:image/png;base64,aGVsbG8="
        onActiveImageUrlChange={vi.fn()}
        messages={[] as Message[]}
        sessionId="session-test"
        controls={controls}
      />
    </ToastProvider>
  );
}

function StatefulVideoHarness({
  onSend,
  controlsSchema,
  providerId = 'google',
  videoExtensionCount = 0,
}: {
  onSend: (text: string, options: any, attachments: Attachment[], nextMode: AppMode) => void;
  controlsSchema?: any;
  providerId?: string;
  videoExtensionCount?: number;
}) {
  const controls = useControlsState('video-gen');
  const [attachments, setAttachments] = useState<Attachment[]>([]);

  useEffect(() => {
    controls.setAspectRatio('16:9');
    controls.setResolution('720p');
    controls.setVideoSeconds('8');
    controls.setVideoExtensionCount(videoExtensionCount);
  }, [controls, videoExtensionCount]);

  return (
    <ToastProvider>
      <ChatEditInputArea
        onSend={onSend}
        isLoading={false}
        mode="video-gen"
        activeAttachments={attachments}
        onAttachmentsChange={setAttachments}
        activeImageUrl={null}
        onActiveImageUrlChange={vi.fn()}
        messages={[] as Message[]}
        sessionId="session-test"
        providerId={providerId}
        controlsSchema={controlsSchema}
        controls={controls}
      />
    </ToastProvider>
  );
}

function EnhancedVideoHarness({
  onSend,
}: {
  onSend: (text: string, options: any, attachments: Attachment[], nextMode: AppMode) => void;
}) {
  const controls = useControlsState('video-gen');

  useEffect(() => {
    controls.setAspectRatio('16:9');
    controls.setResolution('720p');
    controls.setVideoSeconds('8');
    controls.setEnhancePrompt(true);
    controls.setEnhancePromptModel('gemini-2.5-flash');
  }, [controls]);

  return (
    <ToastProvider>
      <ChatEditInputArea
        onSend={onSend}
        isLoading={false}
        mode="video-gen"
        activeAttachments={[]}
        onAttachmentsChange={vi.fn()}
        activeImageUrl={null}
        onActiveImageUrlChange={vi.fn()}
        messages={[] as Message[]}
        sessionId="session-test"
        controls={controls}
      />
    </ToastProvider>
  );
}

function StatefulImageEditHarness({
  onSend,
}: {
  onSend: (text: string, options: any, attachments: Attachment[], nextMode: AppMode) => void;
}) {
  const controls = useControlsState('image-chat-edit');
  const [attachments, setAttachments] = useState<Attachment[]>([]);

  return (
    <ToastProvider>
      <ChatEditInputArea
        onSend={onSend}
        isLoading={false}
        mode="image-chat-edit"
        activeAttachments={attachments}
        onAttachmentsChange={setAttachments}
        activeImageUrl={null}
        onActiveImageUrlChange={vi.fn()}
        messages={[] as Message[]}
        sessionId="session-test"
        controls={controls}
      />
    </ToastProvider>
  );
}

function InitialAttachmentHarness({
  onActiveImageUrlChange,
}: {
  onActiveImageUrlChange: (url: string | null) => void;
}) {
  const controls = useControlsState('image-chat-edit');
  const initialAttachments: Attachment[] = [
    {
      id: 'att-initial-cloud',
      name: 'initial.png',
      mimeType: 'image/png',
      cloudUrl: '/api/storage/local-files/2026/05/31/initial.png',
      uploadStatus: 'completed',
    },
  ];

  return (
    <ToastProvider>
      <ChatEditInputArea
        onSend={vi.fn()}
        isLoading={false}
        mode="image-chat-edit"
        activeAttachments={[]}
        onAttachmentsChange={vi.fn()}
        activeImageUrl={null}
        onActiveImageUrlChange={onActiveImageUrlChange}
        messages={[] as Message[]}
        sessionId="session-test"
        controls={controls}
        initialAttachments={initialAttachments}
      />
    </ToastProvider>
  );
}

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

describe('ChatEditInputArea', () => {
  beforeEach(() => {
    vi.mocked(processUserAttachments).mockImplementation(
      async (attachments: Attachment[], activeImageUrl?: string | null) =>
        attachments.length > 0 || !activeImageUrl
          ? attachments
          : [
              {
                id: 'canvas-generated',
                mimeType: 'image/png',
                name: 'canvas.png',
                url: activeImageUrl,
              },
            ],
    );
    vi.mocked(processUserAttachments).mockClear();
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:mock-file'),
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('submits text-only video generation requests', async () => {
    const onSend = vi.fn();
    render(<TestHarness mode="video-gen" onSend={onSend} />);

    fireEvent.change(
      screen.getByPlaceholderText(/描述你想生成的视频/i),
      { target: { value: '生成一段产品旋转视频' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /生成视频/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledWith(
        '生成一段产品旋转视频',
        expect.objectContaining({
          aspectRatio: '16:9',
          resolution: '720p',
          seconds: '8',
          videoInputStrategy: 'text_to_video',
        }),
        [],
        'video-gen',
      );
    });

    const sentOptions = onSend.mock.calls[0]?.[1] as Record<string, unknown>;
    expect(sentOptions.numberOfImages).toBeUndefined();
  });

  it('submits text-only audio generation requests', async () => {
    const onSend = vi.fn();
    render(<TestHarness mode="audio-gen" onSend={onSend} />);

    fireEvent.change(
      screen.getByPlaceholderText(/输入要转换为语音的文本/i),
      { target: { value: '把这段话合成为语音' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /生成语音/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledWith(
        '把这段话合成为语音',
        expect.any(Object),
        [],
        'audio-gen',
      );
    });
  });

  it('passes image-chat-edit generation count to the provider options', async () => {
    const onSend = vi.fn();
    render(<ImageChatEditHarness onSend={onSend} />);

    fireEvent.change(
      screen.getByPlaceholderText(/描述你要对图片做的编辑/i),
      { target: { value: '生成三张不同风格的改图' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /开始编辑/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledWith(
        '生成三张不同风格的改图',
        expect.objectContaining({
          numberOfImages: 3,
        }),
        expect.arrayContaining([
          expect.objectContaining({
            url: 'data:image/png;base64,aGVsbG8=',
          }),
        ]),
        'image-chat-edit',
      );
    });
  });

  it('blocks image edit requests when the active canvas cannot be resolved to an attachment', async () => {
    vi.mocked(processUserAttachments).mockResolvedValueOnce([]);
    const onSend = vi.fn();
    render(<ImageChatEditHarness onSend={onSend} />);

    fireEvent.change(
      screen.getByPlaceholderText(/描述你要对图片做的编辑/i),
      { target: { value: '继续编辑当前画布图片' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /开始编辑/i }));

    await waitFor(() => {
      expect(processUserAttachments).toHaveBeenCalled();
    });

    expect(onSend).not.toHaveBeenCalled();
    expect(await screen.findByText('未能读取当前图片，请重新选择历史图片或重新上传附件')).toBeInTheDocument();
  });

  it('omits hidden OpenAI GPT Image edit options and keeps prompt enhancement enabled', async () => {
    const onSend = vi.fn();
    render(<OpenAIImageChatEditHarness onSend={onSend} />);

    fireEvent.change(
      screen.getByPlaceholderText(/描述你要对图片做的编辑/i),
      { target: { value: '保留主体并替换为电商场景' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /开始编辑/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalled();
    });

    const sentOptions = onSend.mock.calls[0]?.[1] as Record<string, unknown>;
    expect(sentOptions).toEqual(
      expect.objectContaining({
        numberOfImages: 2,
        enhancePrompt: true,
      }),
    );
    expect(sentOptions.quality).toBeUndefined();
    expect(sentOptions.background).toBeUndefined();
    expect(sentOptions.moderation).toBeUndefined();
    expect(sentOptions.outputFormat).toBeUndefined();
    expect(sentOptions.outputCompressionQuality).toBeUndefined();
    expect(sentOptions.outputMimeType).toBeUndefined();
  });

  it('continues OpenAI Responses image edits from the active canvas response id', async () => {
    const onSend = vi.fn();
    render(<OpenAIImageChatEditHarness onSend={onSend} activeCanvasResponseId="resp_123" />);

    fireEvent.change(
      screen.getByPlaceholderText(/描述你要对图片做的编辑/i),
      { target: { value: '继续上一轮编辑并增强光线' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /开始编辑/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalled();
    });

    const sentOptions = onSend.mock.calls[0]?.[1] as Record<string, unknown>;
    const sentAttachments = onSend.mock.calls[0]?.[2] as Attachment[];
    expect(sentOptions).toEqual(
      expect.objectContaining({
        openaiPreviousResponseId: 'resp_123',
      }),
    );
    expect(sentOptions.openaiImageApi).toBeUndefined();
    expect(sentOptions.openaiResponsesModel).toBeUndefined();
    expect(processUserAttachments).toHaveBeenCalledWith(
      [],
      'data:image/png;base64,aGVsbG8=',
      [],
      'session-test',
      'canvas',
    );
    expect(sentAttachments).toHaveLength(1);
    expect(sentAttachments[0].url).toBe('data:image/png;base64,aGVsbG8=');
  });

  it('uses the latest active canvas response id after switching canvas history items', async () => {
    const onSend = vi.fn();
    const { rerender } = render(
      <OpenAIImageChatEditHarness onSend={onSend} activeCanvasResponseId="resp_old" />,
    );

    rerender(<OpenAIImageChatEditHarness onSend={onSend} activeCanvasResponseId="resp_new" />);

    fireEvent.change(
      screen.getByPlaceholderText(/描述你要对图片做的编辑/i),
      { target: { value: '基于当前画布继续编辑' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /开始编辑/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalled();
    });

    const sentOptions = onSend.mock.calls[0]?.[1] as Record<string, unknown>;
    expect(sentOptions.openaiPreviousResponseId).toBe('resp_new');
  });

  it('passes Tongyi prompt enhancement option for image edit modes', async () => {
    const onSend = vi.fn();
    render(<TongyiImageChatEditHarness onSend={onSend} />);

    fireEvent.change(
      screen.getByPlaceholderText(/描述你要对图片做的编辑/i),
      { target: { value: '保留主体，把背景改成白色影棚' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /开始编辑/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalled();
    });

    const sentOptions = onSend.mock.calls[0]?.[1] as Record<string, unknown>;
    expect(sentOptions).toEqual(
      expect.objectContaining({
        promptExtend: true,
      }),
    );
  });

  it('omits Wan 2.7 unsupported edit params from Tongyi image edit requests', async () => {
    const onSend = vi.fn();
    render(<TongyiWan27ImageChatEditHarness onSend={onSend} />);

    fireEvent.change(
      screen.getByPlaceholderText(/描述你要对图片做的编辑/i),
      { target: { value: '把车身改成红色' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /开始编辑/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalled();
    });

    const sentOptions = onSend.mock.calls[0]?.[1] as Record<string, unknown>;
    expect(sentOptions.promptExtend).toBeUndefined();
    expect(sentOptions.negativePrompt).toBeUndefined();
    expect(sentOptions.thinkingMode).toBeUndefined();
  });

  it('omits unsupported output MIME options for Gemini recontext requests', async () => {
    const onSend = vi.fn();
    render(<ImageRecontextHarness onSend={onSend} />);

    fireEvent.change(
      screen.getByPlaceholderText(/描述新的上下文环境/i),
      { target: { value: '放到夏日桌面场景' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /重新上下文/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalled();
    });

    const sentOptions = onSend.mock.calls[0]?.[1] as Record<string, unknown>;
    expect(sentOptions.outputMimeType).toBeUndefined();
    expect(sentOptions.outputCompressionQuality).toBeUndefined();
  });

  it('forces upscale outpainting requests to a single image', async () => {
    const onSend = vi.fn();
    render(<ImageOutpaintingHarness onSend={onSend} />);

    fireEvent.click(screen.getByRole('button', { name: /开始扩图/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledWith(
        '',
        expect.objectContaining({
          outpaintMode: 'upscale',
          upscaleFactor: 'x3',
          numberOfImages: 1,
        }),
        expect.arrayContaining([
          expect.objectContaining({
            url: 'data:image/png;base64,aGVsbG8=',
          }),
        ]),
        'image-outpainting',
      );
    });
  });

  it('passes the selected video prompt enhancement model to generation', async () => {
    const onSend = vi.fn();
    render(<EnhancedVideoHarness onSend={onSend} />);

    fireEvent.change(
      screen.getByPlaceholderText(/描述你想生成的视频/i),
      { target: { value: '生成一段带运镜的产品视频' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /生成视频/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledWith(
        '生成一段带运镜的产品视频',
        expect.objectContaining({
          enhancePrompt: true,
          enhancePromptModel: 'gemini-2.5-flash',
        }),
        [],
        'video-gen',
      );
    });
  });

  it.each(['google', 'openai', 'tongyi', 'grok'])(
    'labels the main prompt as global/base video prompt when extension is enabled for %s',
    (providerId) => {
      render(
        <StatefulVideoHarness
          onSend={vi.fn()}
          providerId={providerId}
          videoExtensionCount={1}
        />
      );

      expect(screen.getByPlaceholderText(/全局\/基础视频提示词/i)).toBeInTheDocument();
      expect(screen.queryByPlaceholderText(/^描述你想生成的视频/)).not.toBeInTheDocument();
    }
  );

  it('allows more than two video reference files without implicit front-end truncation', async () => {
    const onSend = vi.fn();
    render(<StatefulVideoHarness onSend={onSend} />);

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeTruthy();
    expect(fileInput.multiple).toBe(true);

    const files = [
      new File(['a'], 'frame-1.png', { type: 'image/png' }),
      new File(['b'], 'frame-2.png', { type: 'image/png' }),
      new File(['c'], 'frame-3.png', { type: 'image/png' }),
    ];

    fireEvent.change(fileInput, { target: { files } });
    const promptInputs = screen.getAllByPlaceholderText(/描述你想生成的视频/i);
    fireEvent.change(promptInputs[promptInputs.length - 1], {
      target: { value: '用多张图合成一段视频' },
    });
    fireEvent.click(screen.getByRole('button', { name: /生成视频/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledWith(
        '用多张图合成一段视频',
        expect.objectContaining({
          aspectRatio: '16:9',
          resolution: '720p',
          seconds: '8',
        }),
        expect.arrayContaining([
          expect.objectContaining({ name: 'frame-1.png' }),
          expect.objectContaining({ name: 'frame-2.png' }),
          expect.objectContaining({ name: 'frame-3.png' }),
        ]),
        'video-gen',
      );
    });

    const sentAttachments = onSend.mock.calls[0]?.[2] as Attachment[];
    expect(sentAttachments).toHaveLength(3);
  });

  it('lets video attachments be assigned schema roles before submit', async () => {
    const onSend = vi.fn();
    const controlsSchema = {
      provider: 'tongyi',
      mode: 'video-gen',
      modelId: 'wan2.7-i2v',
      videoContract: {
        attachmentSlots: [
          {
            name: 'source_image',
            label: '首帧',
            kind: 'image',
            roles: ['first_frame', 'source_image'],
            enabled: true,
          },
          {
            name: 'last_frame_image',
            label: '尾帧',
            kind: 'image',
            roles: ['last_frame'],
            enabled: true,
          },
        ],
      },
    };
    render(<StatefulVideoHarness onSend={onSend} controlsSchema={controlsSchema} />);

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: {
        files: [
          new File(['a'], 'start.png', { type: 'image/png' }),
          new File(['b'], 'end.png', { type: 'image/png' }),
        ],
      },
    });

    await waitFor(() => {
      expect(screen.getByTitle('start.png')).toBeInTheDocument();
      expect(screen.getByTitle('end.png')).toBeInTheDocument();
    });

    const roleSelects = screen.getAllByLabelText(/素材角色/i);
    fireEvent.change(roleSelects[1], { target: { value: 'last_frame' } });

    const promptInputs = screen.getAllByPlaceholderText(/描述你想生成的视频/i);
    fireEvent.change(promptInputs[promptInputs.length - 1], {
      target: { value: '用首尾帧生成产品视频' },
    });
    fireEvent.click(screen.getByRole('button', { name: /生成视频/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalled();
    });

    const sentAttachments = onSend.mock.calls[0]?.[2] as Attachment[];
    expect(sentAttachments).toEqual([
      expect.objectContaining({ name: 'start.png', role: 'first_frame' }),
      expect.objectContaining({ name: 'end.png', role: 'last_frame' }),
    ]);
  });

  it('accepts driving audio only when the video contract exposes an audio slot', async () => {
    const onSend = vi.fn();
    const controlsSchema = {
      provider: 'tongyi',
      mode: 'video-gen',
      modelId: 'wan2.7-i2v',
      videoContract: {
        attachmentSlots: [
          {
            name: 'driving_audio',
            label: '驱动音频',
            kind: 'audio',
            roles: ['driving_audio'],
            enabled: true,
          },
        ],
      },
    };
    render(<StatefulVideoHarness onSend={onSend} controlsSchema={controlsSchema} />);

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput.accept).toContain('audio/*');

    fireEvent.change(fileInput, {
      target: {
        files: [new File(['audio'], 'voice.mp3', { type: 'audio/mpeg' })],
      },
    });

    await waitFor(() => {
      expect(screen.getByTitle('voice.mp3')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/描述你想生成的视频/i), {
      target: { value: '使用音频驱动口型' },
    });
    fireEvent.click(screen.getByRole('button', { name: /生成视频/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalled();
    });

    expect(onSend.mock.calls[0]?.[2]).toEqual([
      expect.objectContaining({ name: 'voice.mp3', role: 'driving_audio' }),
    ]);
  });

  it('adds pasted image files through the shared prompt input attachment flow', async () => {
    const onSend = vi.fn();
    render(<StatefulImageEditHarness onSend={onSend} />);

    const textarea = screen.getByPlaceholderText(/请先上传图片/i);
    dispatchPaste(textarea, [new File(['a'], 'clipboard.png', { type: 'image/png' })]);

    await waitFor(() => {
      expect(screen.getByTitle('clipboard.png')).toBeInTheDocument();
    });

    fireEvent.change(textarea, {
      target: { value: '把背景改成玻璃展厅' },
    });
    fireEvent.click(screen.getByRole('button', { name: /开始编辑/i }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledWith(
        '把背景改成玻璃展厅',
        expect.any(Object),
        [expect.objectContaining({ name: 'clipboard.png', mimeType: 'image/png' })],
        'image-chat-edit',
      );
    });
  });

  it('uses durable initial attachment urls when activating the edit canvas', async () => {
    const onActiveImageUrlChange = vi.fn();

    render(<InitialAttachmentHarness onActiveImageUrlChange={onActiveImageUrlChange} />);

    await waitFor(() => {
      expect(onActiveImageUrlChange).toHaveBeenCalledWith(
        '/api/storage/local-files/2026/05/31/initial.png'
      );
    });
  });
});
