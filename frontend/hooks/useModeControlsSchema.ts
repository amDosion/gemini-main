import { useEffect, useMemo, useState } from 'react';
import { requestJson } from '../services/http';

type ResolutionMap = Record<string, Record<string, string>>;
type OptionValue = string | number | boolean;
type ParamOption = { label: string; value: OptionValue };
type ParamOptionsMap = Record<string, ParamOption[]>;
type NumericRange = { min?: number; max?: number; step?: number };
type NumericRangesMap = Record<string, NumericRange>;
type AspectRatioOption = { label: string; value: string };
type ResolutionTierOption = { label: string; value: string; baseResolution: string };
type VideoContractSupports = Record<string, boolean>;

export interface VideoContractAttachmentSlot {
  name: string;
  label?: string;
  kind?: string;
  multiple?: boolean;
  required?: boolean;
  roles?: string[];
  enabled?: boolean;
  maxItems?: number;
}

export interface VideoContractInputStrategy {
  id: string;
  label?: string;
  requires?: string[];
  allows?: string[];
}

export interface VideoContractEnhancePromptPolicy {
  mandatory?: boolean;
  lockedWhenMandatory?: boolean;
  effectiveDefault?: boolean;
}

export interface VideoContractTogglePolicy {
  available?: boolean;
  forcedValue?: OptionValue | null;
}

export interface VideoContractSubtitlePolicy {
  available?: boolean;
  singleSidecarFormat?: boolean;
  defaultEnabledMode?: string | null;
  supportedValues?: string[];
}

export interface VideoContractStoryboardPromptPolicy {
  preferred?: boolean;
  deprecatedCompanionFields?: string[];
}

export interface VideoContractFieldPolicies {
  enhancePrompt?: VideoContractEnhancePromptPolicy;
  generateAudio?: VideoContractTogglePolicy;
  personGeneration?: VideoContractTogglePolicy;
  subtitleMode?: VideoContractSubtitlePolicy;
  storyboardPrompt?: VideoContractStoryboardPromptPolicy;
}

export interface VideoContractExtensionOption {
  count: number;
  label: string;
  totalSeconds: number;
}

export interface VideoContractExtensionMatrixEntry {
  baseSeconds: string;
  options: VideoContractExtensionOption[];
}

export interface VideoContractExtensionConstraints {
  addedSeconds?: number;
  maxExtensionCount?: number;
  maxSourceVideoSeconds?: number;
  maxOutputVideoSeconds?: number;
  requireDurationSeconds?: string[];
  requireResolutionValues?: string[];
}

export interface VideoContract {
  version?: string;
  runtimeApiMode?: string;
  supports?: VideoContractSupports;
  attachmentSlots?: VideoContractAttachmentSlot[];
  inputStrategies?: VideoContractInputStrategy[];
  fieldPolicies?: VideoContractFieldPolicies;
  normalizationRules?: string[];
  extensionDurationMatrix?: VideoContractExtensionMatrixEntry[];
  extensionConstraints?: VideoContractExtensionConstraints;
}

export interface ModeControlsSchema {
  schemaVersion?: string;
  provider: string;
  mode: string;
  requestedMode?: string;
  modelId?: string;
  defaults?: Record<string, unknown>;
  constraints?: Record<string, unknown>;
  aspectRatios?: AspectRatioOption[];
  resolutionTiers?: ResolutionTierOption[];
  resolutionMap?: ResolutionMap;
  paramOptions?: ParamOptionsMap;
  numericRanges?: NumericRangesMap;
  videoContract?: VideoContract;
}

type ControlsApiResponse = {
  success: boolean;
  provider: string;
  mode: string;
  modelId?: string;
  schema?: Record<string, unknown>;
};

const schemaCache = new Map<string, ModeControlsSchema>();

const FALLBACK_VIDEO_RESOLUTION_MAP: ResolutionMap = {
  '720p': {
    '16:9': '1280×720',
    '9:16': '720×1280',
  },
  '1080p': {
    '16:9': '1920×1080',
    '9:16': '1080×1920',
  },
  '4k': {
    '16:9': '3840×2160',
    '9:16': '2160×3840',
  },
};

const ABORT_MESSAGE = 'Request cancelled by user';

const isAbortRequestError = (error: unknown): boolean => {
  if (!(error instanceof Error)) return false;
  return error.name === 'AbortError' || error.message === ABORT_MESSAGE;
};

