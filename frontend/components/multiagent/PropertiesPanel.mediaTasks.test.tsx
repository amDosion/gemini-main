// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { PropertiesPanel } from './PropertiesPanel';

vi.mock('./AgentSelector', () => ({
  AgentSelector: ({ onResolvedAgent }: { onResolvedAgent?: (agent: any) => void }) => {
    React.useEffect(() => {
      onResolvedAgent?.({
        id: 'agent-1',
        name: '数据分析 Agent',
        providerId: 'openai',
        modelId: 'gpt-4.1',
        source: { kind: 'seed', label: '官方 Seed', isSystem: true },
        runtime: { kind: 'google-adk', label: 'Google ADK', supportsRun: true, supportsLiveRun: true, supportsSessions: true, supportsMemory: true, supportsOfficialOrchestration: true },
        agentCard: {
          defaults: {
            defaultTaskType: 'data-analysis',
            dataAnalysis: { outputFormat: 'markdown' },
            audioGeneration: { voice: 'nova', responseFormat: 'mp3', speed: 1 },
          },
        },
      });
    }, [onResolvedAgent]);
    return <div data-testid="agent-selector" />;
  },
}));

vi.mock('../../services/apiClient', () => ({
  getAuthHeaders: () => ({}),
}));

const fetchMock = vi.fn();

const buildNode = (type: string, data: Record<string, any> = {}) => ({
  id: `node-${type}`,
  type,
  data: {
    type,
    label: `Node ${type}`,
    description: '',
    icon: '🤖',
    iconColor: 'bg-teal-500',
    status: 'pending',
    ...data,
  },
});

