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
  providerId: 'google',
  modelId: 'veo-3.1',
  systemPrompt: 'You are helpful.',
  temperature: 0.7,
  maxTokens: 4096,
  icon: '🤖',
  color: '#14b8a6',
  status: 'active',
  agentCard: {
    defaults: {
      defaultTaskType: 'video-gen',
    },
  },
  ...overrides,
});

const providers: ProviderModels[] = [
  {
    providerId: 'openai',
    providerName: 'OpenAI',
    models: [{ id: 'gpt-4.1', name: 'GPT 4.1', supportedTasks: ['chat'] }],
    allModels: [{ id: 'gpt-4.1', name: 'GPT 4.1', supportedTasks: ['chat'] }],
    defaultModelsByTask: {},
  },
  {
    providerId: 'google',
    providerName: 'Google',
    models: [{ id: 'veo-3.1', name: 'Veo 3.1', supportedTasks: ['video-gen'] }],
    allModels: [{ id: 'veo-3.1', name: 'Veo 3.1', supportedTasks: ['video-gen'] }],
    defaultModelsByTask: { 'video-gen': 'veo-3.1' },
  },
];

describe('AgentManagerEditorForm fail-closed', () => {
  afterEach(() => {
    cleanup();
  });

  it('clears modelId when provider switch removes compatibility', () => {
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

    fireEvent.change(screen.getAllByDisplayValue('Google').at(-1)!, {
      target: { value: 'openai' },
    });

    const nextAgent = onChange.mock.calls.at(-1)?.[0] as AgentDef;
    expect(nextAgent.modelId).toBe('');
  });

  it('disables save when current model is incompatible with task type', () => {
    render(
      <AgentManagerEditorForm
        editing={buildAgent({
          providerId: 'openai',
          modelId: 'gpt-4.1',
          agentCard: { defaults: { defaultTaskType: 'audio-gen' } },
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
