// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { resolveModelForModeSend } from './modeModelSelection';

const CHAT_MODEL = {
  id: 'gemini-2.5-flash',
  name: 'Gemini 2.5 Flash',
  description: 'chat',
  capabilities: { vision: true, search: true, reasoning: true, coding: true },
};

const VIDEO_MODEL = {
  id: 'veo-3.1-generate-preview',
  name: 'Veo 3.1',
  description: 'video',
  capabilities: { vision: true, search: false, reasoning: false, coding: false },
};

describe('resolveModelForModeSend', () => {
  it('does not fall back to all-provider chat models for regular video sends', () => {
    const result = resolveModelForModeSend({
      mode: 'video-gen',
      currentModelId: CHAT_MODEL.id,
      visibleModels: [],
      allVisibleModels: [CHAT_MODEL, VIDEO_MODEL],
      activeModelConfig: undefined,
      isLoadingModels: true,
    });

    expect(result).toEqual({ reason: 'loading' });
  });

  it('keeps forced model fallback for welcome-prompt style sends', () => {
    const result = resolveModelForModeSend({
      mode: 'chat',
      currentModelId: CHAT_MODEL.id,
      forcedModelId: VIDEO_MODEL.id,
      visibleModels: [CHAT_MODEL],
      allVisibleModels: [CHAT_MODEL, VIDEO_MODEL],
      activeModelConfig: CHAT_MODEL,
      isLoadingModels: false,
    });

    expect(result.reason).toBe('resolved');
    if (result.reason === 'resolved') {
      expect(result.model.id).toBe(VIDEO_MODEL.id);
    }
  });

  it('prefers the first visible mode model when currentModelId is stale', () => {
    const result = resolveModelForModeSend({
      mode: 'video-gen',
      currentModelId: CHAT_MODEL.id,
      visibleModels: [VIDEO_MODEL],
      allVisibleModels: [CHAT_MODEL, VIDEO_MODEL],
      activeModelConfig: undefined,
      isLoadingModels: false,
    });

    expect(result.reason).toBe('resolved');
    if (result.reason === 'resolved') {
      expect(result.model.id).toBe(VIDEO_MODEL.id);
    }
  });
});
