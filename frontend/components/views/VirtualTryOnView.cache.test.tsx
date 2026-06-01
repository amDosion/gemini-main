// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { VirtualTryOnView } from './VirtualTryOnView';
import { Role, type Message } from '../../types/types';

vi.mock('../common/GenViewLayout', () => ({
  GenViewLayout: ({ sidebar, main }: any) => (
    <div>
      <aside data-testid="tryon-sidebar">{sidebar}</aside>
      <main data-testid="tryon-main">{main}</main>
    </div>
  ),
}));

vi.mock('../common/CachedImage', () => ({
  CachedImage: ({ src, source, alt, preferMemoryCache, ...props }: any) => (
    <img
      data-testid="cached-tryon-image"
      data-source-url={source?.url || ''}
      data-has-file={String(Boolean(source?.file))}
      data-prefer-memory-cache={String(preferMemoryCache)}
      src={`cached:${src}`}
      alt={alt}
      {...props}
    />
  ),
}));

vi.mock('../../contexts/ToastContext', () => ({
  useToastContext: () => ({ showError: vi.fn() }),
}));

vi.mock('../../hooks/useModeControlsSchema', () => ({
  useModeControlsSchema: () => ({
    schema: {
      defaults: { base_steps: 32, number_of_images: 1 },
      numericRanges: { base_steps: { min: 8, max: 48, step: 8 } },
      paramOptions: { number_of_images: [{ label: '1', value: 1 }] },
    },
  }),
}));

vi.mock('../../hooks/handlers/attachmentUtils', () => ({
  fileToBase64: vi.fn(async (file: File) => `data:image/png;base64,${file.name}`),
  processUserAttachments: vi.fn(),
}));

const baseProps = {
  setAppMode: vi.fn(),
  onImageClick: vi.fn(),
  loadingState: 'idle',
  onSend: vi.fn(),
  onStop: vi.fn(),
  activeModelConfig: {
    id: 'tryon-model',
    name: 'Try-On Model',
    description: 'try-on model',
    capabilities: { vision: true, search: false, reasoning: false, coding: false },
  },
  providerId: 'tongyi',
  sessionId: 'tryon-session',
};

describe('VirtualTryOnView media cache integration', () => {
  beforeEach(() => {
    if (!HTMLElement.prototype.scrollTo) {
      HTMLElement.prototype.scrollTo = vi.fn();
    } else {
      vi.spyOn(HTMLElement.prototype, 'scrollTo').mockImplementation(() => undefined);
    }
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it('renders cloudUrl-only try-on history and active result images through CachedImage', () => {
    const messages: Message[] = [
      {
        id: 'tryon-result-message',
        role: Role.MODEL,
        content: 'try-on result',
        timestamp: Date.now(),
        mode: 'virtual-try-on',
        attachments: [
          {
            id: 'tryon-result-image',
            name: 'tryon-result.png',
            mimeType: 'image/png',
            cloudUrl: '/api/storage/local-files/tryon/result.png',
            uploadStatus: 'completed',
          },
        ],
      },
    ];

    render(<VirtualTryOnView {...baseProps} messages={messages} />);

    const renderedImages = screen.getAllByTestId('cached-tryon-image');
    expect(renderedImages).toHaveLength(2);
    expect(renderedImages.map((image) => image.getAttribute('src'))).toEqual([
      'cached:/api/storage/local-files/tryon/result.png',
      'cached:/api/storage/local-files/tryon/result.png',
    ]);
    expect(renderedImages.every((image) =>
      image.getAttribute('data-source-url') === '/api/storage/local-files/tryon/result.png'
    )).toBe(true);
  });

  it('uses durable try-on result urls instead of stale blob urls in history and active result images', () => {
    const messages: Message[] = [
      {
        id: 'tryon-stale-result-message',
        role: Role.MODEL,
        content: 'try-on result',
        timestamp: Date.now(),
        mode: 'virtual-try-on',
        attachments: [
          {
            id: 'tryon-stale-result-image',
            name: 'tryon-stale-result.png',
            mimeType: 'image/png',
            url: 'blob:https://gemini.dicry.cn:18443/stale-tryon-result',
            cloudUrl: '/api/storage/local-files/tryon/stale-result.png',
            uploadStatus: 'completed',
          },
        ],
      },
    ];

    render(<VirtualTryOnView {...baseProps} messages={messages} />);

    const renderedImages = screen.getAllByTestId('cached-tryon-image');
    expect(renderedImages.map((image) => image.getAttribute('src'))).toEqual([
      'cached:/api/storage/local-files/tryon/stale-result.png',
      'cached:/api/storage/local-files/tryon/stale-result.png',
    ]);
    expect(renderedImages.map((image) => image.getAttribute('data-prefer-memory-cache'))).toEqual([
      'undefined',
      'undefined',
    ]);
  });

  it('renders file-only try-on history and active result images through CachedImage', () => {
    const file = new File(['tryon-file-only'], 'tryon-file-only.png', { type: 'image/png' });
    const messages: Message[] = [
      {
        id: 'tryon-file-only-message',
        role: Role.MODEL,
        content: 'try-on file-only result',
        timestamp: Date.now(),
        mode: 'virtual-try-on',
        attachments: [
          {
            id: 'tryon-file-only-image',
            name: 'tryon-file-only.png',
            mimeType: 'image/png',
            file,
            uploadStatus: 'pending',
          },
        ],
      },
    ];

    render(<VirtualTryOnView {...baseProps} messages={messages} />);

    const renderedImages = screen.getAllByTestId('cached-tryon-image');
    expect(renderedImages).toHaveLength(2);
    expect(renderedImages.map((image) => image.getAttribute('src'))).toEqual([
      'cached:local-blob:tryon-file-only-image',
      'cached:local-blob:tryon-file-only-image',
    ]);
    expect(renderedImages.map((image) => image.getAttribute('data-has-file'))).toEqual([
      'true',
      'true',
    ]);
  });

  it('renders uploaded person and garment previews through CachedImage', async () => {
    render(<VirtualTryOnView {...baseProps} messages={[]} />);

    const inputs = document.querySelectorAll('input[type="file"]');
    expect(inputs).toHaveLength(2);

    fireEvent.change(inputs[0], {
      target: { files: [new File(['person'], 'person.png', { type: 'image/png' })] },
    });
    fireEvent.change(inputs[1], {
      target: { files: [new File(['garment'], 'garment.png', { type: 'image/png' })] },
    });

    await waitFor(() => {
      expect(screen.getByAltText('人物图')).toHaveAttribute(
        'data-source-url',
        'data:image/png;base64,person.png'
      );
      expect(screen.getByAltText('服装图')).toHaveAttribute(
        'data-source-url',
        'data:image/png;base64,garment.png'
      );
    });
  });
});
