// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../contexts/ToastContext';
import { Role, type Attachment, type Message } from '../../types/types';
import { ImageMaskEditView } from './ImageMaskEditView';

const apiRequestMock = vi.hoisted(() => vi.fn());

vi.mock('../../services/apiClient', () => ({
  apiClient: {
    request: apiRequestMock,
  },
}));

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

const sourceImageUrl = 'data:image/png;base64,cmF3';
const maskImageUrl = 'data:image/png;base64,bWFzaw==';

const makeAttachment = (): Attachment => ({
  id: 'source-1',
  name: 'source.png',
  mimeType: 'image/png',
  url: sourceImageUrl,
  uploadStatus: 'completed',
});

const renderMaskView = () => {
  const messages: Message[] = [
    {
      id: 'user-1',
      role: Role.USER,
      content: 'source image',
      timestamp: 1,
      attachments: [makeAttachment()],
    },
  ];

  return render(
    <ToastProvider>
      <ImageMaskEditView
        messages={messages}
        setAppMode={vi.fn()}
        onImageClick={vi.fn()}
        loadingState="idle"
        onSend={vi.fn()}
        onStop={vi.fn()}
        activeModelConfig={{
          id: 'imagen-3.0-capability-001',
          name: 'Imagen Capability',
          description: '',
          capabilities: {
            vision: true,
            search: false,
            reasoning: false,
            coding: false,
          },
        }}
        initialAttachments={[makeAttachment()]}
        providerId="google"
        sessionId="session-1"
      />
    </ToastProvider>
  );
};

describe('ImageMaskEditView auto mask feedback', () => {
  beforeEach(() => {
    Element.prototype.scrollTo = vi.fn();
    apiRequestMock.mockReset();
    apiRequestMock.mockResolvedValue({
      data: {
        success: true,
        masks: [{ url: maskImageUrl, mime_type: 'image/png', labels: [] }],
      },
    });
    vi.stubGlobal('fetch', vi.fn(async () => ({
      blob: async () => new Blob(['raw'], { type: 'image/png' }),
    })));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('renders automatic background mask feedback directly on the main canvas', async () => {
    renderMaskView();

    await waitFor(() => {
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', sourceImageUrl);
    });

    fireEvent.click(screen.getByRole('button', { name: /Extract mask/i }));
    fireEvent.click(screen.getByRole('button', { name: /Background \(自动背景\)/i }));

    await waitFor(() => {
      expect(screen.getByAltText('自动背景 Mask 覆盖层')).toHaveAttribute('src', maskImageUrl);
    });

    expect(screen.getByText('自动背景 Mask 已应用')).toBeInTheDocument();
    expect(screen.getByText('已同步到主画布')).toBeInTheDocument();
    expect(apiRequestMock).toHaveBeenCalledWith(
      '/api/modes/google/image-mask-preview',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"maskMode":"MASK_MODE_BACKGROUND"'),
      })
    );
  });

  it('shows non-blocking feedback when the mask preview segmentation model is not enabled', async () => {
    apiRequestMock.mockResolvedValueOnce({
      data: {
        success: false,
        error: "Model access denied (404). Please request access to 'image-segmentation-001' model at: https://console.cloud.google.com/vertex-ai/publishers/google/model-garden/image-segmentation-001",
      },
    });

    renderMaskView();

    await waitFor(() => {
      expect(screen.getByAltText('Main Canvas')).toHaveAttribute('src', sourceImageUrl);
    });

    fireEvent.click(screen.getByRole('button', { name: /Extract mask/i }));
    fireEvent.click(screen.getByRole('button', { name: /Background \(自动背景\)/i }));

    await waitFor(() => {
      expect(screen.getByText(/自动背景 Mask 预览模型未开通/)).toBeInTheDocument();
    });

    expect(screen.getByText(/不依赖该预览模型/)).toBeInTheDocument();
    expect(screen.queryByText(/未能提取 自动背景 Mask/)).not.toBeInTheDocument();
  });
});
