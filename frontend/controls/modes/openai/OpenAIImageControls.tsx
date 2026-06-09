/**
 * OpenAI GPT Image controls shared by text-to-image and image-to-image modes.
 */
import React, { useEffect, useMemo, useRef } from 'react';
import {
  FileImage,
  Gauge,
  Image as ImageIcon,
  Layers,
  Ratio,
  ShieldCheck,
  SlidersHorizontal,
} from 'lucide-react';
import { AppMode, ModelConfig } from '../../../types/types';
import { ControlsState } from '../../types';
import PromptEnhanceControl from '../../shared/PromptEnhanceControl';
import { useEnhancePromptModels } from '../../../hooks/useEnhancePromptModels';
import {
  getPixelResolutionFromSchema,
  ModeControlsSchema,
  useModeControlsSchema,
} from '../../../hooks/useModeControlsSchema';

type OptionValue = string | number | boolean;
type Option = { label: string; value: OptionValue };

// 模块级稳定空函数:作为缺失 setter 的回退。内联 (() => {}) 每次渲染换新身份,
// 当这些 setter 出现在 useEffect 依赖数组里时会导致 effect 每渲染都重跑。
const NOOP = (): void => {};

export interface OpenAIImageControlsProps {
  providerId?: string;
  mode: AppMode | 'image-edit';
  currentModel?: ModelConfig;
  controls?: Partial<ControlsState>;
  aspectRatio?: string;
  setAspectRatio?: (value: string) => void;
  resolution?: string;
  setResolution?: (value: string) => void;
  numberOfImages?: number;
  setNumberOfImages?: (value: number) => void;
  availableModels?: ModelConfig[];
  controlsSchema?: ModeControlsSchema | null;
  controlsSchemaLoading?: boolean;
  controlsSchemaError?: string | null;
}

