import { describe, expect, it } from 'vitest';
import { ModelConfig } from '../types/types';
import {
  getEnhancePromptModelCandidates,
  isDeepResearchModel,
  isMultimodalUnderstandingModel,
  isTongyiVisionPromptEnhancementModel,
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

  it('keeps OpenAI text models as prompt enhancement candidates for OpenAI image modes', () => {
    const candidates = getEnhancePromptModelCandidates(
      [
        buildModel('gpt-5.4-mini', false),
        buildModel('o4-mini', false),
        buildModel('gpt-image-2', true),
        buildModel('dall-e-3', true),
        buildModel('text-embedding-3-large', false),
        buildModel('tts-1', false),
      ],
      'openai'
    );

    expect(candidates.map((model) => model.id)).toEqual(['gpt-5.4-mini', 'o4-mini']);
  });

  it('keeps Tongyi Qwen text models as prompt enhancement candidates for Wan image modes', () => {
    const candidates = getEnhancePromptModelCandidates(
      [
        buildModel('qwen-plus', false),
        buildModel('qwen-max', false),
        buildModel('qwen-vl-max', true),
        buildModel('qwen-image-2.0-pro', true),
        buildModel('wan2.7-image-pro', true),
        buildModel('wan2.7-t2v', true),
        buildModel('happyhorse-1.0-t2v', true),
        buildModel('z-image-turbo', true),
      ],
      'tongyi'
    );

    expect(candidates.map((model) => model.id)).toEqual([
      'qwen-plus',
      'qwen-max',
      'qwen-vl-max',
    ]);
  });

  it('keeps only Tongyi vision models when image editing needs visual prompt enhancement', () => {
    const candidates = getEnhancePromptModelCandidates(
      [
        buildModel('qwen-plus', false),
        buildModel('qwen-max', false),
        buildModel('qwen-vl-max', true),
        buildModel('qwen3-vl-plus', true),
        buildModel('qwen-image-edit-plus', true),
        buildModel('wan2.7-image-pro', true),
      ],
      'tongyi',
      { requiresVision: true }
    );

    expect(candidates.map((model) => model.id)).toEqual([
      'qwen-vl-max',
      'qwen3-vl-plus',
    ]);
    expect(isTongyiVisionPromptEnhancementModel(buildModel('qwen-plus', false))).toBe(false);
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