describe('PropertiesPanel media task support', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/agents/available-models')) {
        return new Response(
          JSON.stringify({
            providers: [
              {
                providerId: 'google',
                providerName: 'Google',
                models: [],
                allModels: [
                  { id: 'veo-3.1', name: 'Veo 3.1', supportedTasks: ['video-gen'] },
                  { id: 'veo-2.0-generate-001', name: 'Veo 2.0', supportedTasks: ['video-gen'] },
                  { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', supportedTasks: ['chat', 'vision-understand'] },
                ],
              },
              {
                providerId: 'openai',
                providerName: 'OpenAI',
                models: [],
                allModels: [
                  { id: 'tts-1', name: 'TTS 1', supportedTasks: ['audio-gen'] },
                ],
              },
            ],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }
      if (url.includes('/api/modes/google/video-gen/controls')) {
        return new Response(
          JSON.stringify({
            success: true,
            provider: 'google',
            mode: 'video-gen',
            schema: {
              provider: 'google',
              mode: 'video-gen',
              defaults: {
                aspect_ratio: '16:9',
                resolution: '720p',
                seconds: '8',
                video_extension_count: 0,
                enhance_prompt: true,
                generate_audio: false,
                subtitle_mode: 'none',
              },
              aspect_ratios: [
                { value: '16:9', label: '16:9' },
                { value: '9:16', label: '9:16' },
              ],
              resolution_tiers: [
                { value: '720p', label: '720p', baseResolution: '1280×720' },
                { value: '1080p', label: '1080p', baseResolution: '1920×1080' },
                { value: '4k', label: '4k', baseResolution: '3840×2160' },
              ],
              resolution_map: {
                '720p': { '16:9': '1280×720', '9:16': '720×1280' },
                '1080p': { '16:9': '1920×1080', '9:16': '1080×1920' },
                '4k': { '16:9': '3840×2160', '9:16': '2160×3840' },
              },
              param_options: {
                seconds: ['4', '6', '8'],
                video_extension_count: [0, 1, 2],
                person_generation: ['dont_allow', 'allow_adult'],
                subtitle_mode: ['none', 'vtt'],
                subtitle_language: ['en-US', 'zh-CN'],
              },
              constraints: {
                supports_generate_audio: true,
                supports_person_generation: true,
                supports_subtitle_sidecar: true,
                enhance_prompt_mandatory: true,
                video_extension_added_seconds: 7,
                video_extension_require_resolution_values: ['720p'],
              },
              video_contract: {
                field_policies: {
                  enhance_prompt: {
                    mandatory: true,
                    locked_when_mandatory: true,
                    effective_default: true,
                  },
                  generate_audio: {
                    available: true,
                    forced_value: null,
                  },
                  person_generation: {
                    available: true,
                    forced_value: null,
                  },
                  subtitle_mode: {
                    available: true,
                    single_sidecar_format: true,
                    default_enabled_mode: 'vtt',
                    supported_values: ['none', 'vtt'],
                  },
                  storyboard_prompt: {
                    preferred: true,
                    deprecated_companion_fields: ['tracked_feature', 'tracking_overlay_text'],
                  },
                },
                extension_duration_matrix: [
                  {
                    base_seconds: '4',
                    options: [{ count: 0, label: '4s (base)', total_seconds: 4 }],
                  },
                  {
                    base_seconds: '6',
                    options: [{ count: 0, label: '6s (base)', total_seconds: 6 }],
                  },
                  {
                    base_seconds: '8',
                    options: [
                      { count: 0, label: '8s (base)', total_seconds: 8 },
                      { count: 1, label: '15s (+1 extension)', total_seconds: 15 },
                      { count: 2, label: '22s (+2 extensions)', total_seconds: 22 },
                    ],
                  },
                ],
                extension_constraints: {
                  added_seconds: 7,
                  require_resolution_values: ['720p'],
                },
              },
            },
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }
      throw new Error(`Unexpected fetch in test: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('renders stored video tasks without degrading them to chat', async () => {
    render(
      <PropertiesPanel
        selectedNode={buildNode('agent', {
          agentTaskType: 'video-gen',
          agentProviderId: 'google',
          agentModelId: 'veo-3.1',
          agentContinueFromPreviousLastFrame: true,
        }) as any}
        onClose={vi.fn()}
        onUpdateNode={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue('720p (1280×720)')).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue('🎬 视频生成（文生视频）')).toBeInTheDocument();
    expect(screen.getByText('视频生成参数')).toBeInTheDocument();
    expect(screen.getByDisplayValue('16:9 横屏')).toBeInTheDocument();
    expect(screen.getByDisplayValue('720p (1280×720)')).toBeInTheDocument();
    expect(screen.getByDisplayValue('8s')).toBeInTheDocument();
    expect(screen.getByLabelText('以上一段最后一帧作为首帧')).toBeChecked();
  });

  it('keeps video continuation strategies mutually exclusive', async () => {
    const onUpdateNode = vi.fn();

    render(
      <PropertiesPanel
        selectedNode={buildNode('agent', {
          agentTaskType: 'video-gen',
          agentProviderId: 'google',
          agentModelId: 'veo-3.1',
        }) as any}
        onClose={vi.fn()}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByLabelText('续接上一段视频结果'));
    expect(onUpdateNode).toHaveBeenLastCalledWith('node-agent', expect.objectContaining({
      agentContinueFromPreviousVideo: true,
      agentContinueFromPreviousLastFrame: false,
    }));

    fireEvent.click(screen.getByLabelText('以上一段最后一帧作为首帧'));
    expect(onUpdateNode).toHaveBeenLastCalledWith('node-agent', expect.objectContaining({
      agentContinueFromPreviousLastFrame: true,
      agentContinueFromPreviousVideo: false,
    }));
  });

  it('shows media task options and preserves stored audio tasks', async () => {
    render(
      <PropertiesPanel
        selectedNode={buildNode('agent', {
          agentTaskType: 'audio-gen',
          agentProviderId: 'openai',
          agentModelId: 'tts-1',
          agentVoice: 'alloy',
        }) as any}
        onClose={vi.fn()}
        onUpdateNode={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    expect(screen.getByDisplayValue('🎧 音频生成（语音/旁白）')).toBeInTheDocument();
    expect(screen.getByText('音频生成参数')).toBeInTheDocument();
    expect(screen.getByDisplayValue('alloy')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /🎬 视频生成（文生视频）/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /🎧 音频生成（语音\/旁白）/ })).toBeInTheDocument();
  });

  it('applies audio task defaults when switching from chat', async () => {
    const onUpdateNode = vi.fn();

    render(
      <PropertiesPanel
        selectedNode={buildNode('agent', {
          agentTaskType: 'chat',
          agentProviderId: 'openai',
          agentModelId: 'tts-1',
        }) as any}
        onClose={vi.fn()}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    fireEvent.change(document.querySelector('[data-field-key="agentTaskType"]') as HTMLSelectElement, {
      target: { value: 'audio-gen' },
    });

    expect(onUpdateNode).toHaveBeenCalledWith('node-agent', expect.objectContaining({
      agentTaskType: 'audio-gen',
      agentAudioFormat: 'mp3',
      agentSpeechSpeed: 1,
    }));
  });

  it('applies backend-derived workflow video defaults when switching from chat', async () => {
    const onUpdateNode = vi.fn();

    render(
      <PropertiesPanel
        selectedNode={buildNode('agent', {
          agentTaskType: 'chat',
          agentProviderId: 'google',
          agentModelId: 'veo-3.1',
        }) as any}
        onClose={vi.fn()}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    fireEvent.change(document.querySelector('[data-field-key="agentTaskType"]') as HTMLSelectElement, {
      target: { value: 'video-gen' },
    });

    expect(onUpdateNode).toHaveBeenCalledWith('node-agent', expect.objectContaining({
      agentTaskType: 'video-gen',
      agentAspectRatio: '16:9',
      agentResolutionTier: '720p',
      agentVideoDurationSeconds: 8,
      agentVideoExtensionCount: 0,
      agentPromptExtend: true,
      agentGenerateAudio: false,
      agentSubtitleMode: 'none',
    }));
  });

  it('fails closed when a provider has no compatible override model for the selected task', async () => {
    const onUpdateNode = vi.fn();

    render(
      <PropertiesPanel
        selectedNode={buildNode('agent', {
          agentTaskType: 'chat',
          agentProviderId: 'google',
          agentModelId: 'gemini-2.5-flash',
        }) as any}
        onClose={vi.fn()}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    fireEvent.change(document.querySelector('[data-field-key="modelOverrideProviderId"]') as HTMLSelectElement, {
      target: { value: 'openai' },
    });

    expect(onUpdateNode).toHaveBeenCalledWith('node-agent', {
      modelOverrideProviderId: 'openai',
      modelOverrideModelId: '',
    });
  });

  it('renders bounded audio/video input node editors', () => {
    const { rerender } = render(
      <PropertiesPanel
        selectedNode={buildNode('input_video') as any}
        onClose={vi.fn()}
        onUpdateNode={vi.fn()}
      />
    );

    expect(screen.getByText('输入视频（input.videoUrl / input.videoUrls）')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/prev\.output\.videoUrl/)).toBeInTheDocument();

    rerender(
      <PropertiesPanel
        selectedNode={buildNode('input_audio') as any}
        onClose={vi.fn()}
        onUpdateNode={vi.fn()}
      />
    );

    expect(screen.getByText('输入音频（input.audioUrl / input.audioUrls）')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/prev\.output\.audioUrl/)).toBeInTheDocument();
  });

  it('renders workflow video tool editors for generate / understand / delete', async () => {
    const { rerender } = render(
      <PropertiesPanel
        selectedNode={buildNode('tool', {
          toolName: 'video_generate',
          toolProviderId: 'google',
          toolModelId: 'veo-3.1',
          toolAspectRatio: '16:9',
          toolResolutionTier: '1K',
          toolVideoDurationSeconds: 8,
          toolSourceVideoUrl: '{{prev.output.videoUrl}}',
        }) as any}
        onClose={vi.fn()}
        onUpdateNode={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue('720p (1280×720)')).toBeInTheDocument();
    });

    expect(screen.getByText('视频生成参数')).toBeInTheDocument();
    expect(screen.getByDisplayValue('16:9 横屏')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('1K')).not.toBeInTheDocument();
    expect(screen.getByDisplayValue('8s')).toBeInTheDocument();
    expect(screen.getByDisplayValue('{{prev.output.videoUrl}}')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /🧠 视频理解/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /🗑️ 视频删除/ })).toBeInTheDocument();

    rerender(
      <PropertiesPanel
        selectedNode={buildNode('tool', {
          toolName: 'video_understand',
          toolProviderId: 'google',
          toolModelId: 'gemini-2.5-flash',
          toolSourceVideoUrl: '{{prev.output.videoUrl}}',
          toolArgsTemplate: JSON.stringify({
            prompt: '请分析该视频的主要场景。',
            output_format: 'json',
          }),
        }) as any}
        onClose={vi.fn()}
        onUpdateNode={vi.fn()}
      />
    );

    expect(screen.getByText('视频理解参数')).toBeInTheDocument();
    expect(screen.getByDisplayValue('JSON')).toBeInTheDocument();

    rerender(
      <PropertiesPanel
        selectedNode={buildNode('tool', {
          toolName: 'video_delete',
          toolProviderId: 'google',
          toolArgsTemplate: JSON.stringify({
            provider_file_name: 'files/demo-video',
          }),
        }) as any}
        onClose={vi.fn()}
        onUpdateNode={vi.fn()}
      />
    );

    expect(screen.getByText('视频删除参数')).toBeInTheDocument();
    expect(screen.getByDisplayValue('files/demo-video')).toBeInTheDocument();
  });

  it('renders inline end-node audio and video previews', () => {
    render(
      <PropertiesPanel
        selectedNode={buildNode('end', {
          status: 'completed',
          result: {
            finalOutput: {
              text: '媒体执行完成',
              audioUrl: 'https://cdn.example.com/final.mp3',
              videoUrl: 'https://cdn.example.com/final.mp4',
            },
          },
        }) as any}
        onClose={vi.fn()}
        onUpdateNode={vi.fn()}
      />
    );

    expect(screen.getByText('结束结果预览')).toBeInTheDocument();
    expect(screen.getByText('结果视频共 1 条')).toBeInTheDocument();
    expect(screen.getByText('结果音频共 1 条')).toBeInTheDocument();
    expect(document.querySelector('video')).toBeTruthy();
    expect(document.querySelector('audio')).toBeTruthy();
  });

  it('surfaces agent source and duplicate node defaults for cleanup', async () => {
    const onUpdateNode = vi.fn();

    render(
      <PropertiesPanel
        selectedNode={buildNode('agent', {
          agentId: 'agent-1',
          agentTaskType: 'data-analysis',
          agentOutputFormat: 'markdown',
          agentVoice: 'alloy',
        }) as any}
        onClose={vi.fn()}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Agent 默认值继承分析')).toBeInTheDocument();
    });

    expect(screen.getByText('来源: 官方 Seed')).toBeInTheDocument();
    expect(screen.getByText('Runtime: Google ADK')).toBeInTheDocument();
    expect(screen.getByText(/重复 2/)).toBeInTheDocument();
    expect(screen.getByText(/覆盖 1/)).toBeInTheDocument();
    expect(screen.getAllByText(/任务类型/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/音色/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /清理重复字段 2/ }));

    expect(onUpdateNode).toHaveBeenCalledWith('node-agent', {
      agentTaskType: undefined,
      agentOutputFormat: undefined,
    });
  });
});
