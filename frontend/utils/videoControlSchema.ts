import type {
  ModeControlsSchema,
  VideoContractExtensionOption,
  VideoContractFieldPolicies,
} from '../hooks/useModeControlsSchema';

export interface VideoControlFieldPolicies {
  enhancePromptMandatory: boolean;
  enhancePromptLocked: boolean;
  enhancePromptEffectiveDefault: boolean;
  generateAudioAvailable: boolean;
  generateAudioForcedValue: boolean | null;
  personGenerationAvailable: boolean;
  personGenerationForcedValue: string | number | boolean | null;
  subtitleModeAvailable: boolean;
  subtitleModeSingleSidecarFormat: boolean;
  subtitleModeDefaultEnabled: string | null;
  subtitleModeSupportedValues: string[];
  storyboardPromptPreferred: boolean;
  storyboardPromptDeprecatedCompanionFields: string[];
}

export interface VideoControlExtensionConstraints {
  addedSeconds: number | null;
  maxExtensionCount: number | null;
  maxSourceVideoSeconds: number | null;
  maxOutputVideoSeconds: number | null;
  requireDurationSeconds: string[];
  requireResolutionValues: string[];
}

export interface VideoControlContract {
  defaultAspectRatio: string;
  defaultResolution: string;
  defaultVideoSeconds: string;
  defaultVideoExtensionCount: number;
  defaultStoryboardShotSeconds: number;
  defaultGenerateAudio: boolean;
  defaultPersonGeneration: string;
  defaultSubtitleMode: string;
  defaultSubtitleLanguage: string;
  defaultSubtitleScript: string;
  defaultStoryboardPrompt: string;
  defaultNegativePrompt: string;
  defaultSeed: number;
  defaultEnhancePrompt: boolean;
  validAspectRatios: string[];
  validResolutionTiers: string[];
  validSeconds: string[];
  validVideoExtensionCounts: number[];
  validStoryboardShotSeconds: number[];
  validPersonGenerationValues: string[];
  validSubtitleModes: string[];
  validSubtitleLanguages: string[];
  validVideoExtensionCountsBySeconds: Record<string, number[]>;
  extensionOptionsBySeconds: Record<string, VideoContractExtensionOption[]>;
  fieldPolicies: VideoControlFieldPolicies;
  extensionConstraints: VideoControlExtensionConstraints;
  schemaReady: boolean;
}

type VideoControlSelection = {
  aspectRatio: string;
  resolution: string;
  videoSeconds: string;
  videoExtensionCount?: number;
};

const EMPTY_FIELD_POLICIES: VideoControlFieldPolicies = {
  enhancePromptMandatory: false,
  enhancePromptLocked: false,
  enhancePromptEffectiveDefault: false,
  generateAudioAvailable: true,
  generateAudioForcedValue: null,
  personGenerationAvailable: true,
  personGenerationForcedValue: null,
  subtitleModeAvailable: false,
  subtitleModeSingleSidecarFormat: false,
  subtitleModeDefaultEnabled: null,
  subtitleModeSupportedValues: [],
  storyboardPromptPreferred: false,
  storyboardPromptDeprecatedCompanionFields: [],
};

const EMPTY_EXTENSION_CONSTRAINTS: VideoControlExtensionConstraints = {
  addedSeconds: null,
  maxExtensionCount: null,
  maxSourceVideoSeconds: null,
  maxOutputVideoSeconds: null,
  requireDurationSeconds: [],
  requireResolutionValues: [],
};

