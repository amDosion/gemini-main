import { describe, expect, it } from 'vitest';
import {
  buildVideoInputStrategyOptions,
  getVideoInputStrategyDisplayLabel,
  isVideoExtensionStrategyId,
} from './videoSubmodeOptions';
import type { ModelConfig } from '../types/types';
import type { VideoContractInputStrategy } from '../hooks/useModeControlsSchema';

const makeModel = (id: string): ModelConfig => ({
  id,
  name: id,
  description: id,
  capabilities: {
    vision: true,
    search: false,
    reasoning: false,
    coding: false,
  },
});

// Schema fallback strategies used when the Tongyi-specific path does not apply.
const schemaStrategies: VideoContractInputStrategy[] = [
  { id: 'text_to_video', label: 'schema-t2v' },
  { id: 'image_to_video', label: 'schema-i2v' },
];

// Model list fixtures: t2v, i2v, r2v, and video-edit families across the
// wan2.7 and happyhorse model lines.
const wan27Models: ModelConfig[] = [
  makeModel('wan2.7-t2v-plus'),
  makeModel('wan2.7-i2v-plus'),
  makeModel('wan2.7-r2v-plus'),
  makeModel('wan2.7-videoedit-plus'),
];

const happyhorseModels: ModelConfig[] = [
  makeModel('happyhorse-t2v-base'),
  makeModel('happyhorse-i2v-base'),
  makeModel('happyhorse-r2v-base'),
  makeModel('happyhorse-video-edit-base'),
];

const allModels: ModelConfig[] = [...wan27Models, ...happyhorseModels];

const optionById = (
  options: ReturnType<typeof buildVideoInputStrategyOptions>,
  id: string
): string | undefined => options.find((option) => option.id === id)?.targetModelId;

describe('isVideoExtensionStrategyId', () => {
  it('recognizes extension-family strategy ids case-insensitively', () => {
    expect(isVideoExtensionStrategyId('video_extension')).toBe(true);
    expect(isVideoExtensionStrategyId('VIDEO_CONTINUATION')).toBe(true);
    expect(isVideoExtensionStrategyId(' video_continuation_to_last_frame ')).toBe(true);
  });

  it('returns false for non-extension and empty ids', () => {
    expect(isVideoExtensionStrategyId('text_to_video')).toBe(false);
    expect(isVideoExtensionStrategyId(undefined)).toBe(false);
    expect(isVideoExtensionStrategyId('')).toBe(false);
  });
});

describe('getVideoInputStrategyDisplayLabel', () => {
  it('maps known strategy ids to localized labels', () => {
    expect(getVideoInputStrategyDisplayLabel({ id: 'text_to_video' })).toBe('文生视频');
    expect(getVideoInputStrategyDisplayLabel({ id: 'masked_video_edit' })).toBe('遮罩视频编辑');
  });

  it('falls back to provided label then raw id for unknown strategies', () => {
    expect(getVideoInputStrategyDisplayLabel({ id: 'unknown', label: 'Custom' })).toBe('Custom');
    expect(getVideoInputStrategyDisplayLabel({ id: 'unknown' })).toBe('unknown');
  });
});