function normalizeAspectRatios(raw: unknown): AspectRatioOption[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  const options: AspectRatioOption[] = [];
  for (const item of raw) {
    if (typeof item === 'string') {
      options.push({ label: item, value: item });
      continue;
    }
    if (item && typeof item === 'object' && typeof item.value === 'string') {
      options.push({
        label: typeof item.label === 'string' ? item.label : item.value,
        value: item.value,
      });
    }
  }
  return options;
}

function normalizeResolutionTiers(raw: unknown): ResolutionTierOption[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  const options: ResolutionTierOption[] = [];
  for (const item of raw) {
    if (typeof item === 'string') {
      options.push({ label: item, value: item, baseResolution: item });
      continue;
    }
    if (item && typeof item === 'object' && typeof item.value === 'string') {
      options.push({
        label: typeof item.label === 'string' ? item.label : item.value,
        value: item.value,
        baseResolution: typeof item.baseResolution === 'string' ? item.baseResolution : item.value,
      });
    }
  }
  return options;
}

function normalizeResolutionMap(raw: unknown): ResolutionMap | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const result: ResolutionMap = {};
  for (const [tier, mapping] of Object.entries(raw)) {
    if (!mapping || typeof mapping !== 'object') continue;
    const typed: Record<string, string> = {};
    for (const [ratio, value] of Object.entries(mapping as Record<string, unknown>)) {
      if (typeof value === 'string') typed[ratio] = value;
    }
    result[tier] = typed;
  }
  return result;
}

function normalizeParamOptions(raw: unknown): ParamOptionsMap | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const result: ParamOptionsMap = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (!Array.isArray(value)) continue;
    const options: ParamOption[] = [];
    for (const item of value) {
      if (
        item &&
        typeof item === 'object' &&
        'value' in item &&
        (typeof (item as Record<string, unknown>).value === 'string' ||
          typeof (item as Record<string, unknown>).value === 'number' ||
          typeof (item as Record<string, unknown>).value === 'boolean')
      ) {
        const v = (item as Record<string, unknown>).value as OptionValue;
        options.push({
          label: typeof (item as Record<string, unknown>).label === 'string' ? (item as Record<string, unknown>).label as string : String(v),
          value: v,
        });
      } else if (typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean') {
        options.push({ label: String(item), value: item });
      }
    }
    result[key] = options;
  }
  return result;
}

function normalizeNumericRanges(raw: unknown): NumericRangesMap | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const result: NumericRangesMap = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (!value || typeof value !== 'object') continue;
    const min = (value as Record<string, unknown>).min;
    const max = (value as Record<string, unknown>).max;
    const step = (value as Record<string, unknown>).step;
    result[key] = {
      min: typeof min === 'number' ? min : undefined,
      max: typeof max === 'number' ? max : undefined,
      step: typeof step === 'number' ? step : undefined,
    };
  }
  return result;
}

function normalizeStringArray(raw: unknown): string[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  const result = raw
    .map((item) => (typeof item === 'string' ? item : null))
    .filter((value): value is string => Boolean(value && value.length > 0));
  return result.length > 0 ? result : undefined;
}

function normalizeVideoContractAttachmentSlots(raw: unknown): VideoContractAttachmentSlot[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  const result: VideoContractAttachmentSlot[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object' || typeof item.name !== 'string') continue;
    result.push({
      name: item.name,
      label: typeof item.label === 'string' ? item.label : undefined,
      kind: typeof item.kind === 'string' ? item.kind : undefined,
      multiple: typeof item.multiple === 'boolean' ? item.multiple : undefined,
      required: typeof item.required === 'boolean' ? item.required : undefined,
      roles: normalizeStringArray(item.roles),
      enabled: typeof item.enabled === 'boolean' ? item.enabled : undefined,
      maxItems:
        typeof item.maxItems === 'number'
          ? item.maxItems
          : typeof item.max_items === 'number'
            ? item.max_items
            : undefined,
    });
  }
  return result.length > 0 ? result : undefined;
}

function normalizeVideoContractInputStrategies(raw: unknown): VideoContractInputStrategy[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  const result: VideoContractInputStrategy[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object' || typeof item.id !== 'string') continue;
    result.push({
      id: item.id,
      label: typeof item.label === 'string' ? item.label : undefined,
      requires: normalizeStringArray(item.requires),
      allows: normalizeStringArray(item.allows),
    });
  }
  return result.length > 0 ? result : undefined;
}

