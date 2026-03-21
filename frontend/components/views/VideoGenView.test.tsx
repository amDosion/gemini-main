// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import { Role } from '../../types/types';
import { VideoGenView } from './VideoGenView';

vi.mock('../common/GenViewLayout', () => ({
  GenViewLayout: ({ sidebarExtraHeader, sidebar, main }: any) => (
    <div>
      <div data-testid="sidebar-extra">{sidebarExtraHeader}</div>
      <div data-testid="sidebar">{sidebar}</div>
      <div data-testid="main">{main}</div>
    </div>
  ),
}));

const useControlsStateMock = vi.fn();
vi.mock('../../hooks/useControlsState', () => ({
  useControlsState: (...args: any[]) => useControlsStateMock(...args),
}));

vi.mock('../../hooks/useModeControlsSchema', () => ({
  useModeControlsSchema: () => ({
    schema: {
      aspectRatios: [{ value: '16:9', label: '16:9' }],
      resolutionTiers: [{ value: '720p', label: '720p' }],
      paramOptions: {
        seconds: [{ value: '8', label: '8s' }],
        video_extension_count: [{ value: 0, label: '不延长' }, { value: 1, label: '延长 1 次' }],
        storyboard_shot_seconds: [{ value: 4, label: '4s / 镜头' }],
        person_generation: [{ value: 'allow_adult', label: '允许成人' }],
        subtitle_mode: [{ value: 'none', label: '无字幕' }, { value: 'vtt', label: '字幕' }],
        subtitle_language: [{ value: 'en-US', label: 'English' }],
      },
      defaults: {
        aspect_ratio: '16:9',
        resolution: '720p',
        seconds: '8',
        video_extension_count: 0,
        storyboard_shot_seconds: 4,
        generate_audio: false,
        person_generation: 'allow_adult',
        subtitle_mode: 'none',
        subtitle_language: 'en-US',
        subtitle_script: '',
        storyboard_prompt: '',
        negative_prompt: '',
        seed: 17,
        enhance_prompt: true,
      },
      videoContract: {
        fieldPolicies: {
          enhancePrompt: {
            mandatory: true,
            lockedWhenMandatory: true,
            effectiveDefault: true,
          },
          generateAudio: {
            available: false,
            forcedValue: false,
          },
          subtitleMode: {
            available: true,
            singleSidecarFormat: true,
            defaultEnabledMode: 'vtt',
            supportedValues: ['none', 'vtt'],
          },
          storyboardPrompt: {
            preferred: true,
          },
        },
        extensionDurationMatrix: [
          {
            baseSeconds: '8',
            options: [
              { count: 0, label: '8s (base)', totalSeconds: 8 },
              { count: 1, label: '15s (+1 extensions)', totalSeconds: 15 },
            ],
          },
        ],
      },
    },
    loading: false,
    error: null,
  }),
}));

vi.mock('../../coordinators/ModeControlsCoordinator', () => ({
  ModeControlsCoordinator: () => <div data-testid="video-controls" />,
}));

vi.mock('../chat/ChatEditInputArea', () => ({
  __esModule: true,
  default: () => <div data-testid="video-input" />,
}));

const useHistoryListActionsMock = vi.fn();
vi.mock('../../hooks/useHistoryListActions', () => ({
  useHistoryListActions: (...args: any[]) => useHistoryListActionsMock(...args),
}));

