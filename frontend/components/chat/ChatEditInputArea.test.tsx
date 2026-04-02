// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect, useState } from 'react';

vi.mock('../../hooks/handlers/attachmentUtils', () => ({
  processUserAttachments: vi.fn(async (attachments: Attachment[]) => attachments),
}));

import ChatEditInputArea from './ChatEditInputArea';
import { ToastProvider } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
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

function StatefulVideoHarness({
  onSend,
}: {
  onSend: (text: string, options: any, attachments: Attachment[], nextMode: AppMode) => void;
}) {
  const controls = useControlsState('video-gen');
  const [attachments, setAttachments] = useState<Attachment[]>([]);

  useEffect(() => {
    controls.setAspectRatio('16:9');
    controls.setResolution('720p');
    controls.setVideoSeconds('8');
  }, [controls]);

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
        controls={controls}
      />
    </ToastProvider>
  );
}

describe('ChatEditInputArea', () => {
  beforeEach(() => {
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
        }),
        [],
        'video-gen',
      );
    });
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
});
