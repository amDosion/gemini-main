// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { VertexAIConfiguration } from './VertexAIConfiguration';

const mocks = vi.hoisted(() => ({
  request: vi.fn(),
  showSuccess: vi.fn(),
  showError: vi.fn(),
}));

vi.mock('../../../services/db', () => ({
  db: {
    request: mocks.request,
  },
}));

vi.mock('../../../contexts/ToastContext', () => ({
  useToastContext: () => ({
    showSuccess: mocks.showSuccess,
    showError: mocks.showError,
  }),
}));

describe('VertexAIConfiguration model list', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('uses high-contrast unselected cards and purpose-focused model descriptions', async () => {
    mocks.request.mockResolvedValueOnce({
      apiMode: 'vertex_ai',
      vertexAiProjectId: 'project-1',
      vertexAiLocation: 'us-central1',
      vertexAiCredentialsJson: '{}',
      savedModels: [
        {
          id: 'veo-3.1-generate-001',
          name: 'veo-3.1-generate-001',
          description: 'Google AI model: veo-3.1-generate-001',
          capabilities: { vision: false, search: false, reasoning: false, coding: false },
          contextWindow: 0,
        },
      ],
      hiddenModels: ['imagen-4.0-upscale-preview'],
    });

    render(<VertexAIConfiguration onClose={vi.fn()} />);

    const videoCard = await screen.findByTestId('vertex-model-card-veo-3.1-generate-001');
    const upscaleCard = await screen.findByTestId('vertex-model-card-imagen-4.0-upscale-preview');

    await waitFor(() => {
      expect(screen.getByText('视频生成')).toBeTruthy();
      expect(screen.getByText('图片放大')).toBeTruthy();
    });

    expect(videoCard.getAttribute('aria-pressed')).toBe('true');
    expect(upscaleCard.getAttribute('aria-pressed')).toBe('false');
    const upscaleMeta = screen.getByTestId('vertex-model-meta-imagen-4.0-upscale-preview');

    expect(upscaleMeta.className).toContain('flex');
    expect(upscaleMeta.className).toContain('items-center');
    expect(within(upscaleMeta).getByText('图片放大')).toBeTruthy();
    expect(within(upscaleMeta).getByText('未选择')).toBeTruthy();
    expect(upscaleCard.className).not.toContain('amber');
    expect(upscaleCard.className).not.toContain('opacity-60');
    expect(screen.queryByText('Google AI model: veo-3.1-generate-001')).toBeNull();
  });
});
