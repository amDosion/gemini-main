// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LLMService } from './llmService';
import type { ChatOptions, ModelConfig } from '../types/types';

const makeModel = (): ModelConfig => ({
  id: 'imagen-debug-model',
  name: 'Imagen Debug Model',
  description: 'debug model',
  capabilities: {
    vision: true,
    search: false,
    reasoning: false,
    coding: false,
  },
  contextWindow: 0,
});

describe('LLMService debug logging', () => {
  beforeEach(() => {
    window.localStorage.setItem('llm.verbose', '1');
  });

  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it('redacts secrets from verbose option logs', () => {
    const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
    const service = new LLMService();
    const options = {
      enableSearch: false,
      enableThinking: false,
      enableCodeExecution: false,
      imageAspectRatio: '1:1',
      numberOfImages: 1,
      apiKey: 'sk-secret-debug-key',
      accessToken: 'secret-access-token',
      password: 'debug-password',
      baseUrl: 'https://api.example.test/v1?api_key=secret-query-key&safe=1',
      nested: {
        refreshToken: 'secret-refresh-token',
        authorization: 'Bearer secret-bearer-token',
      },
    } as unknown as ChatOptions;

    service.startNewChat([], makeModel(), options);

    const debugText = debugSpy.mock.calls
      .map((call) =>
        call
          .map((arg) => (typeof arg === 'string' ? arg : JSON.stringify(arg)))
          .join(' ')
      )
      .join('\n');

    expect(debugText).toContain('[REDACTED]');
    expect(debugText).not.toContain('sk-secret-debug-key');
    expect(debugText).not.toContain('secret-access-token');
    expect(debugText).not.toContain('debug-password');
    expect(debugText).not.toContain('secret-query-key');
    expect(debugText).not.toContain('secret-refresh-token');
    expect(debugText).not.toContain('secret-bearer-token');
  });
});