function normalizeFieldPolicies(
  fieldPolicies: VideoContractFieldPolicies | null | undefined,
  schema: ModeControlsSchema | null | undefined
): VideoControlFieldPolicies {
  const constraints = schema?.constraints ?? {};
  const defaults = schema?.defaults ?? {};
  const subtitleModeSupportedValues =
    fieldPolicies?.subtitleMode?.supportedValues ??
    (schema?.paramOptions?.subtitle_mode ?? [])
      .map((option) => String(option.value))
      .filter((value) => value.length > 0);

  return {
    enhancePromptMandatory:
      fieldPolicies?.enhancePrompt?.mandatory ?? constraints.enhance_prompt_mandatory === true,
    enhancePromptLocked:
      fieldPolicies?.enhancePrompt?.lockedWhenMandatory ??
      fieldPolicies?.enhancePrompt?.mandatory ??
      constraints.enhance_prompt_mandatory === true,
    enhancePromptEffectiveDefault:
      fieldPolicies?.enhancePrompt?.effectiveDefault ??
      (typeof defaults.enhance_prompt === 'boolean' ? defaults.enhance_prompt : false),
    generateAudioAvailable:
      fieldPolicies?.generateAudio?.available ??
      (constraints.supports_generate_audio === true ||
        (schema?.paramOptions?.generate_audio?.length ?? 0) > 0),
    generateAudioForcedValue:
      typeof fieldPolicies?.generateAudio?.forcedValue === 'boolean'
        ? fieldPolicies.generateAudio.forcedValue
        : null,
    personGenerationAvailable:
      fieldPolicies?.personGeneration?.available ??
      (constraints.supports_person_generation === true ||
        (schema?.paramOptions?.person_generation?.length ?? 0) > 0),
    personGenerationForcedValue:
      fieldPolicies?.personGeneration?.forcedValue !== undefined
        ? fieldPolicies.personGeneration.forcedValue ?? null
        : null,
    subtitleModeAvailable:
      fieldPolicies?.subtitleMode?.available ?? subtitleModeSupportedValues.length > 0,
    subtitleModeSingleSidecarFormat:
      fieldPolicies?.subtitleMode?.singleSidecarFormat ?? false,
    subtitleModeDefaultEnabled:
      fieldPolicies?.subtitleMode?.defaultEnabledMode ??
      subtitleModeSupportedValues.find((value) => value !== 'none') ??
      null,
    subtitleModeSupportedValues,
    storyboardPromptPreferred:
      fieldPolicies?.storyboardPrompt?.preferred ?? constraints.supports_storyboard_prompting === true,
    storyboardPromptDeprecatedCompanionFields:
      fieldPolicies?.storyboardPrompt?.deprecatedCompanionFields ?? [],
  };
}

function buildLegacyExtensionOptionsBySeconds(
  schema: ModeControlsSchema | null | undefined,
  validSeconds: string[]
): Record<string, VideoContractExtensionOption[]> {
  const availableVideoExtensionCounts = (schema?.paramOptions?.video_extension_count ?? [])
    .map((option) => Number(option.value))
    .filter((value): value is number => Number.isFinite(value) && value >= 0);
  const addedSeconds = Number(schema?.constraints?.video_extension_added_seconds);
  const maxSourceVideoSeconds = Number(schema?.constraints?.max_source_video_seconds);
  const maxOutputVideoSeconds = Number(schema?.constraints?.max_output_video_seconds);
  const upperBound = Number.isFinite(maxOutputVideoSeconds) && maxOutputVideoSeconds > 0
    ? maxOutputVideoSeconds
    : Number.isFinite(maxSourceVideoSeconds) && maxSourceVideoSeconds > 0
      ? maxSourceVideoSeconds
      : 0;

  if (!availableVideoExtensionCounts.length || !Number.isFinite(addedSeconds) || addedSeconds <= 0) {
    return {};
  }

  return Object.fromEntries(
    validSeconds.map((baseSeconds) => {
      const baseValue = Number(baseSeconds);
      if (!Number.isFinite(baseValue) || baseValue <= 0) {
        return [baseSeconds, []];
      }
      const options = availableVideoExtensionCounts
        .map((count) => ({
          count,
          totalSeconds: baseValue + count * addedSeconds,
        }))
        .filter((option) => upperBound <= 0 || option.totalSeconds <= upperBound)
        .map((option) => ({
          ...option,
          label: option.count === 0 ? `${option.totalSeconds}s (base)` : `${option.totalSeconds}s (+${option.count} extensions)`,
        }));
      return [baseSeconds, options];
    })
  );
}

function buildExtensionOptionsBySeconds(
  schema: ModeControlsSchema | null | undefined,
  validSeconds: string[]
): Record<string, VideoContractExtensionOption[]> {
  const backendMatrix = schema?.videoContract?.extensionDurationMatrix;
  if (backendMatrix && backendMatrix.length > 0) {
    return Object.fromEntries(
      backendMatrix.map((entry) => [entry.baseSeconds, entry.options])
    );
  }
  return buildLegacyExtensionOptionsBySeconds(schema, validSeconds);
}

