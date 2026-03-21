import { describe, expect, it } from 'vitest';
import { ChatOptions, ModelConfig, Message, Role } from '../../types/types';
import { MessagePreparer } from './MessagePreparer';

const BASE_OPTIONS: ChatOptions = {
  enableSearch: false,
  enableThinking: false,
  enableCodeExecution: false,
  imageAspectRatio: '1:1',
  imageResolution: '1024x1024',
};

const HISTORY: Message[] = [
  {
    id: 'u1',
    role: Role.USER,
    content: 'hello',
    timestamp: 1,
  },
  {
    id: 'a1',
    role: Role.MODEL,
    content: 'hi',
    timestamp: 2,
  },
];

const buildModel = (contextWindow?: number): ModelConfig => ({
  id: 'test-model',
  name: 'Test Model',
  description: 'for tests',
  capabilities: {
    vision: false,
    search: false,
    reasoning: false,
    coding: false,
  },
  contextWindow,
});

describe('MessagePreparer', () => {
  it('uses backend-provided contextWindow when available', async () => {
    const preparer = new MessagePreparer();

    const payload = await preparer.prepare(
      HISTORY,
      'current input',
      [],
      BASE_OPTIONS,
      buildModel(65536),
    );

    expect(payload.contextWindow).toBe(65536);
    expect(payload.messages).toHaveLength(2);
  });

  it('falls back to a safe default when contextWindow is missing or invalid', async () => {
    const preparer = new MessagePreparer();

    const noWindowPayload = await preparer.prepare(
      HISTORY,
      'current input',
      [],
      BASE_OPTIONS,
      buildModel(undefined),
    );
    const invalidWindowPayload = await preparer.prepare(
      HISTORY,
      'current input',
      [],
      BASE_OPTIONS,
      buildModel(0),
    );

    expect(noWindowPayload.contextWindow).toBe(128000);
    expect(invalidWindowPayload.contextWindow).toBe(128000);
  });
});
