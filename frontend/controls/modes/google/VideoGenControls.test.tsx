// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

const enhancePromptModelsMock = vi.hoisted(() => [
  { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
  { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash Preview' },
]);

vi.mock('../../../hooks/useEnhancePromptModels', () => ({
  useEnhancePromptModels: () => enhancePromptModelsMock,
}));

import { VideoGenControls } from './VideoGenControls';

afterEach(() => {
  cleanup();
});

describe('Google VideoGenControls', () => {
  it('supports advanced prompt enhancement controls', () => {
    const setAspectRatio = vi.fn();
    const setResolution = vi.fn();
    const setVideoSeconds = vi.fn();
    const setVideoExtensionCount = vi.fn();
    const setStoryboardShotSeconds = vi.fn();
    const setGenerateAudio = vi.fn();
    const setSubtitleMode = vi.fn();
    const setSubtitleLanguage = vi.fn();
    const setSubtitleScript = vi.fn();
    const setStoryboardPrompt = vi.fn();
    const setStoryboardSegments = vi.fn();
    const setShowAdvanced = vi.fn();
    const setNegativePrompt = vi.fn();
    const setSeed = vi.fn();
    const setEnhancePrompt = vi.fn();

    const { rerender } = render(
      <VideoGenControls
        providerId="google"
        aspectRatio="16:9"
        setAspectRatio={setAspectRatio}
        resolution="720p"
        setResolution={setResolution}
        videoSeconds="8"
        setVideoSeconds={setVideoSeconds}
        videoExtensionCount={0}
        setVideoExtensionCount={setVideoExtensionCount}
        storyboardShotSeconds={4}
        setStoryboardShotSeconds={setStoryboardShotSeconds}
        generateAudio={false}
        setGenerateAudio={setGenerateAudio}
        subtitleMode="none"
        setSubtitleMode={setSubtitleMode}
        subtitleLanguage="zh-CN"
        setSubtitleLanguage={setSubtitleLanguage}
        subtitleScript=""
        setSubtitleScript={setSubtitleScript}
        storyboardPrompt=""
        setStoryboardPrompt={setStoryboardPrompt}
        storyboardSegments={[]}
        setStoryboardSegments={setStoryboardSegments}
        showAdvanced={false}
        setShowAdvanced={setShowAdvanced}
        negativePrompt=""
        setNegativePrompt={setNegativePrompt}
        seed={-1}
        setSeed={setSeed}
        enhancePrompt={false}
        setEnhancePrompt={setEnhancePrompt}
        controlsSchema={{
          defaults: {
            aspect_ratio: '16:9',
            resolution: '720p',
            seconds: '8',
            enhance_prompt: false,
            generate_audio: false,
            subtitle_mode: 'none',
            subtitle_language: 'zh-CN',
            subtitle_script: '',
            storyboard_shot_seconds: 4,
            seed: -1,
            negative_prompt: '',
          },
          aspectRatios: [{ label: '16:9 Landscape', value: '16:9' }],
          resolutionTiers: [{ label: '720p HD', value: '720p', baseResolution: '1280×720' }],
          paramOptions: {
            seconds: [{ label: '8s', value: '8' }],
            video_extension_count: [
              { label: '不延长', value: 0 },
              { label: '延长 1 次', value: 1 },
              { label: '延长 2 次', value: 2 },
            ],
            generate_audio: [{ label: '无配音', value: false }, { label: '生成音频', value: true }],
            subtitle_mode: [{ label: '无字幕', value: 'none' }, { label: '字幕', value: 'vtt' }],
            subtitle_language: [{ label: '中文', value: 'zh-CN' }, { label: 'English', value: 'en-US' }],
            storyboard_shot_seconds: [{ label: '4s / 镜头', value: 4 }, { label: '6s / 镜头', value: 6 }],
          },
          constraints: {
            video_extension_added_seconds: 7,
            max_source_video_seconds: 141,
            supports_storyboard_prompting: true,
          },
          videoContract: {
            fieldPolicies: {
              enhancePrompt: {
                mandatory: true,
                lockedWhenMandatory: true,
                effectiveDefault: true,
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
                  { count: 2, label: '22s (+2 extensions)', totalSeconds: 22 },
                ],
              },
            ],
            extensionConstraints: {
              addedSeconds: 7,
              maxOutputVideoSeconds: 141,
            },
          },
          numericRanges: {
            seed: { min: -1, max: 2147483647, step: 1 },
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    expect(screen.getAllByText('1280×720').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByText('高级参数'));
    expect(setShowAdvanced).toHaveBeenCalledWith(true);

    rerender(
      <VideoGenControls
        providerId="google"
        aspectRatio="16:9"
        setAspectRatio={setAspectRatio}
        resolution="720p"
        setResolution={setResolution}
        videoSeconds="8"
        setVideoSeconds={setVideoSeconds}
        videoExtensionCount={1}
        setVideoExtensionCount={setVideoExtensionCount}
        storyboardShotSeconds={4}
        setStoryboardShotSeconds={setStoryboardShotSeconds}
        generateAudio={false}
        setGenerateAudio={setGenerateAudio}
        subtitleMode="none"
        setSubtitleMode={setSubtitleMode}
        subtitleLanguage="zh-CN"
        setSubtitleLanguage={setSubtitleLanguage}
        subtitleScript=""
        setSubtitleScript={setSubtitleScript}
        storyboardPrompt=""
        setStoryboardPrompt={setStoryboardPrompt}
        storyboardSegments={[]}
        setStoryboardSegments={setStoryboardSegments}
        showAdvanced={true}
        setShowAdvanced={setShowAdvanced}
        negativePrompt=""
        setNegativePrompt={setNegativePrompt}
        seed={-1}
        setSeed={setSeed}
        enhancePrompt={false}
        setEnhancePrompt={setEnhancePrompt}
        controlsSchema={{
          defaults: {
            aspect_ratio: '16:9',
            resolution: '720p',
            seconds: '8',
            enhance_prompt: false,
            generate_audio: false,
            subtitle_mode: 'none',
            subtitle_language: 'zh-CN',
            subtitle_script: '',
            storyboard_shot_seconds: 4,
            seed: -1,
            negative_prompt: '',
          },
          aspectRatios: [{ label: '16:9 Landscape', value: '16:9' }],
          resolutionTiers: [{ label: '720p HD', value: '720p', baseResolution: '1280×720' }],
          paramOptions: {
            seconds: [{ label: '8s', value: '8' }],
            video_extension_count: [
              { label: '不延长', value: 0 },
              { label: '延长 1 次', value: 1 },
              { label: '延长 2 次', value: 2 },
            ],
            generate_audio: [{ label: '无配音', value: false }, { label: '生成音频', value: true }],
            subtitle_mode: [{ label: '无字幕', value: 'none' }, { label: '字幕', value: 'vtt' }],
            subtitle_language: [{ label: '中文', value: 'zh-CN' }, { label: 'English', value: 'en-US' }],
            storyboard_shot_seconds: [{ label: '4s / 镜头', value: 4 }, { label: '6s / 镜头', value: 6 }],
          },
          constraints: {
            video_extension_added_seconds: 7,
            max_source_video_seconds: 141,
            supports_storyboard_prompting: true,
          },
          videoContract: {
            fieldPolicies: {
              enhancePrompt: {
                mandatory: true,
                lockedWhenMandatory: true,
                effectiveDefault: true,
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
                  { count: 2, label: '22s (+2 extensions)', totalSeconds: 22 },
                ],
              },
            ],
            extensionConstraints: {
              addedSeconds: 7,
              maxOutputVideoSeconds: 141,
            },
          },
          numericRanges: {
            seed: { min: -1, max: 2147483647, step: 1 },
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    fireEvent.change(screen.getByPlaceholderText('不想在视频中出现的内容...'), {
      target: { value: 'low quality, watermark' },
    });
    expect(setNegativePrompt).toHaveBeenCalledWith('low quality, watermark');

    fireEvent.change(screen.getByPlaceholderText('随机 (-1)'), {
      target: { value: '42' },
    });
    expect(setSeed).toHaveBeenCalledWith(42);

    fireEvent.click(screen.getByRole('switch', { name: 'AI 增强提示词' }));
    expect(setEnhancePrompt).toHaveBeenCalledWith(true);

    fireEvent.change(screen.getByLabelText('延长次数'), {
      target: { value: '2' },
    });
    expect(setVideoExtensionCount).toHaveBeenCalledWith(2);

    fireEvent.change(screen.getByLabelText('生成音频'), {
      target: { value: 'true' },
    });
    expect(setGenerateAudio).toHaveBeenCalledWith(true);
    expect(screen.queryByLabelText('人物生成')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('switch', { name: '字幕' }));
    expect(setSubtitleMode).toHaveBeenCalledWith('vtt');

    fireEvent.change(screen.getByLabelText('分镜镜头时长'), {
      target: { value: '6' },
    });
    expect(setStoryboardShotSeconds).toHaveBeenCalledWith(6);

    rerender(
      <VideoGenControls
        providerId="google"
        aspectRatio="16:9"
        setAspectRatio={setAspectRatio}
        resolution="720p"
        setResolution={setResolution}
        videoSeconds="8"
        setVideoSeconds={setVideoSeconds}
        videoExtensionCount={2}
        setVideoExtensionCount={setVideoExtensionCount}
        storyboardShotSeconds={4}
        setStoryboardShotSeconds={setStoryboardShotSeconds}
        generateAudio={true}
        setGenerateAudio={setGenerateAudio}
        subtitleMode="none"
        setSubtitleMode={setSubtitleMode}
        subtitleLanguage="zh-CN"
        setSubtitleLanguage={setSubtitleLanguage}
        subtitleScript=""
        setSubtitleScript={setSubtitleScript}
        storyboardPrompt=""
        setStoryboardPrompt={setStoryboardPrompt}
        storyboardSegments={[]}
        setStoryboardSegments={setStoryboardSegments}
        showAdvanced={true}
        setShowAdvanced={setShowAdvanced}
        negativePrompt=""
        setNegativePrompt={setNegativePrompt}
        seed={-1}
        setSeed={setSeed}
        enhancePrompt={false}
        setEnhancePrompt={setEnhancePrompt}
        controlsSchema={{
          defaults: {
            aspect_ratio: '16:9',
            resolution: '720p',
            seconds: '8',
            enhance_prompt: false,
            generate_audio: true,
            subtitle_mode: 'none',
            subtitle_language: 'zh-CN',
            subtitle_script: '',
            storyboard_shot_seconds: 4,
            seed: -1,
            negative_prompt: '',
          },
          aspectRatios: [{ label: '16:9 Landscape', value: '16:9' }],
          resolutionTiers: [{ label: '720p HD', value: '720p', baseResolution: '1280×720' }],
          paramOptions: {
            seconds: [{ label: '8s', value: '8' }],
            generate_audio: [{ label: '无音频', value: false }, { label: '生成音频和口播', value: true }],
            subtitle_mode: [{ label: '无字幕', value: 'none' }, { label: '字幕', value: 'vtt' }],
            subtitle_language: [{ label: '中文', value: 'zh-CN' }, { label: 'English', value: 'en-US' }],
            storyboard_shot_seconds: [{ label: '4s / 镜头', value: 4 }, { label: '6s / 镜头', value: 6 }],
          },
          videoContract: {
            fieldPolicies: {
              enhancePrompt: {
                mandatory: true,
                lockedWhenMandatory: true,
                effectiveDefault: true,
              },
              generateAudio: {
                available: true,
                forcedValue: null,
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
                  { count: 2, label: '22s (+2 extensions)', totalSeconds: 22 },
                ],
              },
            ],
            extensionConstraints: {
              addedSeconds: 7,
              maxOutputVideoSeconds: 141,
            },
          },
          numericRanges: {
            seed: { min: -1, max: 2147483647, step: 1 },
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    expect(screen.queryByLabelText('口播脚本')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('分镜提示词')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('延长 1 分镜提示词'), {
      target: { value: 'Macro product close-up continuation' },
    });
    expect(setStoryboardSegments).toHaveBeenCalledWith(['Macro product close-up continuation']);
    expect(setStoryboardPrompt).not.toHaveBeenCalled();
  });

  it('lets video prompt enhancement choose the same extra model pool as chat-edit', () => {
    const setEnhancePromptModel = vi.fn();

    render(
      <VideoGenControls
        providerId="google"
        showAdvanced={true}
        setShowAdvanced={vi.fn()}
        enhancePrompt={true}
        setEnhancePrompt={vi.fn()}
        enhancePromptModel=""
        setEnhancePromptModel={setEnhancePromptModel}
        controlsSchema={{
          defaults: {
            aspect_ratio: '16:9',
            resolution: '720p',
            seconds: '8',
            enhance_prompt: false,
          },
          aspectRatios: [{ label: '16:9 Landscape', value: '16:9' }],
          resolutionTiers: [{ label: '720p HD', value: '720p', baseResolution: '1280×720' }],
          paramOptions: {
            seconds: [{ label: '8s', value: '8' }],
          },
          videoContract: {
            fieldPolicies: {
              enhancePrompt: {
                mandatory: false,
                lockedWhenMandatory: false,
                effectiveDefault: false,
              },
              storyboardPrompt: {
                preferred: false,
              },
            },
            extensionDurationMatrix: [],
            extensionConstraints: {},
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    expect(screen.getByRole('option', { name: 'Gemini 2.5 Flash' })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('增强提示词模型'), {
      target: { value: 'gemini-3-flash-preview' },
    });
    expect(setEnhancePromptModel).toHaveBeenCalledWith('gemini-3-flash-preview');
  });

  it('shows local video prompt enhancement for OpenAI outside advanced controls', () => {
    render(
      <VideoGenControls
        providerId="openai"
        aspectRatio="16:9"
        setAspectRatio={vi.fn()}
        resolution="1K"
        setResolution={vi.fn()}
        videoSeconds="4"
        setVideoSeconds={vi.fn()}
        videoInputStrategy="text_to_video"
        setVideoInputStrategy={vi.fn()}
        showAdvanced={false}
        setShowAdvanced={vi.fn()}
        enhancePrompt={true}
        setEnhancePrompt={vi.fn()}
        enhancePromptModel=""
        setEnhancePromptModel={vi.fn()}
        controlsSchema={{
          provider: 'openai',
          mode: 'video-gen',
          modelId: 'sora-2-pro',
          defaults: {
            aspect_ratio: '16:9',
            resolution: '1K',
            seconds: '4',
            video_input_strategy: 'text_to_video',
            enhance_prompt: true,
          },
          constraints: {
            unsupported_params: [
              'negative_prompt',
              'seed',
              'generate_audio',
              'subtitle_mode',
              'subtitle_language',
              'subtitle_script',
              'storyboard_prompt',
              'storyboard_segments',
            ],
          },
          aspectRatios: [{ label: '16:9 Landscape', value: '16:9' }],
          resolutionTiers: [{ label: '720p (HD)', value: '1K', baseResolution: '1280×720' }],
          paramOptions: {
            seconds: [{ label: '4s', value: '4' }],
          },
          videoContract: {
            inputStrategies: [
              { id: 'text_to_video', label: '文生视频', requires: [], allows: [] },
            ],
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    expect(screen.getByRole('switch', { name: 'AI 增强提示词' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Gemini 2.5 Flash' })).toBeInTheDocument();
  });

  it('shows Tongyi video prompt enhancement outside advanced controls when supported by schema', () => {
    render(
      <VideoGenControls
        providerId="tongyi"
        aspectRatio="16:9"
        setAspectRatio={vi.fn()}
        resolution="1080p"
        setResolution={vi.fn()}
        videoSeconds="5"
        setVideoSeconds={vi.fn()}
        videoInputStrategy="text_to_video"
        setVideoInputStrategy={vi.fn()}
        showAdvanced={false}
        setShowAdvanced={vi.fn()}
        enhancePrompt={true}
        setEnhancePrompt={vi.fn()}
        enhancePromptModel=""
        setEnhancePromptModel={vi.fn()}
        controlsSchema={{
          provider: 'tongyi',
          mode: 'video-gen',
          modelId: 'wan2.7-t2v',
          defaults: {
            aspect_ratio: '16:9',
            resolution: '1080p',
            seconds: '5',
            video_input_strategy: 'text_to_video',
            enhance_prompt: true,
          },
          constraints: {
            unsupported_params: ['negative_prompt'],
          },
          aspectRatios: [{ label: '16:9 Landscape', value: '16:9' }],
          resolutionTiers: [{ label: '1080p Full HD', value: '1080p', baseResolution: '1920×1080' }],
          paramOptions: {
            seconds: [{ label: '5s', value: '5' }],
          },
          videoContract: {
            inputStrategies: [
              { id: 'text_to_video', label: '文生视频', requires: [], allows: [] },
            ],
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    expect(screen.getByRole('switch', { name: 'AI 增强提示词' })).toBeInTheDocument();
    expect(screen.getByLabelText('增强提示词模型')).toBeInTheDocument();
  });

  it('hides fields declared unsupported by the video control schema', () => {
    const { container } = render(
      <VideoGenControls
        providerId="tongyi"
        showAdvanced={true}
        setShowAdvanced={vi.fn()}
        aspectRatio="16:9"
        setAspectRatio={vi.fn()}
        resolution="1080p"
        setResolution={vi.fn()}
        videoSeconds="5"
        setVideoSeconds={vi.fn()}
        negativePrompt=""
        setNegativePrompt={vi.fn()}
        seed={-1}
        setSeed={vi.fn()}
        enhancePrompt={true}
        setEnhancePrompt={vi.fn()}
        controlsSchema={{
          defaults: {
            resolution: '1080p',
            seconds: '5',
            enhance_prompt: true,
          },
          aspectRatios: [
            { label: '16:9 Landscape', value: '16:9' },
            { label: '9:16 Portrait', value: '9:16' },
          ],
          resolutionTiers: [
            { label: '1080p Full HD', value: '1080p', baseResolution: '保持输入素材近似比例' },
          ],
          paramOptions: {
            seconds: [{ label: '5s', value: '5' }],
          },
          constraints: {
            unsupported_params: ['aspect_ratio', 'negative_prompt', 'prompt_extend'],
          },
          numericRanges: {
            seed: { min: -1, max: 2147483647, step: 1 },
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    const view = within(container);
    expect(view.queryByText('视频比例')).not.toBeInTheDocument();
    expect(view.queryByText('负向提示词')).not.toBeInTheDocument();
    expect(view.queryByRole('switch', { name: 'AI 增强提示词' })).not.toBeInTheDocument();
    expect(view.getAllByText('保持输入素材近似比例').length).toBeGreaterThan(0);
  });

  it('does not show a config error while the selected video model/schema is not ready', () => {
    render(
      <VideoGenControls
        providerId="openai"
        controlsSchema={null}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    expect(screen.queryByText(/视频参数配置加载失败/)).not.toBeInTheDocument();
  });

  it('applies model-specific defaults when the video schema changes', async () => {
    const setAspectRatio = vi.fn();
    const setResolution = vi.fn();
    const setVideoSeconds = vi.fn();

    render(
      <VideoGenControls
        providerId="tongyi"
        aspectRatio="16:9"
        setAspectRatio={setAspectRatio}
        resolution="720p"
        setResolution={setResolution}
        videoSeconds="8"
        setVideoSeconds={setVideoSeconds}
        controlsSchema={{
          provider: 'tongyi',
          mode: 'video-gen',
          modelId: 'wan2.7-videoedit',
          defaults: {
            aspect_ratio: 'source',
            resolution: '1080p',
            seconds: '0',
          },
          aspectRatios: [
            { label: '跟随输入视频', value: 'source' },
            { label: '16:9 Landscape', value: '16:9' },
          ],
          resolutionTiers: [
            { label: '720p HD', value: '720p', baseResolution: '1280×720' },
            { label: '1080p Full HD', value: '1080p', baseResolution: '1920×1080' },
          ],
          paramOptions: {
            seconds: [
              { label: '保持原时长', value: '0' },
              { label: '8s', value: '8' },
            ],
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    await waitFor(() => {
      expect(setAspectRatio).toHaveBeenCalledWith('source');
      expect(setResolution).toHaveBeenCalledWith('1080p');
      expect(setVideoSeconds).toHaveBeenCalledWith('0');
    });
  });

  it('renders schema-driven Tongyi video input strategies', () => {
    const setVideoInputStrategy = vi.fn();

    render(
      <VideoGenControls
        providerId="tongyi"
        aspectRatio="16:9"
        setAspectRatio={vi.fn()}
        resolution="1080p"
        setResolution={vi.fn()}
        videoSeconds="5"
        setVideoSeconds={vi.fn()}
        videoInputStrategy="video_continuation"
        setVideoInputStrategy={setVideoInputStrategy}
        showAdvanced={false}
        setShowAdvanced={vi.fn()}
        negativePrompt=""
        setNegativePrompt={vi.fn()}
        seed={-1}
        setSeed={vi.fn()}
        enhancePrompt={true}
        setEnhancePrompt={vi.fn()}
        controlsSchema={{
          provider: 'tongyi',
          mode: 'video-gen',
          modelId: 'wan2.7-i2v',
          defaults: {
            resolution: '1080p',
            seconds: '5',
            video_input_strategy: 'first_frame_to_video',
            enhance_prompt: true,
          },
          constraints: {
            unsupported_params: ['aspect_ratio'],
          },
          resolutionTiers: [
            { label: '720p HD', value: '720p', baseResolution: '保持输入素材近似比例' },
            { label: '1080p Full HD', value: '1080p', baseResolution: '保持输入素材近似比例' },
          ],
          paramOptions: {
            seconds: [{ label: '5s', value: '5' }],
          },
          videoContract: {
            inputStrategies: [
              {
                id: 'first_frame_to_video',
                label: '首帧生视频',
                requires: ['source_image'],
                allows: ['driving_audio'],
              },
              {
                id: 'first_last_frame_to_video',
                label: '首尾帧生成',
                requires: ['source_image', 'last_frame_image'],
                allows: ['driving_audio'],
              },
              {
                id: 'video_continuation',
                label: '视频续写',
                requires: ['source_video'],
                allows: ['driving_audio'],
              },
            ],
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    expect(screen.getByText('子模式')).toBeInTheDocument();
    expect(screen.getByLabelText('子模式')).toHaveValue('first_frame_to_video');
    expect(screen.queryByRole('option', { name: '视频延长（视频）' })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('子模式'), {
      target: { value: 'first_last_frame_to_video' },
    });

    expect(setVideoInputStrategy).toHaveBeenCalledWith('first_last_frame_to_video');
  });

  it('keeps the submode selector visible for single-service video models', () => {
    render(
      <VideoGenControls
        providerId="tongyi"
        aspectRatio="16:9"
        setAspectRatio={vi.fn()}
        resolution="1080p"
        setResolution={vi.fn()}
        videoSeconds="5"
        setVideoSeconds={vi.fn()}
        videoInputStrategy="text_to_video"
        setVideoInputStrategy={vi.fn()}
        showAdvanced={false}
        setShowAdvanced={vi.fn()}
        controlsSchema={{
          provider: 'tongyi',
          mode: 'video-gen',
          modelId: 'wan2.7-t2v',
          defaults: {
            aspect_ratio: '16:9',
            resolution: '1080p',
            seconds: '5',
            video_input_strategy: 'text_to_video',
          },
          aspectRatios: [{ label: '16:9 Landscape', value: '16:9' }],
          resolutionTiers: [
            { label: '1080p Full HD', value: '1080p', baseResolution: '1920×1080' },
          ],
          paramOptions: {
            seconds: [{ label: '5s', value: '5' }],
          },
          videoContract: {
            inputStrategies: [
              {
                id: 'text_to_video',
                label: '文生视频',
                requires: [],
                allows: [],
              },
            ],
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    expect(screen.getByText('子模式')).toBeInTheDocument();
    expect(screen.getByLabelText('子模式')).toHaveValue('text_to_video');
    expect(screen.getByRole('option', { name: '文生视频（无需素材）' })).toBeInTheDocument();
  });

  it('lets Tongyi submode selection switch to the matching independent video model', () => {
    const setVideoInputStrategy = vi.fn();
    const onModelSelect = vi.fn();

    render(
      <VideoGenControls
        providerId="tongyi"
        currentModel={{
          id: 'wan2.7-t2v',
          name: 'Wan 2.7 T2V',
          description: '',
          capabilities: { vision: true, search: false, reasoning: false, coding: false },
        }}
        availableModels={[
          {
            id: 'wan2.7-t2v',
            name: 'Wan 2.7 T2V',
            description: '',
            capabilities: { vision: true, search: false, reasoning: false, coding: false },
          },
          {
            id: 'wan2.7-i2v',
            name: 'Wan 2.7 I2V',
            description: '',
            capabilities: { vision: true, search: false, reasoning: false, coding: false },
          },
          {
            id: 'wan2.7-r2v',
            name: 'Wan 2.7 R2V',
            description: '',
            capabilities: { vision: true, search: false, reasoning: false, coding: false },
          },
          {
            id: 'wan2.7-videoedit',
            name: 'Wan 2.7 Video Edit',
            description: '',
            capabilities: { vision: true, search: false, reasoning: false, coding: false },
          },
        ]}
        onModelSelect={onModelSelect}
        aspectRatio="16:9"
        setAspectRatio={vi.fn()}
        resolution="1080p"
        setResolution={vi.fn()}
        videoSeconds="5"
        setVideoSeconds={vi.fn()}
        videoInputStrategy="text_to_video"
        setVideoInputStrategy={setVideoInputStrategy}
        showAdvanced={false}
        setShowAdvanced={vi.fn()}
        controlsSchema={{
          provider: 'tongyi',
          mode: 'video-gen',
          modelId: 'wan2.7-t2v',
          defaults: {
            aspect_ratio: '16:9',
            resolution: '1080p',
            seconds: '5',
            video_input_strategy: 'text_to_video',
          },
          aspectRatios: [{ label: '16:9 Landscape', value: '16:9' }],
          resolutionTiers: [
            { label: '1080p Full HD', value: '1080p', baseResolution: '1920×1080' },
          ],
          paramOptions: {
            seconds: [{ label: '5s', value: '5' }],
          },
          videoContract: {
            inputStrategies: [
              {
                id: 'text_to_video',
                label: '文生视频',
                requires: [],
                allows: [],
              },
            ],
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    expect(screen.getByRole('option', { name: '图生视频（首帧）' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: '视频延长（视频）' })).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: '视频编辑（视频）' })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('子模式'), {
      target: { value: 'video_edit' },
    });

    expect(setVideoInputStrategy).toHaveBeenCalledWith('video_edit');
    expect(onModelSelect).toHaveBeenCalledWith('wan2.7-videoedit');
  });

  it('renders OpenAI Sora video submodes without a catalog error', () => {
    render(
      <VideoGenControls
        providerId="openai"
        aspectRatio="16:9"
        setAspectRatio={vi.fn()}
        resolution="1K"
        setResolution={vi.fn()}
        videoSeconds="4"
        setVideoSeconds={vi.fn()}
        videoInputStrategy="text_to_video"
        setVideoInputStrategy={vi.fn()}
        showAdvanced={true}
        setShowAdvanced={vi.fn()}
        negativePrompt=""
        setNegativePrompt={vi.fn()}
        seed={-1}
        setSeed={vi.fn()}
        enhancePrompt={false}
        setEnhancePrompt={vi.fn()}
        controlsSchema={{
          provider: 'openai',
          mode: 'video-gen',
          modelId: 'sora-2-pro',
          defaults: {
            aspect_ratio: '16:9',
            resolution: '1K',
            seconds: '4',
            video_input_strategy: 'text_to_video',
          },
          constraints: {
            unsupported_params: [
              'negative_prompt',
              'seed',
              'prompt_extend',
              'enhance_prompt',
              'generate_audio',
              'subtitle_mode',
              'subtitle_language',
              'subtitle_script',
              'storyboard_prompt',
              'storyboard_segments',
            ],
          },
          aspectRatios: [
            { label: '16:9 Landscape', value: '16:9' },
            { label: '9:16 Portrait', value: '9:16' },
          ],
          resolutionTiers: [
            { label: '720p (HD)', value: '1K', baseResolution: '1280×720' },
            { label: '1792×1024', value: '2K', baseResolution: '1792×1024' },
          ],
          paramOptions: {
            seconds: [
              { label: '4s', value: '4' },
              { label: '8s', value: '8' },
              { label: '12s', value: '12' },
            ],
          },
          videoContract: {
            runtimeApiMode: 'openai_videos',
            inputStrategies: [
              { id: 'text_to_video', label: '文生视频', requires: [], allows: [] },
              { id: 'image_to_video', label: '图生视频', requires: ['source_image'], allows: [] },
              { id: 'video_extension', label: '视频延长', requires: ['source_video'], allows: [] },
              { id: 'video_edit', label: '视频编辑', requires: ['source_video'], allows: [] },
            ],
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    expect(screen.queryByText(/视频参数配置加载失败/)).not.toBeInTheDocument();
    expect(screen.getByText('子模式')).toBeInTheDocument();
    expect(screen.getByLabelText('子模式')).toHaveValue('text_to_video');
    expect(screen.getByRole('option', { name: '文生视频（无需素材）' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '图生视频（首帧）' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: '视频延长（视频）' })).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: '视频编辑（视频）' })).toBeInTheDocument();
    expect(screen.queryByText('负向提示词')).not.toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'AI 增强提示词' })).toBeInTheDocument();
  });

  it('shows extension as an independent switch instead of a submode', () => {
    const setVideoExtensionCount = vi.fn();
    const baseProps = {
      providerId: 'google',
      aspectRatio: '16:9',
      setAspectRatio: vi.fn(),
      resolution: '720p',
      setResolution: vi.fn(),
      videoSeconds: '8',
      setVideoSeconds: vi.fn(),
      videoExtensionCount: 0,
      setVideoExtensionCount,
      showAdvanced: false,
      setShowAdvanced: vi.fn(),
      controlsSchema: {
        provider: 'google',
        mode: 'video-gen',
        modelId: 'veo-3.1-generate-preview',
        defaults: {
          aspect_ratio: '16:9',
          resolution: '720p',
          seconds: '8',
          video_input_strategy: 'text_to_video',
        },
        aspectRatios: [{ label: '16:9 Landscape', value: '16:9' }],
        resolutionTiers: [{ label: '720p HD', value: '720p', baseResolution: '1280×720' }],
        paramOptions: {
          seconds: [{ label: '8s', value: '8' }],
        },
        videoContract: {
          inputStrategies: [
            { id: 'text_to_video', label: '文生视频', requires: [], allows: [] },
            { id: 'video_extension', label: '视频延长', requires: ['source_video'], allows: [] },
          ],
          extensionDurationMatrix: [
            {
              baseSeconds: '8',
              options: [
                { count: 0, label: '8s (base)', totalSeconds: 8 },
                { count: 1, label: '15s (+1 extensions)', totalSeconds: 15 },
              ],
            },
          ],
          extensionConstraints: {
            addedSeconds: 7,
            maxOutputVideoSeconds: 37,
          },
        },
      } as any,
      controlsSchemaLoading: false,
      controlsSchemaError: null,
    };

    const { rerender } = render(
      <VideoGenControls
        {...baseProps}
        videoInputStrategy="text_to_video"
        setVideoInputStrategy={vi.fn()}
      />
    );

    expect(screen.queryByLabelText('延长次数')).not.toBeInTheDocument();
    expect(screen.getByRole('switch', { name: '延长视频' })).toHaveAttribute('aria-checked', 'false');
    expect(screen.queryByRole('option', { name: '视频延长（视频）' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('switch', { name: '延长视频' }));
    expect(setVideoExtensionCount).toHaveBeenCalledWith(1);

    rerender(
      <VideoGenControls
        {...baseProps}
        videoInputStrategy="video_extension"
        videoExtensionCount={1}
        setVideoInputStrategy={vi.fn()}
      />
    );

    expect(screen.getByLabelText('延长次数')).toBeInTheDocument();
  });

  it('shows Gemini-style extension count and storyboard controls for Tongyi as an add-on', () => {
    const setVideoSeconds = vi.fn();
    const setVideoExtensionCount = vi.fn();
    const setStoryboardSegments = vi.fn();

    render(
      <VideoGenControls
        providerId="tongyi"
        currentModel={{
          id: 'wan2.7-i2v',
          name: 'Wan 2.7 I2V',
          description: '',
          capabilities: { vision: true, search: false, reasoning: false, coding: false },
        }}
        availableModels={[
          {
            id: 'wan2.7-i2v',
            name: 'Wan 2.7 I2V',
            description: '',
            capabilities: { vision: true, search: false, reasoning: false, coding: false },
          },
        ]}
        aspectRatio="16:9"
        setAspectRatio={vi.fn()}
        resolution="1080p"
        setResolution={vi.fn()}
        videoSeconds="5"
        setVideoSeconds={setVideoSeconds}
        videoInputStrategy="first_frame_to_video"
        setVideoInputStrategy={vi.fn()}
        videoExtensionCount={2}
        setVideoExtensionCount={setVideoExtensionCount}
        storyboardSegments={['', '']}
        setStoryboardSegments={setStoryboardSegments}
        showAdvanced={true}
        setShowAdvanced={vi.fn()}
        controlsSchema={{
          provider: 'tongyi',
          mode: 'video-gen',
          modelId: 'wan2.7-i2v',
          defaults: {
            resolution: '1080p',
            seconds: '5',
            video_input_strategy: 'first_frame_to_video',
          },
          constraints: {
            unsupported_params: ['aspect_ratio'],
          },
          resolutionTiers: [
            { label: '720p HD', value: '720p', baseResolution: '保持输入素材近似比例' },
            { label: '1080p Full HD', value: '1080p', baseResolution: '保持输入素材近似比例' },
          ],
          paramOptions: {
            seconds: [
              { label: '5s', value: '5' },
              { label: '10s', value: '10' },
              { label: '15s', value: '15' },
            ],
          },
          videoContract: {
            inputStrategies: [
              {
                id: 'first_frame_to_video',
                label: '图生视频',
                requires: ['source_image'],
                allows: [],
              },
              {
                id: 'video_continuation',
                label: '视频延长',
                requires: ['source_video'],
                allows: [],
              },
            ],
            extensionDurationMatrix: [
              {
                baseSeconds: '5',
                options: [
                  { count: 0, label: '5s (base)', totalSeconds: 5 },
                  { count: 1, label: '10s (+1 extension)', totalSeconds: 10 },
                  { count: 2, label: '15s (+2 extensions)', totalSeconds: 15 },
                ],
              },
            ],
            extensionConstraints: {
              addedSeconds: 5,
              maxOutputVideoSeconds: 45,
            },
            fieldPolicies: {
              storyboardPrompt: {
                preferred: true,
              },
            },
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    expect(screen.getByText('视频延长')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: '延长视频' })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByLabelText('延长次数')).toHaveValue('2');
    expect(screen.getByLabelText('延长后总时长')).toHaveValue('2');
    expect(screen.queryByLabelText('续写时长')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('延长次数'), {
      target: { value: '1' },
    });
    expect(setVideoExtensionCount).toHaveBeenCalledWith(1);

    fireEvent.change(screen.getByLabelText('延长 1 分镜提示词'), {
      target: { value: '从上一段尾帧继续推进镜头' },
    });
    expect(setStoryboardSegments).toHaveBeenCalledWith(['从上一段尾帧继续推进镜头', '']);
  });

  it('keeps extension available when the active video submode defaults to keep original duration', () => {
    const setVideoSeconds = vi.fn();
    const setVideoExtensionCount = vi.fn();

    render(
      <VideoGenControls
        providerId="tongyi"
        currentModel={{
          id: 'wan2.7-videoedit',
          name: 'Wan 2.7 Video Edit',
          description: '',
          capabilities: { vision: true, search: false, reasoning: false, coding: false },
        }}
        availableModels={[
          {
            id: 'wan2.7-i2v',
            name: 'Wan 2.7 I2V',
            description: '',
            capabilities: { vision: true, search: false, reasoning: false, coding: false },
          },
          {
            id: 'wan2.7-videoedit',
            name: 'Wan 2.7 Video Edit',
            description: '',
            capabilities: { vision: true, search: false, reasoning: false, coding: false },
          },
        ]}
        aspectRatio="source"
        setAspectRatio={vi.fn()}
        resolution="720p"
        setResolution={vi.fn()}
        videoSeconds="0"
        setVideoSeconds={setVideoSeconds}
        videoInputStrategy="video_edit"
        setVideoInputStrategy={vi.fn()}
        videoExtensionCount={0}
        setVideoExtensionCount={setVideoExtensionCount}
        storyboardSegments={[]}
        setStoryboardSegments={vi.fn()}
        showAdvanced={false}
        setShowAdvanced={vi.fn()}
        controlsSchema={{
          provider: 'tongyi',
          mode: 'video-gen',
          modelId: 'wan2.7-videoedit',
          defaults: {
            resolution: '720p',
            seconds: '0',
            video_input_strategy: 'video_edit',
          },
          constraints: {
            unsupported_params: ['aspect_ratio'],
          },
          resolutionTiers: [
            { label: '720p HD', value: '720p', baseResolution: '保持输入素材近似比例' },
          ],
          paramOptions: {
            seconds: [
              { label: '保持原时长', value: '0' },
              { label: '5s', value: '5' },
            ],
          },
          videoContract: {
            inputStrategies: [
              {
                id: 'video_edit',
                label: '视频编辑',
                requires: ['source_video'],
                allows: [],
              },
            ],
            extensionDurationMatrix: [
              {
                baseSeconds: '5',
                options: [
                  { count: 0, label: '5s (base)', totalSeconds: 5 },
                  { count: 1, label: '10s (+1 extension)', totalSeconds: 10 },
                ],
              },
            ],
            extensionConstraints: {
              maxExtensionCount: 1,
              maxOutputVideoSeconds: 45,
            },
            fieldPolicies: {
              storyboardPrompt: {
                preferred: true,
              },
            },
          },
        } as any}
        controlsSchemaLoading={false}
        controlsSchemaError={null}
      />
    );

    const extensionSwitch = screen.getByRole('switch', { name: '延长视频' });
    expect(extensionSwitch).toHaveAttribute('aria-checked', 'false');
    expect(screen.queryByLabelText('延长次数')).not.toBeInTheDocument();

    fireEvent.click(extensionSwitch);

    expect(setVideoSeconds).toHaveBeenCalledWith('5');
    expect(setVideoExtensionCount).toHaveBeenCalledWith(1);
  });
});