export function buildVideoControlContract(
  schema: ModeControlsSchema | null | undefined
): VideoControlContract {
  const validAspectRatios = (schema?.aspectRatios ?? [])
    .map((option) => option.value)
    .filter((value): value is string => typeof value === 'string' && value.length > 0);
  const validResolutionTiers = (schema?.resolutionTiers ?? [])
    .map((option) => option.value)
    .filter((value): value is string => typeof value === 'string' && value.length > 0);
  const validSeconds = (schema?.paramOptions?.seconds ?? [])
    .map((option) => String(option.value))
    .filter((value): value is string => value.length > 0);
  const extensionOptionsBySeconds = buildExtensionOptionsBySeconds(schema, validSeconds);
  const validVideoExtensionCountsBySeconds = Object.fromEntries(
    Object.entries(extensionOptionsBySeconds).map(([baseSeconds, options]) => [
      baseSeconds,
      options
        .map((option) => option.count)
        .filter((value): value is number => Number.isFinite(value) && value >= 0),
    ])
  );
  const validVideoExtensionCounts = Array.from(
    new Set(Object.values(validVideoExtensionCountsBySeconds).flat())
  );
  const defaults = schema?.defaults ?? {};
  const fieldPolicies = normalizeFieldPolicies(schema?.videoContract?.fieldPolicies, schema);
  const validStoryboardShotSeconds = (schema?.paramOptions?.storyboard_shot_seconds ?? [])
    .map((option) => Number(option.value))
    .filter((value): value is number => Number.isFinite(value) && value > 0);
  const validPersonGenerationValues = (schema?.paramOptions?.person_generation ?? [])
    .map((option) => String(option.value))
    .filter((value): value is string => value.length > 0);
  const validSubtitleModes = Array.from(
    new Set([
      ...(schema?.paramOptions?.subtitle_mode ?? [])
        .map((option) => String(option.value))
        .filter((value): value is string => value.length > 0),
      ...fieldPolicies.subtitleModeSupportedValues,
    ])
  );
  const validSubtitleLanguages = (schema?.paramOptions?.subtitle_language ?? [])
    .map((option) => String(option.value))
    .filter((value): value is string => value.length > 0);
  const extensionConstraints = {
    addedSeconds:
      schema?.videoContract?.extensionConstraints?.addedSeconds ??
      (typeof schema?.constraints?.video_extension_added_seconds === 'number'
        ? schema.constraints.video_extension_added_seconds
        : null),
    maxExtensionCount:
      schema?.videoContract?.extensionConstraints?.maxExtensionCount ??
      (typeof schema?.constraints?.max_video_extension_count === 'number'
        ? schema.constraints.max_video_extension_count
        : null),
    maxSourceVideoSeconds:
      schema?.videoContract?.extensionConstraints?.maxSourceVideoSeconds ??
      (typeof schema?.constraints?.max_source_video_seconds === 'number'
        ? schema.constraints.max_source_video_seconds
        : null),
    maxOutputVideoSeconds:
      schema?.videoContract?.extensionConstraints?.maxOutputVideoSeconds ??
      (typeof schema?.constraints?.max_output_video_seconds === 'number'
        ? schema.constraints.max_output_video_seconds
        : null),
    requireDurationSeconds: schema?.videoContract?.extensionConstraints?.requireDurationSeconds ?? [],
    requireResolutionValues: schema?.videoContract?.extensionConstraints?.requireResolutionValues ?? [],
  };
  const defaultAspectRatio =
    (typeof defaults.aspect_ratio === 'string' ? defaults.aspect_ratio : undefined) ??
    validAspectRatios[0] ??
    '16:9';
  const defaultResolution =
    (typeof defaults.resolution === 'string' ? defaults.resolution : undefined) ??
    validResolutionTiers[0] ??
    '720p';
  const defaultVideoSeconds =
    (typeof defaults.seconds === 'string' ? defaults.seconds : undefined) ??
    (typeof defaults.seconds === 'number' ? String(defaults.seconds) : undefined) ??
    validSeconds[0] ??
    '8';
  const validCountsForDefaultSeconds = validVideoExtensionCountsBySeconds[defaultVideoSeconds] ?? [];
  const defaultVideoExtensionCount =
    typeof defaults.video_extension_count === 'number' &&
    (validCountsForDefaultSeconds.length === 0 || validCountsForDefaultSeconds.includes(defaults.video_extension_count))
      ? defaults.video_extension_count
      : validCountsForDefaultSeconds[0] ?? 0;
  const defaultStoryboardShotSeconds =
    typeof defaults.storyboard_shot_seconds === 'number' &&
    (validStoryboardShotSeconds.length === 0 || validStoryboardShotSeconds.includes(defaults.storyboard_shot_seconds))
      ? defaults.storyboard_shot_seconds
      : validStoryboardShotSeconds[0] ?? 4;
  const defaultGenerateAudio =
    typeof defaults.generate_audio === 'boolean'
      ? defaults.generate_audio
      : typeof fieldPolicies.generateAudioForcedValue === 'boolean'
        ? fieldPolicies.generateAudioForcedValue
        : false;
  const defaultPersonGeneration =
    typeof defaults.person_generation === 'string' &&
    (validPersonGenerationValues.length === 0 || validPersonGenerationValues.includes(defaults.person_generation))
      ? defaults.person_generation
      : validPersonGenerationValues[0] ?? '';
  const defaultSubtitleMode =
    typeof defaults.subtitle_mode === 'string' &&
    (validSubtitleModes.length === 0 || validSubtitleModes.includes(defaults.subtitle_mode))
      ? defaults.subtitle_mode
      : validSubtitleModes.includes('none')
        ? 'none'
        : fieldPolicies.subtitleModeDefaultEnabled ?? validSubtitleModes[0] ?? 'none';
  const defaultSubtitleLanguage =
    typeof defaults.subtitle_language === 'string' &&
    (validSubtitleLanguages.length === 0 || validSubtitleLanguages.includes(defaults.subtitle_language))
      ? defaults.subtitle_language
      : validSubtitleLanguages[0] ?? '';
  const defaultSubtitleScript = typeof defaults.subtitle_script === 'string' ? defaults.subtitle_script : '';
  const defaultStoryboardPrompt =
    typeof defaults.storyboard_prompt === 'string' ? defaults.storyboard_prompt : '';
  const defaultNegativePrompt =
    typeof defaults.negative_prompt === 'string' ? defaults.negative_prompt : '';
  const defaultSeed = typeof defaults.seed === 'number' ? defaults.seed : -1;
  const defaultEnhancePrompt =
    typeof defaults.enhance_prompt === 'boolean'
      ? defaults.enhance_prompt
      : fieldPolicies.enhancePromptEffectiveDefault ||
        fieldPolicies.enhancePromptMandatory ||
        true;

  return {
    defaultAspectRatio,
    defaultResolution,
    defaultVideoSeconds,
    defaultVideoExtensionCount,
    defaultStoryboardShotSeconds,
    defaultGenerateAudio,
    defaultPersonGeneration,
    defaultSubtitleMode,
    defaultSubtitleLanguage,
    defaultSubtitleScript,
    defaultStoryboardPrompt,
    defaultNegativePrompt,
    defaultSeed,
    defaultEnhancePrompt,
    validAspectRatios,
    validResolutionTiers,
    validSeconds,
    validVideoExtensionCounts,
    validStoryboardShotSeconds,
    validPersonGenerationValues,
    validSubtitleModes,
    validSubtitleLanguages,
    validVideoExtensionCountsBySeconds,
    extensionOptionsBySeconds,
    fieldPolicies,
    extensionConstraints,
    schemaReady: validAspectRatios.length > 0 && validResolutionTiers.length > 0,
  };
}