export const OpenAIImageControls: React.FC<OpenAIImageControlsProps> = ({
  providerId = 'openai',
  mode,
  currentModel,
  controls,
  aspectRatio: propAspectRatio,
  setAspectRatio: propSetAspectRatio,
  resolution: propResolution,
  setResolution: propSetResolution,
  numberOfImages: propNumberOfImages,
  setNumberOfImages: propSetNumberOfImages,
  availableModels,
  controlsSchema,
  controlsSchemaLoading,
  controlsSchemaError,
}) => {
  const schemaMode = (mode === 'image-edit' ? 'image-chat-edit' : mode) as AppMode;
  const shouldFetchSchema = controlsSchema === undefined;
  const fetched = useModeControlsSchema(providerId, schemaMode, currentModel?.id, {
    enabled: shouldFetchSchema,
  });
  const schema = controlsSchema === undefined ? fetched.schema : controlsSchema;
  const loading = controlsSchemaLoading ?? (controlsSchema === undefined ? fetched.loading : false);
  const error = controlsSchemaError ?? (controlsSchema === undefined ? fetched.error : null);
  const availableRatios = useMemo(() => schema?.aspectRatios ?? [], [schema]);
  const availableResolutions = useMemo(() => schema?.resolutionTiers ?? [], [schema]);
  const paramOptions = schema?.paramOptions ?? {};
  const imageCountOptions = useMemo(
    () =>
      (paramOptions.number_of_images ?? [])
        .map((option) => option.value)
        .filter((value): value is number => typeof value === 'number'),
    [paramOptions.number_of_images]
  );
  const defaults = schema?.defaults ?? {};
  const defaultAspectRatio =
    (typeof defaults.aspect_ratio === 'string' ? defaults.aspect_ratio : undefined) ??
    availableRatios[0]?.value ??
    '1:1';
  const defaultResolution =
    (typeof defaults.resolution === 'string' ? defaults.resolution : undefined) ??
    availableResolutions[0]?.value ??
    '1K';
  const defaultQuality =
    (typeof defaults.quality === 'string' ? defaults.quality : undefined) ??
    String(paramOptions.quality?.[0]?.value ?? 'auto');
  const defaultBackground =
    (typeof defaults.background === 'string' ? defaults.background : undefined) ??
    String(paramOptions.background?.[0]?.value ?? 'auto');
  const defaultModeration =
    (typeof defaults.moderation === 'string' ? defaults.moderation : undefined) ??
    String(paramOptions.moderation?.[0]?.value ?? 'auto');
  const defaultOutputFormat =
    (typeof defaults.output_format === 'string' ? defaults.output_format : undefined) ??
    String(paramOptions.output_format?.[0]?.value ?? 'png');
  const maxImageCount =
    typeof schema?.constraints?.max_image_count === 'number'
      ? schema.constraints.max_image_count
      : 1;
  const minImageCount = imageCountOptions.length ? Math.min(...imageCountOptions) : 1;
  const maxSelectableImageCount = imageCountOptions.length
    ? Math.min(maxImageCount, Math.max(...imageCountOptions))
    : maxImageCount;
  const compressionRange = schema?.numericRanges?.output_compression_quality;

  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? defaultAspectRatio;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? NOOP;
  const resolution = controls?.resolution ?? propResolution ?? defaultResolution;
  const setResolution = controls?.setResolution ?? propSetResolution ?? NOOP;
  const numberOfImages = controls?.numberOfImages ?? propNumberOfImages ?? 1;
  const setNumberOfImages = controls?.setNumberOfImages ?? propSetNumberOfImages ?? NOOP;
  const quality = controls?.quality ?? defaultQuality;
  const setQuality = controls?.setQuality ?? NOOP;
  const background = controls?.background ?? defaultBackground;
  const setBackground = controls?.setBackground ?? NOOP;
  const moderation = controls?.moderation ?? defaultModeration;
  const setModeration = controls?.setModeration ?? NOOP;
  const outputFormat = controls?.outputFormat ?? defaultOutputFormat;
  const setOutputFormat = controls?.setOutputFormat ?? NOOP;
  const outputCompressionQuality =
    controls?.outputCompressionQuality ??
    (typeof defaults.output_compression_quality === 'number'
      ? defaults.output_compression_quality
      : (compressionRange?.max ?? 100));
  const setOutputCompressionQuality = controls?.setOutputCompressionQuality ?? NOOP;
  const defaultEnhancePrompt =
    typeof defaults.enhance_prompt === 'boolean' ? defaults.enhance_prompt : false;
  const enhancePrompt = controls?.enhancePrompt ?? false;
  const setEnhancePrompt = controls?.setEnhancePrompt ?? NOOP;
  const canToggleEnhancePrompt = typeof controls?.setEnhancePrompt === 'function';
  const enhancePromptModel = controls?.enhancePromptModel ?? '';
  const setEnhancePromptModel = controls?.setEnhancePromptModel;
  const enhancePromptThinkingLevel = controls?.enhancePromptThinkingLevel ?? 'auto';
  const setEnhancePromptThinkingLevel = controls?.setEnhancePromptThinkingLevel;
  const enhancePromptModels = useEnhancePromptModels(providerId, availableModels);
  const schemaDefaultSyncKey = [
    providerId,
    schemaMode,
    currentModel?.id ?? '',
    schema?.schemaVersion ?? '',
    defaultAspectRatio,
    defaultResolution,
    String(defaultEnhancePrompt),
  ].join('|');
  const lastSchemaDefaultSyncKey = useRef('');

  useEffect(() => {
    if (loading || !schema || lastSchemaDefaultSyncKey.current === schemaDefaultSyncKey) {
      return;
    }
    lastSchemaDefaultSyncKey.current = schemaDefaultSyncKey;

    const validRatios = availableRatios.map((ratio) => ratio.value);
    if (validRatios.includes(defaultAspectRatio) && aspectRatio !== defaultAspectRatio) {
      setAspectRatio(defaultAspectRatio);
    }

    const validResolutions = availableResolutions.map((tier) => tier.value);
    if (validResolutions.includes(defaultResolution) && resolution !== defaultResolution) {
      setResolution(defaultResolution);
    }

    if (controls?.setEnhancePrompt && controls.enhancePrompt !== defaultEnhancePrompt) {
      controls.setEnhancePrompt(defaultEnhancePrompt);
    }
  }, [
    loading,
    schema,
    schemaDefaultSyncKey,
    availableRatios,
    availableResolutions,
    defaultAspectRatio,
    defaultResolution,
    defaultEnhancePrompt,
    aspectRatio,
    resolution,
    setAspectRatio,
    setResolution,
    controls,
  ]);

  useEffect(() => {
    const validRatios = availableRatios.map((ratio) => ratio.value);
    if (validRatios.length > 0 && !validRatios.includes(aspectRatio)) {
      setAspectRatio(validRatios[0]);
    }
  }, [availableRatios, aspectRatio, setAspectRatio]);

  useEffect(() => {
    const validResolutions = availableResolutions.map((tier) => tier.value);
    if (validResolutions.length > 0 && !validResolutions.includes(resolution)) {
      setResolution(validResolutions[0]);
    }
  }, [availableResolutions, resolution, setResolution]);

  useEffect(() => {
    if (numberOfImages < minImageCount) {
      setNumberOfImages(minImageCount);
      return;
    }
    if (numberOfImages > maxSelectableImageCount) {
      setNumberOfImages(maxSelectableImageCount);
    }
  }, [maxSelectableImageCount, minImageCount, numberOfImages, setNumberOfImages]);

  useEffect(() => {
    syncStringOption(paramOptions.quality, quality, setQuality);
  }, [paramOptions.quality, quality, setQuality]);

  useEffect(() => {
    syncStringOption(paramOptions.background, background, setBackground);
  }, [paramOptions.background, background, setBackground]);

  useEffect(() => {
    syncStringOption(paramOptions.moderation, moderation, setModeration);
  }, [paramOptions.moderation, moderation, setModeration]);

  useEffect(() => {
    syncStringOption(paramOptions.output_format, outputFormat, setOutputFormat);
  }, [paramOptions.output_format, outputFormat, setOutputFormat]);

  const currentPixelResolution = useMemo(() => {
    const schemaPixelRes = getPixelResolutionFromSchema(schema, aspectRatio, resolution);
    return schemaPixelRes ? schemaPixelRes.replace('*', 'x') : '';
  }, [schema, aspectRatio, resolution]);

  return (
    <div className="space-y-4">
      {!loading && (error || availableRatios.length === 0) && (
        <div className="text-[10px] text-rose-400">
          比例配置加载失败，请检查后端 `mode_controls_catalog.json`。
        </div>
      )}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Ratio size={12} className="text-emerald-400" />
            <span className="text-xs text-slate-300">图片比例</span>
          </div>
          {currentPixelResolution && (
            <span className="text-[10px] text-emerald-400 font-mono">{currentPixelResolution}</span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {availableRatios.map((ratio) => (
            <button
              key={ratio.value}
              onClick={() => setAspectRatio(ratio.value)}
              className={`py-1.5 text-[10px] font-medium rounded-lg transition-all ${
                aspectRatio === ratio.value
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {ratio.value}
            </button>
          ))}
        </div>
      </div>

      {availableResolutions.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <ImageIcon size={12} className="text-sky-400" />
            <span className="text-xs text-slate-300">分辨率</span>
          </div>
          <div className="flex gap-2">
            {availableResolutions.map((tier) => {
              const schemaPixelRes = getPixelResolutionFromSchema(schema, aspectRatio, tier.value);
              const tierPixelRes = schemaPixelRes ? schemaPixelRes.replace('*', 'x') : '--';
              const tierLabel = tier.label || tier.value;
              return (
                <button
                  key={tier.value}
                  onClick={() => setResolution(tier.value)}
                  className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all flex flex-col items-center gap-0.5 ${
                    resolution === tier.value
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                  }`}
                >
                  <span className="font-bold">{tierLabel}</span>
                  <span className="text-[10px] opacity-70">{tierPixelRes}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {maxSelectableImageCount > minImageCount ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Layers size={12} className="text-blue-400" />
              <span className="text-xs text-slate-300">生成数量</span>
            </div>
            <span className="text-xs text-blue-400 font-mono font-bold">{numberOfImages}</span>
          </div>
          <input
            type="range"
            aria-label="生成数量"
            min={minImageCount}
            max={maxSelectableImageCount}
            step={1}
            value={numberOfImages}
            onChange={(event) => setNumberOfImages(parseInt(event.target.value, 10))}
            className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-blue-500"
          />
          <div className="flex justify-between text-[10px] text-slate-500 px-0.5">
            <span>{minImageCount}</span>
            <span>{maxSelectableImageCount}</span>
          </div>
        </div>
      ) : null}

      {canToggleEnhancePrompt ? (
        <PromptEnhanceControl
          enabled={enhancePrompt}
          onEnabledChange={setEnhancePrompt}
          modelId={enhancePromptModel}
          onModelIdChange={setEnhancePromptModel}
          modelOptions={enhancePromptModels}
          allowAutoModel={false}
          autoSelectFirstModel
          thinkingLevel={enhancePromptThinkingLevel}
          onThinkingLevelChange={setEnhancePromptThinkingLevel}
        />
      ) : null}

      {paramOptions.quality?.length ? (
        <OptionGrid
          icon={<Gauge size={12} className="text-amber-400" />}
          label="图片质量"
          value={quality}
          options={paramOptions.quality}
          onChange={(value) => setQuality(String(value))}
        />
      ) : null}

      {paramOptions.background?.length ? (
        <OptionGrid
          icon={<SlidersHorizontal size={12} className="text-cyan-400" />}
          label="背景"
          value={background}
          options={paramOptions.background}
          onChange={(value) => setBackground(String(value))}
        />
      ) : null}

      {paramOptions.moderation?.length ? (
        <OptionGrid
          icon={<ShieldCheck size={12} className="text-violet-400" />}
          label="审核"
          value={moderation}
          options={paramOptions.moderation}
          onChange={(value) => setModeration(String(value))}
        />
      ) : null}

      {paramOptions.output_format?.length ? (
        <OptionGrid
          icon={<FileImage size={12} className="text-fuchsia-400" />}
          label="输出格式"
          value={outputFormat}
          options={paramOptions.output_format}
          onChange={(value) => setOutputFormat(String(value))}
        />
      ) : null}

      {compressionRange ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={12} className="text-slate-400" />
              <span className="text-xs text-slate-300">压缩质量</span>
            </div>
            <span className="text-[10px] text-slate-500">{outputCompressionQuality}%</span>
          </div>
          <input
            type="range"
            aria-label="压缩质量"
            min={compressionRange.min ?? 0}
            max={compressionRange.max ?? 100}
            step={compressionRange.step ?? 1}
            value={outputCompressionQuality}
            onChange={(event) => setOutputCompressionQuality(Number(event.target.value))}
            className="w-full accent-emerald-500"
          />
        </div>
      ) : null}
    </div>
  );
};

const syncStringOption = (
  options: Option[] | undefined,
  value: string,
  setValue: (value: string) => void
) => {
  if (!options?.length) return;
  const allowed = options.map((option) => String(option.value));
  if (!allowed.includes(value)) {
    setValue(allowed[0]);
  }
};

const OptionGrid: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: OptionValue;
  options: Option[];
  onChange: (value: OptionValue) => void;
}> = ({ icon, label, value, options, onChange }) => {
  if (!options.length) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-xs text-slate-300">{label}</span>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {options.map((option) => {
          const selected = String(value) === String(option.value);
          return (
            <button
              key={String(option.value)}
              onClick={() => onChange(option.value)}
              className={`min-h-7 px-2 py-1.5 text-[10px] font-medium rounded-lg transition-all ${
                selected
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default OpenAIImageControls;