describe('buildVideoInputStrategyOptions', () => {
  it('returns schema strategies unchanged for non-Tongyi providers', () => {
    const result = buildVideoInputStrategyOptions({
      providerId: 'gemini',
      availableModels: allModels,
      schemaStrategies,
    });
    expect(result).toBe(schemaStrategies);
  });

  it('falls back to schema strategies when no model candidates exist', () => {
    const result = buildVideoInputStrategyOptions({
      providerId: 'tongyi',
      availableModels: [],
      schemaStrategies,
    });
    expect(result).toBe(schemaStrategies);
  });

  it('maps each submode to a model of the matching family', () => {
    const options = buildVideoInputStrategyOptions({
      providerId: 'TongYi',
      availableModels: allModels,
      schemaStrategies,
    });

    expect(options.map((option) => option.id)).toEqual([
      'text_to_video',
      'first_frame_to_video',
      'first_last_frame_to_video',
      'reference_to_video',
      'video_edit',
    ]);
    expect(optionById(options, 'text_to_video')).toMatch(/-t2v/);
    // i2v family powers both image-driven submodes.
    expect(optionById(options, 'first_frame_to_video')).toMatch(/-i2v/);
    expect(optionById(options, 'first_last_frame_to_video')).toMatch(/-i2v/);
    expect(optionById(options, 'reference_to_video')).toMatch(/-r2v/);
    expect(optionById(options, 'video_edit')).toMatch(/videoedit|video-edit/);
  });

  it('prefers the exact current model when it matches the requested family', () => {
    const current = makeModel('happyhorse-i2v-base');
    const options = buildVideoInputStrategyOptions({
      providerId: 'tongyi',
      currentModel: current,
      availableModels: allModels,
      schemaStrategies,
    });
    // i2v submodes resolve to the exact current model.
    expect(optionById(options, 'first_frame_to_video')).toBe('happyhorse-i2v-base');
    expect(optionById(options, 'first_last_frame_to_video')).toBe('happyhorse-i2v-base');
  });

  it('prefers the same model line as the current model for cross-family submodes', () => {
    const current = makeModel('happyhorse-i2v-base');
    const options = buildVideoInputStrategyOptions({
      providerId: 'tongyi',
      currentModel: current,
      availableModels: allModels,
      schemaStrategies,
    });
    // Current line is happyhorse, so other families pick happyhorse over wan2.7.
    expect(optionById(options, 'text_to_video')).toBe('happyhorse-t2v-base');
    expect(optionById(options, 'reference_to_video')).toBe('happyhorse-r2v-base');
    expect(optionById(options, 'video_edit')).toBe('happyhorse-video-edit-base');
  });

  it('defaults to the wan2.7 line ahead of happyhorse when no current line matches', () => {
    const options = buildVideoInputStrategyOptions({
      providerId: 'tongyi',
      // No current model: line preference falls through to the wan2.7 default.
      availableModels: allModels,
      schemaStrategies,
    });
    expect(optionById(options, 'text_to_video')).toBe('wan2.7-t2v-plus');
    expect(optionById(options, 'first_frame_to_video')).toBe('wan2.7-i2v-plus');
    expect(optionById(options, 'reference_to_video')).toBe('wan2.7-r2v-plus');
    expect(optionById(options, 'video_edit')).toBe('wan2.7-videoedit-plus');
  });

  it('falls back to happyhorse when only that line is available', () => {
    const options = buildVideoInputStrategyOptions({
      providerId: 'tongyi',
      availableModels: happyhorseModels,
      schemaStrategies,
    });
    expect(optionById(options, 'text_to_video')).toBe('happyhorse-t2v-base');
    expect(optionById(options, 'video_edit')).toBe('happyhorse-video-edit-base');
  });

  it('drops submodes that have no matching model family and keeps the rest', () => {
    const options = buildVideoInputStrategyOptions({
      providerId: 'tongyi',
      availableModels: [makeModel('wan2.7-t2v-plus')],
      schemaStrategies,
    });
    expect(options.map((option) => option.id)).toEqual(['text_to_video']);
    expect(optionById(options, 'text_to_video')).toBe('wan2.7-t2v-plus');
  });

  it('falls back to schema strategies when no submode resolves to a model', () => {
    const options = buildVideoInputStrategyOptions({
      providerId: 'tongyi',
      // A model that matches no Tongyi family classifier.
      availableModels: [makeModel('unrelated-model-id')],
      schemaStrategies,
    });
    expect(options).toBe(schemaStrategies);
  });

  it('uses currentModel as the sole candidate when availableModels is empty', () => {
    const options = buildVideoInputStrategyOptions({
      providerId: 'tongyi',
      currentModel: makeModel('wan2.7-i2v-plus'),
      schemaStrategies,
    });
    expect(options.map((option) => option.id)).toEqual([
      'first_frame_to_video',
      'first_last_frame_to_video',
    ]);
    expect(optionById(options, 'first_frame_to_video')).toBe('wan2.7-i2v-plus');
  });
});
