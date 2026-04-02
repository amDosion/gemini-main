// @vitest-environment jsdom
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import { VideoGenControls } from './VideoGenControls';

describe('Google VideoGenControls', () => {
  it('supports advanced prompt enhancement controls', () => {
    const setAspectRatio = vi.fn();
    const setResolution = vi.fn();
    const setVideoSeconds = vi.fn();
    const setVideoExtensionCount = vi.fn();
    const setStoryboardShotSeconds = vi.fn();
    const setGenerateAudio = vi.fn();
    const setPersonGeneration = vi.fn();
    const setSubtitleMode = vi.fn();
    const setSubtitleLanguage = vi.fn();
    const setSubtitleScript = vi.fn();
    const setStoryboardPrompt = vi.fn();
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
        personGeneration="allow_adult"
        setPersonGeneration={setPersonGeneration}
        subtitleMode="none"
        setSubtitleMode={setSubtitleMode}
        subtitleLanguage="zh-CN"
        setSubtitleLanguage={setSubtitleLanguage}
        subtitleScript=""
        setSubtitleScript={setSubtitleScript}
        storyboardPrompt=""
        setStoryboardPrompt={setStoryboardPrompt}
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
            person_generation: 'allow_adult',
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
            person_generation: [{ label: '允许成人', value: 'allow_adult' }, { label: '允许所有人', value: 'allow_all' }],
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
        videoExtensionCount={0}
        setVideoExtensionCount={setVideoExtensionCount}
        storyboardShotSeconds={4}
        setStoryboardShotSeconds={setStoryboardShotSeconds}
        generateAudio={false}
        setGenerateAudio={setGenerateAudio}
        personGeneration="allow_adult"
        setPersonGeneration={setPersonGeneration}
        subtitleMode="none"
        setSubtitleMode={setSubtitleMode}
        subtitleLanguage="zh-CN"
        setSubtitleLanguage={setSubtitleLanguage}
        subtitleScript=""
        setSubtitleScript={setSubtitleScript}
        storyboardPrompt=""
        setStoryboardPrompt={setStoryboardPrompt}
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
            person_generation: 'allow_adult',
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
            person_generation: [{ label: '允许成人', value: 'allow_adult' }, { label: '允许所有人', value: 'allow_all' }],
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

    fireEvent.change(screen.getByLabelText('人物生成'), {
      target: { value: 'allow_all' },
    });
    expect(setPersonGeneration).toHaveBeenCalledWith('allow_all');

    fireEvent.click(screen.getByRole('switch', { name: '字幕' }));
    expect(setSubtitleMode).toHaveBeenCalledWith('vtt');

    fireEvent.change(screen.getByLabelText('分镜镜头时长'), {
      target: { value: '6' },
    });
    expect(setStoryboardShotSeconds).toHaveBeenCalledWith(6);

    fireEvent.change(screen.getByLabelText('分镜提示词'), {
      target: { value: 'Shot 1: Hero reveal with text Double-Layer Lace' },
    });
    expect(setStoryboardPrompt).toHaveBeenCalledWith('Shot 1: Hero reveal with text Double-Layer Lace');
  });
});