function normalizeVideoContractExtensionMatrix(
  raw: unknown
): VideoContractExtensionMatrixEntry[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  const result: VideoContractExtensionMatrixEntry[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const baseSeconds =
      typeof item.baseSeconds === 'string'
        ? item.baseSeconds
        : typeof item.base_seconds === 'string'
          ? item.base_seconds
          : undefined;
    if (!baseSeconds) continue;
    const optionsRaw = Array.isArray(item.options) ? item.options : [];
    const options: VideoContractExtensionOption[] = [];
    for (const option of optionsRaw) {
      if (!option || typeof option !== 'object') continue;
      const count =
        typeof option.count === 'number'
          ? option.count
          : typeof option.count === 'string'
            ? Number(option.count)
            : NaN;
      const totalSeconds =
        typeof option.totalSeconds === 'number'
          ? option.totalSeconds
          : typeof option.total_seconds === 'number'
            ? option.total_seconds
            : typeof option.totalSeconds === 'string'
              ? Number(option.totalSeconds)
              : typeof option.total_seconds === 'string'
                ? Number(option.total_seconds)
                : NaN;
      if (!Number.isFinite(count) || !Number.isFinite(totalSeconds)) continue;
      options.push({
        count,
        label: typeof option.label === 'string' ? option.label : `${totalSeconds}s`,
        totalSeconds,
      });
    }
    result.push({ baseSeconds, options });
  }
  return result.length > 0 ? result : undefined;
}

