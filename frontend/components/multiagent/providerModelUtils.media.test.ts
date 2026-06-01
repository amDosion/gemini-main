import { describe, expect, it } from 'vitest';
import {
  formatModelTaskHint,
  normalizeProviderModels,
  normalizeSupportedTasks,
  pickProviderDefaultModel,
  resolveProviderTaskModelSelection,
} from './providerModelUtils';

describe('providerModelUtils media support', () => {
  it('normalizes media task aliases without degrading them to chat', () => {
    expect(normalizeSupportedTasks(['speech', 'video_generation', 'CHAT', 'speech'])).toEqual([
      'audio-gen',
      'video-gen',
      'chat',
    ]);
  });

  it('merges snake_case media model buckets and default models by task', () => {
    const providers = normalizeProviderModels([
      {
        provider_id: 'openai',
        provider_name: 'OpenAI',
        models: [
          { id: 'gpt-4.1', name: 'GPT 4.1', supported_tasks: ['chat'] },
        ],
        video_generation_models: [
          { id: 'sora-preview', name: 'Sora Preview', supported_tasks: ['video-gen'] },
        ],
        audio_generation_models: [
          { id: 'tts-1', name: 'TTS 1', supported_tasks: ['speech'] },
        ],
        default_models_by_task: {
          'video-gen': 'sora-preview',
          'audio-gen': 'tts-1',
        },
      },
    ]);

    expect(providers).toHaveLength(1);
    expect(providers[0].providerId).toBe('openai');
    expect(providers[0].allModels.map((model) => model.id)).toEqual(['gpt-4.1', 'sora-preview', 'tts-1']);
    expect(providers[0].allModels.find((model) => model.id === 'tts-1')?.supportedTasks).toEqual(['audio-gen']);
    expect(pickProviderDefaultModel(providers[0], 'video-gen')?.id).toBe('sora-preview');
    expect(pickProviderDefaultModel(providers[0], 'audio-gen')?.id).toBe('tts-1');
    expect(formatModelTaskHint(['video-gen', 'audio-gen'])).toBe('视频/语音');
  });

  it('fails closed when only incompatible models are available for a task', () => {
    const providers = normalizeProviderModels([
      {
        provider_id: 'openai',
        provider_name: 'OpenAI',
        all_models: [
          { id: 'tts-1', name: 'TTS 1', supported_tasks: ['audio-gen'] },
        ],
        default_models_by_task: {
          chat: 'tts-1',
        },
      },
    ]);

    expect(pickProviderDefaultModel(providers[0], 'chat')).toBeUndefined();
  });

  it('resolves reusable provider task model selection state for panels', () => {
    const providers = normalizeProviderModels([
      {
        provider_id: 'google',
        provider_name: 'Google',
        all_models: [
          { id: 'gemini-chat', name: 'Gemini Chat', supported_tasks: ['chat'] },
          { id: 'veo', name: 'Veo', supported_tasks: ['video-gen'] },
        ],
      },
    ]);

    const selection = resolveProviderTaskModelSelection({
      providers,
      providerId: 'google',
      modelId: 'gemini-chat',
      taskType: 'video-gen',
    });

    expect(selection.selectedProvider?.providerId).toBe('google');
    expect(selection.compatibleModels.map((model) => model.id)).toEqual(['veo']);
    expect(selection.providerHasNoCompatibleModels).toBe(false);
    expect(selection.selectedModel?.id).toBe('gemini-chat');
    expect(selection.selectedModelSupportsTask).toBe(false);
    expect(selection.pickCompatibleModel()?.id).toBe('veo');
  });
});
