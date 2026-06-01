// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { AgentManagerEditorForm } from './AgentManagerEditorForm';
import type { AgentDef } from '../types';
import type { ProviderModels } from '../providerModelUtils';

const buildAgent = (overrides: Partial<AgentDef> = {}): AgentDef => ({
  id: 'agent-1',
  name: 'Media Agent',
  description: '',
  agentType: 'custom',
  providerId: 'openai',
  modelId: 'gpt-4.1',
  systemPrompt: 'You are helpful.',
  temperature: 0.7,
  maxTokens: 4096,
  icon: '🤖',
  color: '#14b8a6',
  status: 'active',
  agentCard: {
    defaults: {
      defaultTaskType: 'chat',
    },
  },
  ...overrides,
});

const providers: ProviderModels[] = [
  {
    providerId: 'openai',
    providerName: 'OpenAI',
    models: [
      { id: 'gpt-4.1', name: 'GPT 4.1', supportedTasks: ['chat'] },
    ],
    allModels: [
      { id: 'gpt-4.1', name: 'GPT 4.1', supportedTasks: ['chat'] },
      { id: 'tts-1', name: 'TTS 1', supportedTasks: ['audio-gen'] },
    ],
    defaultModelsByTask: {
      'audio-gen': 'tts-1',
    },
  },
  {
    providerId: 'google',
    providerName: 'Google',
    models: [],
    allModels: [
      { id: 'veo-3.1', name: 'Veo 3.1', supportedTasks: ['video-gen'] },
      { id: 'gemini-2.5-flash-image', name: 'Gemini Image', supportedTasks: ['image-edit'] },
    ],
    defaultModelsByTask: {
      'video-gen': 'veo-3.1',
      'image-edit': 'gemini-2.5-flash-image',
    },
  },
];

