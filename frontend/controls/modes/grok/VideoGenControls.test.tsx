// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

vi.mock('../../../hooks/useModeControlsSchema', () => ({
  useModeControlsSchema: () => ({
    schema: {
      defaults: {
        seconds: 10,
        quality: 'high',
        size: '1280x720',
      },
      aspectRatios: [
        { label: '16:9 Landscape', value: '1280x720' },
      ],
      resolutionTiers: [
        { label: '高清 720p', value: 'high' },
      ],
      numericRanges: {
        seconds: { min: 6, max: 30, step: 1 },
      },
      videoContract: {
        extensionDurationMatrix: [
          {
            baseSeconds: '10',
            options: [
              { count: 0, label: '10s (base)', totalSeconds: 10 },
              { count: 1, label: '20s (+1 extension)', totalSeconds: 20 },
              { count: 2, label: '30s (+2 extensions)', totalSeconds: 30 },
            ],
          },
        ],
        extensionConstraints: {
          addedSeconds: 10,
          maxOutputVideoSeconds: 90,
        },
        fieldPolicies: {
          storyboardPrompt: {
            preferred: true,
          },
        },
      },
    },
    loading: false,
    error: null,
  }),
}));

vi.mock('../../../hooks/useEnhancePromptModels', () => ({
  useEnhancePromptModels: () => [
    { id: 'grok-4', name: 'Grok 4' },
    { id: 'grok-4.1-fast', name: 'Grok 4.1 Fast' },
  ],
}));

import { VideoGenControls } from './VideoGenControls';

afterEach(() => {
  cleanup();
});

describe('Grok VideoGenControls', () => {
  it('shows prompt enhancement controls for video generation', () => {
    render(
      <VideoGenControls
        providerId="grok"
        enhancePrompt={true}
        setEnhancePrompt={vi.fn()}
        enhancePromptModel=""
        setEnhancePromptModel={vi.fn()}
      />
    );

    expect(screen.getByRole('switch', { name: 'AI 增强提示词' })).toBeInTheDocument();
    expect(screen.getByLabelText('增强提示词模型')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Grok 4' })).toBeInTheDocument();
  });

  it('shows shared extension count and storyboard controls for long continuation', () => {
    const setVideoExtensionCount = vi.fn();
    const setStoryboardSegments = vi.fn();

    render(
      <VideoGenControls
        providerId="grok"
        videoSeconds="10"
        setVideoSeconds={vi.fn()}
        videoExtensionCount={2}
        setVideoExtensionCount={setVideoExtensionCount}
        storyboardSegments={['', '']}
        setStoryboardSegments={setStoryboardSegments}
      />
    );

    expect(screen.getByLabelText('延长次数')).toHaveValue('2');
    expect(screen.getByLabelText('延长后总时长')).toHaveValue('2');
    expect(screen.getByLabelText('延长 1 分镜提示词')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('延长次数'), {
      target: { value: '1' },
    });
    expect(setVideoExtensionCount).toHaveBeenCalledWith(1);

    fireEvent.change(screen.getByLabelText('延长 1 分镜提示词'), {
      target: { value: '继续保持主体动作和镜头方向' },
    });
    expect(setStoryboardSegments).toHaveBeenCalledWith(['继续保持主体动作和镜头方向', '']);
  });
});