function normalizeVideoContract(raw: unknown): VideoContract | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const obj = raw as Record<string, unknown>;

  const supportsRaw = obj.supports as Record<string, unknown> | undefined;
  const supports: VideoContractSupports | undefined =
    supportsRaw && typeof supportsRaw === 'object'
      ? (Object.fromEntries(
          Object.entries(supportsRaw).filter(([, value]) => typeof value === 'boolean')
        ) as VideoContractSupports)
      : undefined;

  const fieldPoliciesRaw = (obj.fieldPolicies ?? obj.field_policies) as Record<string, unknown> | undefined;
  const _fpEnhance = (fieldPoliciesRaw?.enhancePrompt ?? fieldPoliciesRaw?.enhance_prompt) as Record<string, unknown> | undefined;
  const _fpAudio = (fieldPoliciesRaw?.generateAudio ?? fieldPoliciesRaw?.generate_audio) as Record<string, unknown> | undefined;
  const _fpPerson = (fieldPoliciesRaw?.personGeneration ?? fieldPoliciesRaw?.person_generation) as Record<string, unknown> | undefined;
  const _fpSubtitle = (fieldPoliciesRaw?.subtitleMode ?? fieldPoliciesRaw?.subtitle_mode) as Record<string, unknown> | undefined;
  const _fpStoryboard = (fieldPoliciesRaw?.storyboardPrompt ?? fieldPoliciesRaw?.storyboard_prompt) as Record<string, unknown> | undefined;
  const fieldPolicies: VideoContractFieldPolicies | undefined =
    fieldPoliciesRaw && typeof fieldPoliciesRaw === 'object'
      ? {
          enhancePrompt:
            _fpEnhance
              ? {
                  mandatory:
                    typeof _fpEnhance
                      ?.mandatory === 'boolean'
                      ? Boolean(
                          _fpEnhance.mandatory
                        )
                      : undefined,
                  lockedWhenMandatory:
                    typeof _fpEnhance
                      ?.lockedWhenMandatory === 'boolean'
                      ? Boolean(
                          _fpEnhance
                            .lockedWhenMandatory
                        )
                      : typeof _fpEnhance
                            ?.locked_when_mandatory === 'boolean'
                        ? Boolean(
                            _fpEnhance
                              .locked_when_mandatory
                          )
                        : undefined,
                  effectiveDefault:
                    typeof _fpEnhance
                      ?.effectiveDefault === 'boolean'
                      ? Boolean(
                          _fpEnhance
                            .effectiveDefault
                        )
                      : typeof _fpEnhance
                            ?.effective_default === 'boolean'
                        ? Boolean(
                            _fpEnhance
                              .effective_default
                          )
                        : undefined,
                }
              : undefined,
          generateAudio:
            _fpAudio
              ? {
                  available:
                    typeof _fpAudio
                      ?.available === 'boolean'
                      ? Boolean(
                          _fpAudio.available
                        )
                      : undefined,
                  forcedValue:
                    'forcedValue' in _fpAudio
                      ? _fpAudio
                          .forcedValue as OptionValue ?? null
                      : 'forced_value' in _fpAudio
                        ? _fpAudio
                            .forced_value as OptionValue ?? null
                        : undefined,
                }
              : undefined,
          personGeneration:
            _fpPerson
              ? {
                  available:
                    typeof _fpPerson
                      ?.available === 'boolean'
                      ? Boolean(
                          _fpPerson.available
                        )
                      : undefined,
                  forcedValue:
                    'forcedValue' in _fpPerson
                      ? _fpPerson
                          .forcedValue as OptionValue ?? null
                      : 'forced_value' in _fpPerson
                        ? _fpPerson
                            .forced_value as OptionValue ?? null
                        : undefined,
                }
              : undefined,
          subtitleMode:
            _fpSubtitle
              ? {
                  available:
                    typeof _fpSubtitle
                      ?.available === 'boolean'
                      ? Boolean(
                          _fpSubtitle.available
                        )
                      : undefined,
                  singleSidecarFormat:
                    typeof _fpSubtitle
                      ?.singleSidecarFormat === 'boolean'
                      ? Boolean(
                          _fpSubtitle
                            .singleSidecarFormat
                        )
                      : typeof _fpSubtitle
                            ?.single_sidecar_format === 'boolean'
                        ? Boolean(
                            _fpSubtitle
                              .single_sidecar_format
                          )
                        : undefined,
                  defaultEnabledMode:
                    typeof _fpSubtitle
                      ?.defaultEnabledMode === 'string'
                      ? _fpSubtitle
                          .defaultEnabledMode
                      : typeof _fpSubtitle
                            ?.default_enabled_mode === 'string'
                        ? _fpSubtitle
                            .default_enabled_mode
                        : undefined,
                  supportedValues: normalizeStringArray(
                    _fpSubtitle?.supportedValues ??
                      _fpSubtitle?.supported_values
                  ),
                }
              : undefined,
          storyboardPrompt:
            _fpStoryboard
              ? {
                  preferred:
                    typeof _fpStoryboard
                      ?.preferred === 'boolean'
                      ? Boolean(
                          _fpStoryboard.preferred
                        )
                      : undefined,
                  deprecatedCompanionFields: normalizeStringArray(
                    _fpStoryboard
                      ?.deprecatedCompanionFields ??
                      _fpStoryboard
                        ?.deprecated_companion_fields
                  ),
                }
              : undefined,
        }
      : undefined;

  const extensionConstraintsRaw = (obj.extensionConstraints ?? obj.extension_constraints) as Record<string, unknown> | undefined;
  const extensionConstraints: VideoContractExtensionConstraints | undefined =
    extensionConstraintsRaw && typeof extensionConstraintsRaw === 'object'
      ? {
          addedSeconds:
            typeof extensionConstraintsRaw.addedSeconds === 'number'
              ? extensionConstraintsRaw.addedSeconds
              : typeof extensionConstraintsRaw.added_seconds === 'number'
                ? extensionConstraintsRaw.added_seconds
                : undefined,
          maxExtensionCount:
            typeof extensionConstraintsRaw.maxExtensionCount === 'number'
              ? extensionConstraintsRaw.maxExtensionCount
              : typeof extensionConstraintsRaw.max_extension_count === 'number'
                ? extensionConstraintsRaw.max_extension_count
                : undefined,
          maxSourceVideoSeconds:
            typeof extensionConstraintsRaw.maxSourceVideoSeconds === 'number'
              ? extensionConstraintsRaw.maxSourceVideoSeconds
              : typeof extensionConstraintsRaw.max_source_video_seconds === 'number'
                ? extensionConstraintsRaw.max_source_video_seconds
                : undefined,
          maxOutputVideoSeconds:
            typeof extensionConstraintsRaw.maxOutputVideoSeconds === 'number'
              ? extensionConstraintsRaw.maxOutputVideoSeconds
              : typeof extensionConstraintsRaw.max_output_video_seconds === 'number'
                ? extensionConstraintsRaw.max_output_video_seconds
                : undefined,
          requireDurationSeconds: normalizeStringArray(
            extensionConstraintsRaw.requireDurationSeconds ?? extensionConstraintsRaw.require_duration_seconds
          ),
          requireResolutionValues: normalizeStringArray(
            extensionConstraintsRaw.requireResolutionValues ?? extensionConstraintsRaw.require_resolution_values
          ),
        }
      : undefined;

  return {
    version: typeof obj.version === 'string' ? obj.version : undefined,
    runtimeApiMode:
      typeof obj.runtimeApiMode === 'string'
        ? obj.runtimeApiMode
        : typeof obj.runtime_api_mode === 'string'
          ? obj.runtime_api_mode
          : undefined,
    supports,
    attachmentSlots: normalizeVideoContractAttachmentSlots(obj.attachmentSlots ?? obj.attachment_slots),
    inputStrategies: normalizeVideoContractInputStrategies(obj.inputStrategies ?? obj.input_strategies),
    fieldPolicies,
    normalizationRules: normalizeStringArray(obj.normalizationRules ?? obj.normalization_rules),
    extensionDurationMatrix: normalizeVideoContractExtensionMatrix(
      obj.extensionDurationMatrix ?? obj.extension_duration_matrix
    ),
    extensionConstraints,
  };
}

