/**
 * Google 视频生成模式参数控件（仅 Panel 模式）
 *
 * 用于右侧参数面板，通过 ModeControlsCoordinator 分发
 */
import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import { ChevronDown, ChevronUp, Clapperboard, Dices, Film, Maximize2 } from 'lucide-react';
import { VideoGenControlsProps } from '../../types';
import PromptEnhanceControl from '../../shared/PromptEnhanceControl';
import VideoExtensionControl from '../../shared/VideoExtensionControl';
import VideoInputStrategyControl from '../../shared/VideoInputStrategyControl';
import { useModeControlsSchema } from '../../../hooks/useModeControlsSchema';
import { useEnhancePromptModels } from '../../../hooks/useEnhancePromptModels';
import {
  buildVideoControlContract,
  getVideoExtensionOptions,
} from '../../../utils/videoControlSchema';
import { getUnsupportedParams } from '../../shared/modeControlSchemaUtils';
import {
  buildVideoInputStrategyOptions,
  isVideoExtensionStrategyId,
} from '../../../utils/videoSubmodeOptions';

type VideoGenControlsBodyProps = VideoGenControlsProps & {
  schemaLoading: boolean;
  schemaError: string | null;
};

const LOCAL_PROMPT_ENHANCE_VIDEO_PROVIDERS = new Set(['openai']);

