import { describe, expect, it } from 'vitest';
import { ModelConfig } from '../types/types';
import {
  getEnhancePromptModelCandidates,
  isDeepResearchModel,
  isMultimodalUnderstandingModel,
  isThinkingCapableModel,
} from './modelSuitability';

const buildModel = (
  id: string,
  vision: boolean,
  traits?: ModelConfig['traits'],
): ModelConfig => ({
  id,
  name: id,
  description: id,
  capabilities: {
    vision,
    search: false,
    reasoning: false,
    coding: false,
  },
  traits,
});

describe('modelSuitability', () => {
  it('keeps gemini multimodal image understanding models', () => {
    const model = buildModel('gemini-3.1-pro-preview', true);
    expect(isMultimodalUnderstandingModel(model)).toBe(true);
  });

  it('filters out specialized generation/edit pipelines', () => {
    const candidates = getEnhancePromptModelCandidates([
      buildModel('gemini-3.1-pro-preview', true),
      buildModel('gemini-3.1-flash-image-preview', true),
      buildModel('imagen-4.0-generate-preview', true),
      buildModel('veo-3.1-generate-preview', true),
      buildModel('virtual-try-on-001', true),
      buildModel('automl-vision-image-classification', true),
    ]);

    expect(candidates.map((m) => m.id)).toEqual(['gemini-3.1-pro-preview']);
  });

  it('prioritizes backend traits over legacy fallback', () => {
    const model = buildModel('gemini-3.1-flash-image-preview', true, {
      multimodalUnderstanding: true,
      deepResearch: false,
      thinking: false,
    });

    expect(isMultimodalUnderstandingModel(model)).toBe(true);
  });

  it('uses backend traits for thinking and deep research', () => {
    const model = buildModel('plain-chat-model', false, {
      multimodalUnderstanding: false,
      deepResearch: true,
      thinking: true,
    });

    expect(isThinkingCapableModel(model)).toBe(true);
    expect(isDeepResearchModel(model)).toBe(true);
  });
});