export function getVideoExtensionOptions(
  contract: VideoControlContract,
  baseSeconds: string
): VideoContractExtensionOption[] {
  return contract.extensionOptionsBySeconds[baseSeconds] ?? [];
}

export function isVideoControlSelectionValid(
  contract: VideoControlContract,
  selection: VideoControlSelection
): boolean {
  const aspectRatioValid =
    contract.validAspectRatios.length === 0 ||
    contract.validAspectRatios.includes(selection.aspectRatio);
  const resolutionValid =
    contract.validResolutionTiers.length === 0 ||
    contract.validResolutionTiers.includes(selection.resolution);
  const secondsValid =
    contract.validSeconds.length === 0 ||
    contract.validSeconds.includes(selection.videoSeconds);
  const validCountsForSeconds = contract.validVideoExtensionCountsBySeconds[selection.videoSeconds] ?? [];
  const videoExtensionCountValid =
    selection.videoExtensionCount === undefined ||
    (validCountsForSeconds.length > 0
      ? validCountsForSeconds.includes(selection.videoExtensionCount)
      : contract.validVideoExtensionCounts.length === 0 ||
        contract.validVideoExtensionCounts.includes(selection.videoExtensionCount));

  return aspectRatioValid && resolutionValid && secondsValid && videoExtensionCountValid;
}
