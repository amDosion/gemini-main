import { describe, expect, it } from 'vitest';

import type { ModeControlsSchema } from '../hooks/useModeControlsSchema';
import { buildVideoControlContract, isVideoControlSelectionValid } from './videoControlSchema';

describe('videoControlSchema', () => {
  it('derives defaults and valid values from schema', () => {
    const schema: ModeControlsSchema = {
      provider: 'google',
      mode: 'video-gen',
      defaults: {
        aspect_ratio: '16:9',
        resolution: '720p',
        seconds: '8',
      },
      aspectRatios: [
        { label: '16:9', value: '16:9' },
        { label: '9:16', value: '9:16' },
      ],
      resolutionTiers: [
        { label: '720p', value: '720p', baseResolution: '1280x720' },
      ],
      paramOptions: {
        seconds: [
          { label: '8s', value: '8' },
        ],
      },
      videoContract: {
        fieldPolicies: {
          enhancePrompt: {
            mandatory: true,
            lockedWhenMandatory: true,
            effectiveDefault: true,
          },
          subtitleMode: {
            available: true,
            singleSidecarFormat: true,
            defaultEnabledMode: 'vtt',
            supportedValues: ['none', 'vtt'],
          },
        },
        extensionDurationMatrix: [
          {
            baseSeconds: '8',
            options: [
              { count: 0, label: '8s (base)', totalSeconds: 8 },
              { count: 1, label: '15s (+1 extensions)', totalSeconds: 15 },
              { count: 2, label: '22s (+2 extensions)', totalSeconds: 22 },
            ],
          },
        ],
        extensionConstraints: {
          addedSeconds: 7,
          maxOutputVideoSeconds: 141,
        },
      },
    };

    expect(buildVideoControlContract(schema)).toEqual({
      defaultAspectRatio: '16:9',
      defaultResolution: '720p',
      defaultVideoSeconds: '8',
      defaultVideoExtensionCount: 0,
      defaultStoryboardShotSeconds: 4,
      defaultGenerateAudio: false,
      defaultPersonGeneration: '',
      defaultSubtitleMode: 'none',
      defaultSubtitleLanguage: '',
      defaultSubtitleScript: '',
      defaultStoryboardPrompt: '',
      defaultNegativePrompt: '',
      defaultSeed: -1,
      defaultEnhancePrompt: true,
      validAspectRatios: ['16:9', '9:16'],
      validResolutionTiers: ['720p'],
      validSeconds: ['8'],
      validVideoExtensionCounts: [0, 1, 2],
      validStoryboardShotSeconds: [],
      validPersonGenerationValues: [],
      validSubtitleModes: ['none', 'vtt'],
      validSubtitleLanguages: [],
      validVideoExtensionCountsBySeconds: {
        '8': [0, 1, 2],
      },
      extensionOptionsBySeconds: {
        '8': [
          { count: 0, label: '8s (base)', totalSeconds: 8 },
          { count: 1, label: '15s (+1 extensions)', totalSeconds: 15 },
          { count: 2, label: '22s (+2 extensions)', totalSeconds: 22 },
        ],
      },
      fieldPolicies: {
        enhancePromptMandatory: true,
        enhancePromptLocked: true,
        enhancePromptEffectiveDefault: true,
        generateAudioAvailable: false,
        generateAudioForcedValue: null,
        personGenerationAvailable: false,
        personGenerationForcedValue: null,
        subtitleModeAvailable: true,
        subtitleModeSingleSidecarFormat: true,
        subtitleModeDefaultEnabled: 'vtt',
        subtitleModeSupportedValues: ['none', 'vtt'],
        storyboardPromptPreferred: false,
        storyboardPromptDeprecatedCompanionFields: [],
      },
      extensionConstraints: {
        addedSeconds: 7,
        maxExtensionCount: null,
        maxSourceVideoSeconds: null,
        maxOutputVideoSeconds: 141,
        requireDurationSeconds: [],
        requireResolutionValues: [],
      },
      schemaReady: true,
    });
  });

  it('rejects values not allowed by schema', () => {
    const contract = buildVideoControlContract({
      provider: 'openai',
      mode: 'video-gen',
      defaults: {
        aspect_ratio: '16:9',
        resolution: '1K',
        seconds: '4',
        video_extension_count: 0,
      },
      aspectRatios: [{ label: '16:9', value: '16:9' }],
      resolutionTiers: [{ label: '720p', value: '1K', baseResolution: '1280x720' }],
      paramOptions: {
        seconds: [{ label: '4s', value: '4' }],
        video_extension_count: [{ label: '不延长', value: 0 }, { label: '延长 1 次', value: 1 }],
      },
      videoContract: {
        extensionDurationMatrix: [
          {
            baseSeconds: '4',
            options: [
              { count: 0, label: '4s (base)', totalSeconds: 4 },
              { count: 1, label: '11s (+1 extensions)', totalSeconds: 11 },
            ],
          },
        ],
      },
    });

    expect(
      isVideoControlSelectionValid(contract, {
        aspectRatio: '1:1',
        resolution: '1K',
        videoSeconds: '4',
      })
    ).toBe(false);

    expect(
      isVideoControlSelectionValid(contract, {
        aspectRatio: '16:9',
        resolution: '1K',
        videoSeconds: '4',
        videoExtensionCount: 1,
      })
    ).toBe(true);

    expect(
      isVideoControlSelectionValid(contract, {
        aspectRatio: '16:9',
        resolution: '1K',
        videoSeconds: '4',
        videoExtensionCount: 2,
      })
    ).toBe(false);
  });
});