function normalizeSchema(raw: Record<string, unknown> | undefined): ModeControlsSchema | null {
  if (!raw || typeof raw !== 'object') return null;
  const provider = typeof raw.provider === 'string' ? raw.provider : '';
  const mode = typeof raw.mode === 'string' ? raw.mode : '';
  if (!provider || !mode) return null;

  return {
    schemaVersion:
      typeof raw.schemaVersion === 'string'
        ? raw.schemaVersion
        : typeof raw.schema_version === 'string'
          ? raw.schema_version
          : undefined,
    provider,
    mode,
    requestedMode:
      typeof raw.requestedMode === 'string'
        ? raw.requestedMode
        : typeof raw.requested_mode === 'string'
          ? raw.requested_mode
          : undefined,
    modelId:
      typeof raw.modelId === 'string'
        ? raw.modelId
        : typeof raw.model_id === 'string'
          ? raw.model_id
          : undefined,
    defaults: raw.defaults && typeof raw.defaults === 'object' ? raw.defaults as Record<string, unknown> : undefined,
    constraints: raw.constraints && typeof raw.constraints === 'object' ? raw.constraints as Record<string, unknown> : undefined,
    aspectRatios: normalizeAspectRatios(raw.aspectRatios ?? raw.aspect_ratios),
    resolutionTiers: normalizeResolutionTiers(raw.resolutionTiers ?? raw.resolution_tiers),
    resolutionMap: normalizeResolutionMap(raw.resolutionMap ?? raw.resolution_map),
    paramOptions: normalizeParamOptions(raw.paramOptions ?? raw.param_options),
    numericRanges: normalizeNumericRanges(raw.numericRanges ?? raw.numeric_ranges),
    videoContract: normalizeVideoContract(raw.videoContract ?? raw.video_contract),
  };
}

function buildCacheKey(providerId: string, mode: string, modelId?: string): string {
  return `${providerId}::${mode}::${modelId || ''}`;
}

export function getPixelResolutionFromSchema(
  schema: ModeControlsSchema | null | undefined,
  aspectRatio: string,
  resolutionTier: string
): string | null {
  const map = schema?.resolutionMap ?? FALLBACK_VIDEO_RESOLUTION_MAP;
  if (!map) return null;
  const tierMap = map[resolutionTier] || map['720p'];
  if (!tierMap) return null;
  return tierMap[aspectRatio] || tierMap['1:1'] || null;
}

export function useModeControlsSchema(
  providerId: string | undefined,
  mode: string,
  modelId?: string
) {
  const cacheKey = useMemo(
    () => buildCacheKey(providerId || '', mode, modelId),
    [providerId, mode, modelId]
  );

  const [schema, setSchema] = useState<ModeControlsSchema | null>(
    providerId ? (schemaCache.get(cacheKey) || null) : null
  );
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!providerId) {
      setSchema(null);
      setLoading(false);
      setError(null);
      return;
    }

    const cached = schemaCache.get(cacheKey);
    if (cached) {
      setSchema(cached);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    let active = true;
    setLoading(true);

    const params = new URLSearchParams();
    if (modelId) {
      params.set('model_id', modelId);
    }

    const query = params.toString();
    const requestUrl = `/api/modes/${providerId}/${mode}/controls${query ? `?${query}` : ''}`;

    void requestJson<ControlsApiResponse>(requestUrl, {
      method: 'GET',
      withAuth: true,
      signal: controller.signal,
      timeoutMs: 0,
      errorMessage: 'Failed to fetch controls schema',
    })
      .then((data) => {
        if (!active || controller.signal.aborted) return;
        const normalized = normalizeSchema(data.schema);
        if (!normalized) {
          throw new Error('Invalid controls schema payload');
        }
        schemaCache.set(cacheKey, normalized);
        setSchema(normalized);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!active || controller.signal.aborted || isAbortRequestError(err)) return;
        const message = err instanceof Error ? err.message : 'Failed to fetch controls schema';
        setError(message || 'Failed to fetch controls schema');
        setSchema(null);
      })
      .finally(() => {
        if (!active || controller.signal.aborted) return;
        setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [providerId, mode, modelId, cacheKey]);

  return { schema, loading, error };
}