const VideoGenControlsBody: React.FC<VideoGenControlsBodyProps> = ({
  providerId = 'google',
  controls,
  controlsSchema,
  schemaLoading,
  schemaError,
  currentModel,
  availableModels,
  onModelSelect,
  aspectRatio: propAspectRatio,
  setAspectRatio: propSetAspectRatio,
  resolution: propResolution,
  setResolution: propSetResolution,
  videoSeconds: propVideoSeconds,
  setVideoSeconds: propSetVideoSeconds,
  videoInputStrategy: propVideoInputStrategy,
  setVideoInputStrategy: propSetVideoInputStrategy,
  videoExtensionCount: propVideoExtensionCount,
  setVideoExtensionCount: propSetVideoExtensionCount,
  storyboardShotSeconds: propStoryboardShotSeconds,
  setStoryboardShotSeconds: propSetStoryboardShotSeconds,
  generateAudio: propGenerateAudio,
  setGenerateAudio: propSetGenerateAudio,
  subtitleMode: propSubtitleMode,
  setSubtitleMode: propSetSubtitleMode,
  subtitleLanguage: propSubtitleLanguage,
  setSubtitleLanguage: propSetSubtitleLanguage,
  subtitleScript: propSubtitleScript,
  setSubtitleScript: propSetSubtitleScript,
  storyboardPrompt: propStoryboardPrompt,
  setStoryboardPrompt: propSetStoryboardPrompt,
  storyboardSegments: propStoryboardSegments,
  setStoryboardSegments: propSetStoryboardSegments,
  showAdvanced: propShowAdvanced,
  setShowAdvanced: propSetShowAdvanced,
  negativePrompt: propNegativePrompt,
  setNegativePrompt: propSetNegativePrompt,
  seed: propSeed,
  setSeed: propSetSeed,
  enhancePrompt: propEnhancePrompt,
  setEnhancePrompt: propSetEnhancePrompt,
  enhancePromptModel: propEnhancePromptModel,
  setEnhancePromptModel: propSetEnhancePromptModel,
}) => {
  const schema = controlsSchema;
  const videoControlContract = useMemo(() => buildVideoControlContract(schema), [schema]);
  const unsupportedParams = useMemo(() => getUnsupportedParams(schema), [schema]);
  const showAspectRatioControl = !unsupportedParams.has('aspect_ratio');
  const showNegativePromptControl = !unsupportedParams.has('negative_prompt');
  const showPromptEnhanceControl =
    LOCAL_PROMPT_ENHANCE_VIDEO_PROVIDERS.has(String(providerId).toLowerCase()) ||
    (!unsupportedParams.has('prompt_extend') && !unsupportedParams.has('enhance_prompt'));
  const showSeedControl = !unsupportedParams.has('seed');
  const availableRatios = useMemo(() => schema?.aspectRatios ?? [], [schema]);
  const availableResolutionTiers = useMemo(() => schema?.resolutionTiers ?? [], [schema]);
  const availableSeconds = useMemo(() => schema?.paramOptions?.seconds ?? [], [schema]);
  const schemaInputStrategies = useMemo(
    () => schema?.videoContract?.inputStrategies ?? [],
    [schema]
  );
  const rawInputStrategies = useMemo(
    () =>
      buildVideoInputStrategyOptions({
        providerId,
        currentModel,
        availableModels,
        schemaStrategies: schemaInputStrategies,
      }),
    [availableModels, currentModel, providerId, schemaInputStrategies]
  );
  const availableInputStrategies = useMemo(
    () => rawInputStrategies.filter((strategy) => !isVideoExtensionStrategyId(strategy.id)),
    [rawInputStrategies]
  );
  const availableStoryboardShotSeconds = useMemo(
    () => schema?.paramOptions?.storyboard_shot_seconds ?? [],
    [schema]
  );
  const availableGenerateAudioOptions = useMemo(
    () => schema?.paramOptions?.generate_audio ?? [],
    [schema]
  );
  const availableSubtitleModes = useMemo(() => schema?.paramOptions?.subtitle_mode ?? [], [schema]);
  const availableSubtitleLanguages = useMemo(
    () => schema?.paramOptions?.subtitle_language ?? [],
    [schema]
  );
  const defaults = schema?.defaults ?? {};
  const seedRange = schema?.numericRanges?.seed;
  const enhancePromptMandatory = videoControlContract.fieldPolicies.enhancePromptMandatory;
  const storyboardPromptPreferred = videoControlContract.fieldPolicies.storyboardPromptPreferred;
  const defaultSubtitleEnabledMode =
    videoControlContract.fieldPolicies.subtitleModeDefaultEnabled ?? 'vtt';
  const extensionConstraints = videoControlContract.extensionConstraints;
  const extensionAddedSeconds = extensionConstraints.addedSeconds ?? 0;
  const maxOutputVideoSeconds =
    extensionConstraints.maxOutputVideoSeconds ?? extensionConstraints.maxSourceVideoSeconds ?? 0;

  const defaultAspectRatio =
    (typeof defaults.aspect_ratio === 'string' ? defaults.aspect_ratio : undefined) ??
    videoControlContract.defaultAspectRatio;
  const defaultResolution =
    (typeof defaults.resolution === 'string' ? defaults.resolution : undefined) ??
    videoControlContract.defaultResolution;

  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? defaultAspectRatio;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? (() => {});
  const resolution = controls?.resolution ?? propResolution ?? defaultResolution;
  const setResolution = controls?.setResolution ?? propSetResolution ?? (() => {});
  const currentResolutionLabel = useMemo(
    () => availableResolutionTiers.find((tier) => tier.value === resolution)?.baseResolution ?? '',
    [availableResolutionTiers, resolution]
  );
  const defaultVideoSeconds =
    (typeof defaults.seconds === 'string' ? defaults.seconds : undefined) ??
    (typeof defaults.seconds === 'number' ? String(defaults.seconds) : undefined) ??
    videoControlContract.defaultVideoSeconds;
  const schemaDefaultVideoInputStrategy =
    (typeof defaults.video_input_strategy === 'string'
      ? defaults.video_input_strategy
      : undefined) ??
    (typeof defaults.videoInputStrategy === 'string' ? defaults.videoInputStrategy : undefined);
  const defaultVideoInputStrategy =
    schemaDefaultVideoInputStrategy && !isVideoExtensionStrategyId(schemaDefaultVideoInputStrategy)
      ? schemaDefaultVideoInputStrategy
      : (availableInputStrategies[0]?.id ?? '');
  const defaultNegativePrompt = videoControlContract.defaultNegativePrompt;
  const defaultSeed = videoControlContract.defaultSeed;
  const defaultEnhancePrompt = videoControlContract.defaultEnhancePrompt;
  const defaultVideoExtensionCount =
    typeof defaults.video_extension_count === 'number'
      ? defaults.video_extension_count
      : videoControlContract.defaultVideoExtensionCount;
  const defaultStoryboardShotSeconds = videoControlContract.defaultStoryboardShotSeconds;
  const defaultGenerateAudio = videoControlContract.defaultGenerateAudio;
  const defaultSubtitleMode = videoControlContract.defaultSubtitleMode;
  const defaultSubtitleLanguage = videoControlContract.defaultSubtitleLanguage;
  const defaultSubtitleScript = videoControlContract.defaultSubtitleScript;
  const defaultStoryboardPrompt = videoControlContract.defaultStoryboardPrompt;
  const videoSeconds = controls?.videoSeconds ?? propVideoSeconds ?? defaultVideoSeconds;
  const setVideoSeconds = controls?.setVideoSeconds ?? propSetVideoSeconds ?? (() => {});
  const videoInputStrategy =
    controls?.videoInputStrategy ?? propVideoInputStrategy ?? defaultVideoInputStrategy;
  const setVideoInputStrategy =
    controls?.setVideoInputStrategy ?? propSetVideoInputStrategy ?? (() => {});
  const videoExtensionCount =
    controls?.videoExtensionCount ?? propVideoExtensionCount ?? defaultVideoExtensionCount;
  const setVideoExtensionCount =
    controls?.setVideoExtensionCount ?? propSetVideoExtensionCount ?? (() => {});
  const storyboardShotSeconds =
    controls?.storyboardShotSeconds ?? propStoryboardShotSeconds ?? defaultStoryboardShotSeconds;
  const setStoryboardShotSeconds =
    controls?.setStoryboardShotSeconds ?? propSetStoryboardShotSeconds ?? (() => {});
  const generateAudio = controls?.generateAudio ?? propGenerateAudio ?? defaultGenerateAudio;
  const setGenerateAudio = controls?.setGenerateAudio ?? propSetGenerateAudio ?? (() => {});
  const subtitleMode = controls?.subtitleMode ?? propSubtitleMode ?? defaultSubtitleMode;
  const setSubtitleMode = controls?.setSubtitleMode ?? propSetSubtitleMode ?? (() => {});
  const subtitleLanguage =
    controls?.subtitleLanguage ?? propSubtitleLanguage ?? defaultSubtitleLanguage;
  const setSubtitleLanguage =
    controls?.setSubtitleLanguage ?? propSetSubtitleLanguage ?? (() => {});
  const subtitleScript = controls?.subtitleScript ?? propSubtitleScript ?? defaultSubtitleScript;
  const setSubtitleScript = controls?.setSubtitleScript ?? propSetSubtitleScript ?? (() => {});
  const storyboardPrompt =
    controls?.storyboardPrompt ?? propStoryboardPrompt ?? defaultStoryboardPrompt;
  const setStoryboardPrompt =
    controls?.setStoryboardPrompt ?? propSetStoryboardPrompt ?? (() => {});
  const storyboardSegments = controls?.storyboardSegments ?? propStoryboardSegments ?? [];
  const setStoryboardSegments =
    controls?.setStoryboardSegments ?? propSetStoryboardSegments ?? (() => {});
  const subtitlesEnabled = subtitleMode !== 'none';
  const showAdvanced = controls?.showAdvanced ?? propShowAdvanced ?? false;
  const setShowAdvanced = controls?.setShowAdvanced ?? propSetShowAdvanced ?? (() => {});
  const negativePrompt = controls?.negativePrompt ?? propNegativePrompt ?? defaultNegativePrompt;
  const setNegativePrompt = controls?.setNegativePrompt ?? propSetNegativePrompt ?? (() => {});
  const seed = controls?.seed ?? propSeed ?? defaultSeed;
  const setSeed = controls?.setSeed ?? propSetSeed ?? (() => {});
  const enhancePrompt = controls?.enhancePrompt ?? propEnhancePrompt ?? defaultEnhancePrompt;
  const setEnhancePrompt = controls?.setEnhancePrompt ?? propSetEnhancePrompt ?? (() => {});
  const enhancePromptModels = useEnhancePromptModels(providerId);
  const enhancePromptModel = controls?.enhancePromptModel ?? propEnhancePromptModel ?? '';
  const setEnhancePromptModel =
    controls?.setEnhancePromptModel ?? propSetEnhancePromptModel ?? (() => {});
  const appliedSchemaDefaultsRef = useRef<string | null>(null);
  const handleVideoInputStrategyChange = useCallback(
    (nextStrategyId: string) => {
      setVideoInputStrategy(nextStrategyId);
      const nextStrategy = availableInputStrategies.find(
        (strategy) => strategy.id === nextStrategyId
      );
      const targetModelId = nextStrategy?.targetModelId;
      if (targetModelId && targetModelId !== currentModel?.id) {
        onModelSelect?.(targetModelId);
      }
    },
    [availableInputStrategies, currentModel?.id, onModelSelect, setVideoInputStrategy]
  );
  const showExtensionControls = videoControlContract.validVideoExtensionCounts.some(
    (count) => count > 0
  );
  const schemaHasRequiredControls =
    Boolean(schema) &&
    (!showAspectRatioControl || availableRatios.length > 0) &&
    availableResolutionTiers.length > 0;

  useEffect(() => {
    if (!schema) {
      return;
    }
    const schemaDefaultsKey = [
      schema.provider,
      schema.mode,
      schema.modelId ?? '',
      showAspectRatioControl ? defaultAspectRatio : '',
      defaultResolution,
      defaultVideoSeconds,
    ].join('|');
    if (appliedSchemaDefaultsRef.current === schemaDefaultsKey) {
      return;
    }
    appliedSchemaDefaultsRef.current = schemaDefaultsKey;

    if (showAspectRatioControl && defaultAspectRatio && aspectRatio !== defaultAspectRatio) {
      setAspectRatio(defaultAspectRatio);
    }
    if (defaultResolution && resolution !== defaultResolution) {
      setResolution(defaultResolution);
    }
    if (defaultVideoSeconds && videoSeconds !== defaultVideoSeconds) {
      setVideoSeconds(defaultVideoSeconds);
    }
  }, [
    aspectRatio,
    defaultAspectRatio,
    defaultResolution,
    defaultVideoSeconds,
    resolution,
    schema,
    setAspectRatio,
    setResolution,
    setVideoSeconds,
    showAspectRatioControl,
    videoSeconds,
  ]);

  useEffect(() => {
    if (showPromptEnhanceControl && enhancePromptMandatory && !enhancePrompt) {
      setEnhancePrompt(true);
    }
  }, [enhancePrompt, enhancePromptMandatory, setEnhancePrompt, showPromptEnhanceControl]);

  useEffect(() => {
    if (!enhancePromptModel || enhancePromptModels.length === 0) {
      return;
    }
    const stillAvailable = enhancePromptModels.some((model) => model.id === enhancePromptModel);
    if (!stillAvailable) {
      setEnhancePromptModel('');
    }
  }, [enhancePromptModel, enhancePromptModels, setEnhancePromptModel]);

  useEffect(() => {
    if (!showAspectRatioControl) {
      return;
    }
    const validRatios = availableRatios.map((r) => r.value);
    if (validRatios.length > 0 && !validRatios.includes(aspectRatio)) {
      setAspectRatio(validRatios[0]);
    }
  }, [aspectRatio, availableRatios, setAspectRatio, showAspectRatioControl]);

  useEffect(() => {
    const validTiers = availableResolutionTiers.map((r) => r.value);
    if (validTiers.length > 0 && !validTiers.includes(resolution)) {
      setResolution(validTiers[0]);
    }
  }, [resolution, availableResolutionTiers, setResolution]);

  useEffect(() => {
    const validSeconds = availableSeconds.map((option) => String(option.value));
    if (validSeconds.length > 0 && !validSeconds.includes(videoSeconds)) {
      setVideoSeconds(validSeconds[0]);
    }
  }, [availableSeconds, setVideoSeconds, videoSeconds]);

  useEffect(() => {
    const validStrategies = availableInputStrategies.map((strategy) => strategy.id);
    if (validStrategies.length > 0 && !validStrategies.includes(videoInputStrategy)) {
      setVideoInputStrategy(defaultVideoInputStrategy || validStrategies[0]);
    }
  }, [
    availableInputStrategies,
    defaultVideoInputStrategy,
    setVideoInputStrategy,
    videoInputStrategy,
  ]);

  useEffect(() => {
    if (!showExtensionControls && videoExtensionCount !== 0) {
      setVideoExtensionCount(0);
    }
  }, [setVideoExtensionCount, showExtensionControls, videoExtensionCount]);

  useEffect(() => {
    const validShotSeconds = availableStoryboardShotSeconds
      .map((option) => Number(option.value))
      .filter((value) => Number.isFinite(value));
    if (validShotSeconds.length > 0 && !validShotSeconds.includes(storyboardShotSeconds)) {
      setStoryboardShotSeconds(validShotSeconds[0]);
    }
  }, [availableStoryboardShotSeconds, setStoryboardShotSeconds, storyboardShotSeconds]);

  const extensionBaseSeconds = useMemo(() => {
    const currentOptions = getVideoExtensionOptions(videoControlContract, videoSeconds);
    if (currentOptions.some((option) => option.count > 0)) {
      return videoSeconds;
    }
    return (
      Object.entries(videoControlContract.extensionOptionsBySeconds).find(([, options]) =>
        options.some((option) => option.count > 0)
      )?.[0] ?? videoSeconds
    );
  }, [videoControlContract, videoSeconds]);

  const derivedExtensionOptions = useMemo(() => {
    return getVideoExtensionOptions(videoControlContract, extensionBaseSeconds).map((option) => ({
      ...option,
      label:
        option.count === 0
          ? `${option.totalSeconds}s（原始）`
          : `${option.totalSeconds}s（+${option.count} 次延长）`,
    }));
  }, [extensionBaseSeconds, videoControlContract]);
  const firstPositiveExtensionCount = useMemo(
    () => derivedExtensionOptions.find((option) => option.count > 0)?.count ?? 1,
    [derivedExtensionOptions]
  );
  const handleVideoExtensionEnabledChange = useCallback(
    (enabled: boolean) => {
      if (enabled && extensionBaseSeconds !== videoSeconds) {
        setVideoSeconds(extensionBaseSeconds);
      }
      setVideoExtensionCount(
        enabled ? (videoExtensionCount > 0 ? videoExtensionCount : firstPositiveExtensionCount) : 0
      );
    },
    [
      extensionBaseSeconds,
      firstPositiveExtensionCount,
      setVideoExtensionCount,
      setVideoSeconds,
      videoExtensionCount,
      videoSeconds,
    ]
  );

  useEffect(() => {
    const validCounts = derivedExtensionOptions.map((option) => option.count);
    if (validCounts.length > 0 && !validCounts.includes(videoExtensionCount)) {
      setVideoExtensionCount(validCounts[0]);
    }
  }, [derivedExtensionOptions, setVideoExtensionCount, videoExtensionCount]);

  useEffect(() => {
    if (
      showExtensionControls &&
      derivedExtensionOptions.length === 0 &&
      videoExtensionCount !== 0
    ) {
      setVideoExtensionCount(0);
    }
  }, [
    derivedExtensionOptions.length,
    setVideoExtensionCount,
    showExtensionControls,
    videoExtensionCount,
  ]);

  const baseDurationSeconds = useMemo(() => {
    const parsed = parseInt(String(extensionBaseSeconds || ''), 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 8;
  }, [extensionBaseSeconds]);

  return (
    <div className="space-y-4">
      {!schemaLoading && (schemaError || (schema && !schemaHasRequiredControls)) && (
        <div className="text-[10px] text-rose-400">
          视频参数配置加载失败，请检查后端 `mode_controls_catalog.json`。
        </div>
      )}
      <VideoInputStrategyControl
        strategies={availableInputStrategies}
        value={videoInputStrategy}
        onChange={handleVideoInputStrategyChange}
      />
      {/* 视频比例 */}
      {showAspectRatioControl && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Film size={12} className="text-indigo-400" />
            <span className="text-xs text-slate-300">视频比例</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {availableRatios.map((ratio) => (
              <button
                key={ratio.value}
                onClick={() => setAspectRatio(ratio.value)}
                className={`py-2 text-xs font-medium rounded-lg transition-all ${
                  aspectRatio === ratio.value
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                }`}
              >
                {ratio.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 分辨率 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Maximize2 size={12} className="text-emerald-400" />
            <span className="text-xs text-slate-300">分辨率</span>
          </div>
          {currentResolutionLabel && (
            <span className="text-[10px] text-emerald-400 font-mono">{currentResolutionLabel}</span>
          )}
        </div>
        <div className="flex gap-2">
          {availableResolutionTiers.map((res) => (
            <button
              key={res.value}
              onClick={() => setResolution(res.value)}
              className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
                resolution === res.value
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              <span className="block">{res.label}</span>
              {res.baseResolution && (
                <span className="mt-0.5 block text-[10px] opacity-70">{res.baseResolution}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {availableSeconds.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Clapperboard size={12} className="text-amber-400" />
            <span className="text-xs text-slate-300">时长</span>
          </div>
          <div className="flex gap-2">
            {availableSeconds.map((option) => {
              const value = String(option.value);
              return (
                <button
                  key={value}
                  onClick={() => setVideoSeconds(value)}
                  className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
                    videoSeconds === value
                      ? 'bg-amber-600 text-white'
                      : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                  }`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {showExtensionControls && (
        <VideoExtensionControl
          extensionOptions={derivedExtensionOptions}
          extensionCount={videoExtensionCount}
          onExtensionCountChange={setVideoExtensionCount}
          enabled={videoExtensionCount > 0}
          onEnabledChange={handleVideoExtensionEnabledChange}
          addedSeconds={extensionAddedSeconds || baseDurationSeconds}
          maxOutputVideoSeconds={maxOutputVideoSeconds}
          baseDurationSeconds={baseDurationSeconds}
          storyboardSegments={storyboardSegments}
          onStoryboardSegmentsChange={setStoryboardSegments}
          showStoryboard={storyboardPromptPreferred}
        />
      )}

      {showPromptEnhanceControl && (
        <PromptEnhanceControl
          enabled={enhancePrompt}
          onEnabledChange={setEnhancePrompt}
          modelId={enhancePromptModel}
          onModelIdChange={setEnhancePromptModel}
          modelOptions={enhancePromptModels}
          allowAutoModel
          disabled={enhancePromptMandatory}
          disabledHint={
            enhancePromptMandatory ? '当前 Veo 3.1 模型必须启用 AI 增强提示词。' : undefined
          }
          thinkingLevel={controls?.enhancePromptThinkingLevel ?? 'auto'}
          onThinkingLevelChange={controls?.setEnhancePromptThinkingLevel}
        />
      )}

      <div className="border-t border-slate-700/50 pt-4">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full flex items-center justify-between text-xs text-slate-400 hover:text-slate-200 transition-colors"
        >
          <span>高级参数</span>
          {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        {showAdvanced && (
          <div className="mt-4 space-y-4">
            {showSeedControl && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-300">Seed</span>
                  <button
                    onClick={() => setSeed(Math.floor(Math.random() * 2147483647))}
                    className="text-xs text-indigo-400 hover:text-indigo-300"
                    title="随机种子"
                  >
                    <Dices size={14} />
                  </button>
                </div>
                <input
                  type="number"
                  value={seed === -1 ? '' : seed}
                  onChange={(event) =>
                    setSeed(event.target.value ? parseInt(event.target.value, 10) : -1)
                  }
                  placeholder="随机 (-1)"
                  min={seedRange?.min}
                  max={seedRange?.max}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
            )}

            {showNegativePromptControl && (
              <div className="space-y-2">
                <span className="text-xs text-slate-300">负向提示词</span>
                <textarea
                  value={negativePrompt}
                  onChange={(event) => setNegativePrompt(event.target.value)}
                  placeholder="不想在视频中出现的内容..."
                  className="w-full h-16 bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-300 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500"
                />
              </div>
            )}

            {availableGenerateAudioOptions.length > 0 && (
              <label className="space-y-1">
                <span className="text-xs text-slate-300">音频</span>
                <select
                  aria-label="生成音频"
                  value={String(generateAudio)}
                  onChange={(event) => setGenerateAudio(event.target.value === 'true')}
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none"
                >
                  {availableGenerateAudioOptions.map((option) => (
                    <option key={String(option.value)} value={String(option.value)}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {availableStoryboardShotSeconds.length > 0 && (
              <label className="space-y-1">
                <span className="text-xs text-slate-300">分镜镜头时长</span>
                <select
                  aria-label="分镜镜头时长"
                  value={String(storyboardShotSeconds)}
                  onChange={(event) =>
                    setStoryboardShotSeconds(
                      parseInt(event.target.value, 10) || defaultStoryboardShotSeconds
                    )
                  }
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none"
                >
                  {availableStoryboardShotSeconds.map((option) => (
                    <option key={String(option.value)} value={String(option.value)}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {availableSubtitleModes.length > 0 && (
              <div className="flex items-center justify-between py-1">
                <div className="flex items-center gap-2">
                  <Clapperboard size={12} className="text-fuchsia-400" />
                  <span className="text-xs text-slate-300">字幕</span>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setSubtitleMode(subtitlesEnabled ? 'none' : defaultSubtitleEnabledMode)
                  }
                  className={`w-10 h-6 flex items-center rounded-full p-1 transition-colors duration-200 ${
                    subtitlesEnabled ? 'bg-fuchsia-600' : 'bg-slate-600'
                  }`}
                  role="switch"
                  aria-checked={subtitlesEnabled}
                  aria-label="字幕"
                >
                  <div
                    className={`w-4 h-4 bg-white rounded-full shadow-md transform transition-transform duration-200 ${
                      subtitlesEnabled ? 'translate-x-4' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
            )}

            {subtitlesEnabled && availableSubtitleLanguages.length > 0 && (
              <>
                <label className="space-y-1">
                  <span className="text-xs text-slate-300">字幕语言</span>
                  <select
                    aria-label="字幕语言"
                    value={subtitleLanguage}
                    onChange={(event) => setSubtitleLanguage(event.target.value)}
                    className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none"
                  >
                    {availableSubtitleLanguages.map((option) => (
                      <option key={String(option.value)} value={String(option.value)}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                {!generateAudio && (
                  <div className="space-y-2">
                    <span className="text-xs text-slate-300">字幕脚本</span>
                    <textarea
                      aria-label="字幕脚本"
                      value={subtitleScript}
                      onChange={(event) => setSubtitleScript(event.target.value)}
                      placeholder="每行一句，或使用 | 分隔。不会再从提示词自动生成字幕。"
                      className="w-full h-24 bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-300 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const VideoGenControlsFromApi: React.FC<VideoGenControlsProps> = (props) => {
  const { providerId = 'google', currentModel } = props;
  const { schema, loading, error } = useModeControlsSchema(
    providerId,
    'video-gen',
    currentModel?.id
  );

  return (
    <VideoGenControlsBody
      {...props}
      controlsSchema={schema}
      schemaLoading={loading}
      schemaError={error}
    />
  );
};

export const VideoGenControls: React.FC<VideoGenControlsProps> = (props) => {
  if (
    'controlsSchema' in props ||
    'controlsSchemaLoading' in props ||
    'controlsSchemaError' in props
  ) {
    return (
      <VideoGenControlsBody
        {...props}
        schemaLoading={Boolean(props.controlsSchemaLoading)}
        schemaError={props.controlsSchemaError ?? null}
      />
    );
  }

  return <VideoGenControlsFromApi {...props} />;
};

export default VideoGenControls;