describe('VideoGenView history list', () => {
  const createMockControls = (overrides: Record<string, any> = {}) => ({
    aspectRatio: '16:9',
    resolution: '720p',
    videoSeconds: '8',
    videoExtensionCount: 0,
    storyboardShotSeconds: 4,
    generateAudio: false,
    personGeneration: 'allow_adult',
    subtitleMode: 'none',
    subtitleLanguage: 'en-US',
    subtitleScript: '',
    storyboardPrompt: '',
    enhancePrompt: false,
    negativePrompt: '',
    seed: -1,
    setAspectRatio: vi.fn(),
    setResolution: vi.fn(),
    setVideoSeconds: vi.fn(),
    setVideoExtensionCount: vi.fn(),
    setStoryboardShotSeconds: vi.fn(),
    setGenerateAudio: vi.fn(),
    setPersonGeneration: vi.fn(),
    setSubtitleMode: vi.fn(),
    setSubtitleLanguage: vi.fn(),
    setSubtitleScript: vi.fn(),
    setStoryboardPrompt: vi.fn(),
    setEnhancePrompt: vi.fn(),
    setNegativePrompt: vi.fn(),
    setSeed: vi.fn(),
    ...overrides,
  });

  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.stubGlobal(
      'requestAnimationFrame',
      ((cb: FrameRequestCallback) => {
        cb(0);
        return 1;
      }) as typeof requestAnimationFrame
    );
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    });
    useHistoryListActionsMock.mockImplementation(({ items }: any) => ({
      showFavoritesOnly: false,
      setShowFavoritesOnly: vi.fn(),
      filteredItems: items,
      favoriteCount: 1,
      isFavorite: (messageId: string) => messageId === 'video-msg-1',
      isFavoritePending: () => false,
      toggleFavorite: vi.fn(async () => {}),
      deleteItem: vi.fn(),
    }));
    Object.defineProperty(HTMLMediaElement.prototype, 'play', {
      configurable: true,
      value: vi.fn().mockResolvedValue(undefined),
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(HTMLElement.prototype, 'requestFullscreen', {
      configurable: true,
      value: vi.fn().mockResolvedValue(undefined),
    });
    useControlsStateMock.mockImplementation(() => createMockControls());
  });

  it('renders video history as gen-style list with hover prompt preview and action menu', async () => {
    render(
      <VideoGenView
        messages={[
          {
            id: 'video-msg-1',
            role: Role.MODEL,
            content: 'Video generated for: "A sunrise over the ocean with slow cinematic motion"',
            timestamp: Date.now(),
            attachments: [
              {
                id: 'video-1',
                url: 'https://cdn.example.com/video-1.mp4',
                mimeType: 'video/mp4',
                name: 'video-1.mp4',
              },
            ],
          } as any,
        ]}
        setAppMode={vi.fn()}
        loadingState="idle"
        onSend={vi.fn()}
        onStop={vi.fn()}
        activeModelConfig={{ id: 'veo-2.0-generate-001', name: 'Veo 2' } as any}
        providerId="google"
        sessionId="session-1"
        onDeleteMessage={vi.fn()}
      />
    );

    expect(screen.getByText('仅收藏')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('A sunrise over the ocean with slow cinematic motion')).toBeInTheDocument();

    await waitFor(() => {
      expect(document.querySelector('video')).toBeTruthy();
    });

    fireEvent.mouseEnter(screen.getByTestId('video-history-item-video-msg-1'));

    await waitFor(() => {
      expect(screen.getByText('原始提示词')).toBeInTheDocument();
      expect(screen.getByText('未返回优化后的提示词')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTitle('历史项操作'));

    await waitFor(() => {
      expect(screen.getByText('取消收藏')).toBeInTheDocument();
      expect(screen.getByText('删除')).toBeInTheDocument();
    });
  });

  it('shows persisted extension metadata in the history list and hover preview', async () => {
    render(
      <VideoGenView
        messages={[
          {
            id: 'video-msg-extension',
            role: Role.MODEL,
            content: '📝 Extended mountain drone shot',
            timestamp: Date.now(),
            continuationStrategy: 'video_extension_chain',
            videoExtensionCount: 1,
            videoExtensionApplied: 1,
            totalDurationSeconds: 15,
            subtitleMode: 'both',
            subtitleAttachmentIds: ['sub-vtt', 'sub-srt'],
            attachments: [
              {
                id: 'video-extension-1',
                url: 'https://cdn.example.com/video-extension-1.mp4',
                mimeType: 'video/mp4',
                name: 'video-extension-1.mp4',
              },
            ],
          } as any,
        ]}
        setAppMode={vi.fn()}
        loadingState="idle"
        onSend={vi.fn()}
        onStop={vi.fn()}
        activeModelConfig={{ id: 'veo-3.1-generate-preview', name: 'Veo 3.1' } as any}
        providerId="google"
        sessionId="session-1"
        onDeleteMessage={vi.fn()}
      />
    );

    expect(screen.getByText('延长 1 次')).toBeInTheDocument();
    expect(screen.getByText('总时长 15s')).toBeInTheDocument();
    expect(screen.getByText('官方延长')).toBeInTheDocument();
    expect(screen.getByText('字幕')).toBeInTheDocument();

    fireEvent.mouseEnter(screen.getByTestId('video-history-item-video-msg-extension'));

    await waitFor(() => {
      expect(screen.getByText('视频信息')).toBeInTheDocument();
    });
  });

  it('shows skeleton placeholders while generating video', () => {
    render(
      <VideoGenView
        messages={[]}
        setAppMode={vi.fn()}
        loadingState="loading"
        onSend={vi.fn()}
        onStop={vi.fn()}
        activeModelConfig={{ id: 'veo-2.0-generate-001', name: 'Veo 2' } as any}
        providerId="google"
        sessionId="session-1"
        onDeleteMessage={vi.fn()}
      />
    );

    expect(screen.getByTestId('video-main-loading-skeleton')).toBeInTheDocument();
    expect(screen.queryByTestId('video-history-loading-skeleton')).not.toBeInTheDocument();
    expect(screen.getByText('生成中...')).toBeInTheDocument();
  });

  it('supports keyboard up/down selection for video history', async () => {
    render(
      <VideoGenView
        messages={[
          {
            id: 'video-msg-1',
            role: Role.MODEL,
            content: '📝 First video prompt',
            timestamp: Date.now() - 1000,
            attachments: [
              {
                id: 'video-1',
                url: 'https://cdn.example.com/video-1.mp4',
                mimeType: 'video/mp4',
                name: 'video-1.mp4',
              },
            ],
          } as any,
          {
            id: 'video-msg-2',
            role: Role.MODEL,
            content: '📝 Second video prompt',
            timestamp: Date.now(),
            attachments: [
              {
                id: 'video-2',
                url: 'https://cdn.example.com/video-2.mp4',
                mimeType: 'video/mp4',
                name: 'video-2.mp4',
              },
            ],
          } as any,
        ]}
        setAppMode={vi.fn()}
        loadingState="idle"
        onSend={vi.fn()}
        onStop={vi.fn()}
        activeModelConfig={{ id: 'veo-2.0-generate-001', name: 'Veo 2' } as any}
        providerId="google"
        sessionId="session-1"
        onDeleteMessage={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('video-main-player')).toHaveAttribute('src', 'https://cdn.example.com/video-2.mp4');
    });

    fireEvent.keyDown(window, { key: 'ArrowDown' });

    await waitFor(() => {
      expect(screen.getByTestId('video-main-player')).toHaveAttribute('src', 'https://cdn.example.com/video-1.mp4');
    });
  });

  it('uses a real fullscreen request and supports spacebar playback toggle', async () => {
    let paused = true;
    const playMock = vi.fn().mockImplementation(async function (this: HTMLMediaElement) {
      paused = false;
      fireEvent.play(this);
      paused = true;
    });
    const pauseMock = vi.fn().mockImplementation(function (this: HTMLMediaElement) {
      paused = true;
      fireEvent.pause(this);
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'play', {
      configurable: true,
      value: playMock,
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
      configurable: true,
      value: pauseMock,
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'paused', {
      configurable: true,
      get: () => paused,
    });

    render(
      <VideoGenView
        messages={[
          {
            id: 'video-msg-1',
            role: Role.MODEL,
            content: '📝 Fullscreen test prompt',
            timestamp: Date.now(),
            attachments: [
              {
                id: 'video-1',
                url: 'https://cdn.example.com/video-1.mp4',
                mimeType: 'video/mp4',
                name: 'video-1.mp4',
              },
            ],
          } as any,
        ]}
        setAppMode={vi.fn()}
        loadingState="idle"
        onSend={vi.fn()}
        onStop={vi.fn()}
        activeModelConfig={{ id: 'veo-2.0-generate-001', name: 'Veo 2' } as any}
        providerId="google"
        sessionId="session-1"
        onDeleteMessage={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('video-main-player')).toBeInTheDocument();
    });

    fireEvent.keyDown(window, { key: ' ' });
    expect(playMock).toHaveBeenCalled();

    fireEvent.click(screen.getByLabelText('全屏播放'));
    expect(HTMLElement.prototype.requestFullscreen).toHaveBeenCalled();
  });

  it('resets video params using backend contract defaults', async () => {
    const controls = createMockControls({
      aspectRatio: '1:1',
      resolution: '4k',
      videoSeconds: '6',
      videoExtensionCount: 1,
      storyboardShotSeconds: 6,
      generateAudio: true,
      personGeneration: 'allow_all',
      subtitleMode: 'vtt',
      subtitleLanguage: 'zh-CN',
      subtitleScript: 'old subtitle',
      storyboardPrompt: 'old storyboard',
      enhancePrompt: false,
      negativePrompt: 'old negative',
      seed: 999,
    });
    useControlsStateMock.mockImplementation(() => controls);

    render(
      <VideoGenView
        messages={[]}
        setAppMode={vi.fn()}
        loadingState="idle"
        onSend={vi.fn()}
        onStop={vi.fn()}
        activeModelConfig={{ id: 'veo-3.1-generate-preview', name: 'Veo 3.1' } as any}
        providerId="google"
        sessionId="session-1"
        onDeleteMessage={vi.fn()}
      />
    );

    fireEvent.click(screen.getByTitle('重置为默认值'));

    expect(controls.setAspectRatio).toHaveBeenCalledWith('16:9');
    expect(controls.setResolution).toHaveBeenCalledWith('720p');
    expect(controls.setVideoSeconds).toHaveBeenCalledWith('8');
    expect(controls.setVideoExtensionCount).toHaveBeenCalledWith(0);
    expect(controls.setStoryboardShotSeconds).toHaveBeenCalledWith(4);
    expect(controls.setGenerateAudio).toHaveBeenCalledWith(false);
    expect(controls.setPersonGeneration).toHaveBeenCalledWith('allow_adult');
    expect(controls.setSubtitleMode).toHaveBeenCalledWith('none');
    expect(controls.setSubtitleLanguage).toHaveBeenCalledWith('en-US');
    expect(controls.setSubtitleScript).toHaveBeenCalledWith('');
    expect(controls.setStoryboardPrompt).toHaveBeenCalledWith('');
    expect(controls.setNegativePrompt).toHaveBeenCalledWith('');
    expect(controls.setSeed).toHaveBeenCalledWith(17);
    expect(controls.setEnhancePrompt).toHaveBeenCalledWith(true);
  });
});