describe('AgentManagerEditorForm media defaults', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders existing video task defaults without degrading them to chat', () => {
    render(
      <AgentManagerEditorForm
        editing={buildAgent({
          providerId: 'google',
          modelId: 'veo-3.1',
          agentCard: {
            defaults: {
              defaultTaskType: 'video-gen',
              videoGeneration: {
                aspectRatio: '16:9',
                resolution: '1080p',
                durationSeconds: 8,
                continueFromPreviousLastFrame: true,
              },
            },
          },
        })}
        isNew={false}
        saving={false}
        providers={providers}
        onCancel={vi.fn()}
        onSave={vi.fn()}
        onChange={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue('🎬 视频生成')).toBeInTheDocument();
    expect(screen.getByDisplayValue('16:9 横屏')).toBeInTheDocument();
    expect(screen.getByDisplayValue('1080p')).toBeInTheDocument();
    expect(screen.getByDisplayValue('8')).toBeInTheDocument();
    expect(screen.getByLabelText('顺序视频节点时以上一段最后一帧作为首帧')).toBeChecked();
  });

  it('edits image-edit defaults that workflow template agents already support', () => {
    const onChange = vi.fn();
    const initialAgent = buildAgent({
      providerId: 'google',
      modelId: 'gemini-2.5-flash-image',
      agentCard: {
        defaults: {
          defaultTaskType: 'image-edit',
          imageEdit: {
            editMode: 'image-chat-edit',
            preserveProductIdentity: true,
            productMatchThreshold: 72,
            maxRetries: 2,
            outputLanguage: 'en',
            addMagicSuffix: true,
          },
        },
      },
    });
    const ControlledForm = () => {
      const [agent, setAgent] = React.useState(initialAgent);
      return (
        <AgentManagerEditorForm
          editing={agent}
          isNew={false}
          saving={false}
          providers={providers}
          onCancel={vi.fn()}
          onSave={vi.fn()}
          onChange={(next) => {
            onChange(next);
            setAgent(next);
          }}
        />
      );
    };

    render(<ControlledForm />);

    expect(screen.getByLabelText('保留商品主体一致性')).toBeChecked();
    fireEvent.change(screen.getByLabelText('商品一致性阈值'), { target: { value: '80' } });
    fireEvent.change(screen.getByLabelText('编辑重试次数'), { target: { value: '3' } });
    fireEvent.change(screen.getByLabelText('输出语言'), { target: { value: 'zh' } });

    const nextAgent = onChange.mock.calls.at(-1)?.[0] as AgentDef;
    expect(nextAgent.agentCard?.defaults?.imageEdit).toMatchObject({
      productMatchThreshold: 80,
      maxRetries: 3,
      outputLanguage: 'zh',
      preserveProductIdentity: true,
    });
  });

  it('edits advanced video defaults that workflow template agents already support', () => {
    const onChange = vi.fn();
    const initialAgent = buildAgent({
      providerId: 'google',
      modelId: 'veo-3.1',
      agentCard: {
        defaults: {
          defaultTaskType: 'video-gen',
          videoGeneration: {
            aspectRatio: '16:9',
            resolution: '1080p',
            durationSeconds: 8,
            videoExtensionCount: 1,
            generateAudio: false,
            subtitleMode: 'none',
            subtitleLanguage: 'zh-CN',
            negativePrompt: 'no blur',
            storyboardPrompt: 'Shot 1',
            promptExtend: true,
          },
        },
      },
    });
    const ControlledForm = () => {
      const [agent, setAgent] = React.useState(initialAgent);
      return (
        <AgentManagerEditorForm
          editing={agent}
          isNew={false}
          saving={false}
          providers={providers}
          onCancel={vi.fn()}
          onSave={vi.fn()}
          onChange={(next) => {
            onChange(next);
            setAgent(next);
          }}
        />
      );
    };

    render(<ControlledForm />);

    expect(screen.getByLabelText('生成原生音频')).not.toBeChecked();
    fireEvent.change(screen.getByLabelText('视频延长次数'), { target: { value: '2' } });
    fireEvent.click(screen.getByLabelText('生成原生音频'));
    fireEvent.change(screen.getByLabelText('字幕模式'), { target: { value: 'srt' } });
    fireEvent.change(screen.getByLabelText('字幕语言'), { target: { value: 'en-US' } });
    fireEvent.change(screen.getByLabelText('反向提示词'), { target: { value: 'no text' } });
    fireEvent.change(screen.getByLabelText('分镜提示词'), { target: { value: 'Shot 2' } });

    const nextAgent = onChange.mock.calls.at(-1)?.[0] as AgentDef;
    expect(nextAgent.agentCard?.defaults?.videoGeneration).toMatchObject({
      videoExtensionCount: 2,
      generateAudio: true,
      subtitleMode: 'srt',
      subtitleLanguage: 'en-US',
      negativePrompt: 'no text',
      storyboardPrompt: 'Shot 2',
    });
  });

  it('keeps agent video chaining defaults mutually exclusive', () => {
    const onChange = vi.fn();

    render(
      <AgentManagerEditorForm
        editing={buildAgent({
          providerId: 'google',
          modelId: 'veo-3.1',
          agentCard: {
            defaults: {
              defaultTaskType: 'video-gen',
              videoGeneration: {},
            },
          },
        })}
        isNew={false}
        saving={false}
        providers={providers}
        onCancel={vi.fn()}
        onSave={vi.fn()}
        onChange={onChange}
      />
    );

    fireEvent.click(screen.getByLabelText('顺序视频节点时自动续接上一段视频'));
    let nextAgent = onChange.mock.calls.at(-1)?.[0] as AgentDef;
    expect(nextAgent.agentCard?.defaults?.videoGeneration).toMatchObject({
      continueFromPreviousVideo: true,
      continueFromPreviousLastFrame: false,
    });

    fireEvent.click(screen.getByLabelText('顺序视频节点时以上一段最后一帧作为首帧'));
    nextAgent = onChange.mock.calls.at(-1)?.[0] as AgentDef;
    expect(nextAgent.agentCard?.defaults?.videoGeneration).toMatchObject({
      continueFromPreviousLastFrame: true,
      continueFromPreviousVideo: false,
    });
  });

  it('switches to audio task defaults and picks a compatible model', () => {
    const onChange = vi.fn();

    render(
      <AgentManagerEditorForm
        editing={buildAgent()}
        isNew={false}
        saving={false}
        providers={providers}
        onCancel={vi.fn()}
        onSave={vi.fn()}
        onChange={onChange}
      />
    );

    fireEvent.change(screen.getByDisplayValue('💬 对话'), {
      target: { value: 'audio-gen' },
    });

    const nextAgent = onChange.mock.calls.at(-1)?.[0] as AgentDef;
    expect(nextAgent.modelId).toBe('tts-1');
    expect(nextAgent.agentCard?.defaults?.defaultTaskType).toBe('audio-gen');
    expect(nextAgent.agentCard?.defaults?.audioGeneration).toMatchObject({
      responseFormat: 'mp3',
      speed: 1,
    });
  });

  it('clears model selection when switched provider has no compatible model', () => {
    const onChange = vi.fn();

    render(
      <AgentManagerEditorForm
        editing={buildAgent({
          providerId: 'google',
          modelId: 'veo-3.1',
          agentCard: {
            defaults: {
              defaultTaskType: 'video-gen',
            },
          },
        })}
        isNew={false}
        saving={false}
        providers={providers}
        onCancel={vi.fn()}
        onSave={vi.fn()}
        onChange={onChange}
      />
    );

    fireEvent.change(screen.getAllByDisplayValue('Google').at(-1)!, {
      target: { value: 'openai' },
    });

    const nextAgent = onChange.mock.calls.at(-1)?.[0] as AgentDef;
    expect(nextAgent.modelId).toBe('');
  });

  it('fails closed for incompatible existing model and disables save', () => {
    render(
      <AgentManagerEditorForm
        editing={buildAgent({
          modelId: 'gpt-4.1',
          agentCard: {
            defaults: {
              defaultTaskType: 'audio-gen',
            },
          },
        })}
        isNew={false}
        saving={false}
        providers={providers}
        onCancel={vi.fn()}
        onSave={vi.fn()}
        onChange={vi.fn()}
      />
    );

    expect(screen.getByText(/保存前必须切换到支持 audio-gen 的模型/)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: '保存' }).at(-1)).toBeDisabled();
  });
});
