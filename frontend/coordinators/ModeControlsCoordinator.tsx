/**
 * 模式控制协调者（仅 Panel 模式）
 *
 * 根据当前 mode 和 providerId 分发渲染对应的控制组件
 * 用于 View 组件右侧的参数面板
 *
 * 架构说明：
 * - 控件注册表维护"通用实现 + provider 差异覆盖"
 * - 协调者按 providerId + mode 分发渲染
 *
 * 使用方式：
 * <ModeControlsCoordinator
 *   mode={mode}
 *   providerId={providerId}
 *   controls={controls}
 *   currentModel={activeModelConfig}
 *   maxImageCount={4}
 * />
 */
import React from 'react';
import { AppMode, ModelConfig } from '../types/types';
import {
  ControlsState,
  ChatControlsProps,
  ImageGenControlsProps,
  ImageEditControlsProps,
  ImageMaskEditControlsProps,
  ImageOutpaintControlsProps,
  VideoGenControlsProps,
  AudioGenControlsProps,
  VirtualTryOnControlsProps,
  PdfExtractControlsProps,
  MultiAgentControlsProps,
} from '../controls/types';
import { getProviderControls } from '../controls/modes/registry';
import {
  useModeControlsSchema,
  ModeControlsSchema,
} from '../hooks/useModeControlsSchema';

/**
 * 需要从后端 `/api/.../controls` 接口动态获取 schema 的模式集合。
 * 这些模式下，Coordinator 内部调用 `useModeControlsSchema`，调用方仅传 mode/providerId/currentModel。
 * 调用方仍可显式传 controlsSchema / controlsSchemaLoading / controlsSchemaError 进行覆盖（用于测试或视图级共用 schema）。
 */
const SCHEMA_DRIVEN_MODES = new Set<AppMode>(['video-gen']);

/**
 * Helper type: intersects T with the three schema override fields so they can be
 * spread onto schema-driven controls without unsafe casts.
 */
type WithControlsSchema<T> = T & {
  controlsSchema?: ModeControlsSchema | null;
  controlsSchemaLoading?: boolean;
  controlsSchemaError?: string | null;
};

type ModeControlsCoordinatorProps = {
  mode: AppMode;
  providerId: string;
  currentModel?: ModelConfig;
  availableModels?: ModelConfig[];
  onModelSelect?: (id: string) => void;
  /** 传递 controls 状态对象 */
  controls?: ControlsState;
  /** 最大图片数量（image-gen 模式） */
  maxImageCount?: number;
  /**
   * Schema override props for schema-driven modes (e.g. video-gen).
   * When provided, these take precedence over the internally fetched schema.
   */
  controlsSchema?: ModeControlsSchema | null;
  controlsSchemaLoading?: boolean;
  controlsSchemaError?: string | null;
} & Partial<ChatControlsProps> &
  Partial<ImageGenControlsProps> &
  Partial<ImageEditControlsProps> &
  Partial<ImageMaskEditControlsProps> &
  Partial<ImageOutpaintControlsProps> &
  Partial<VideoGenControlsProps> &
  Partial<AudioGenControlsProps> &
  Partial<VirtualTryOnControlsProps> &
  Partial<PdfExtractControlsProps> &
  Partial<MultiAgentControlsProps>;

export const ModeControlsCoordinator: React.FC<ModeControlsCoordinatorProps> = (props) => {
  const {
    mode,
    providerId,
    currentModel,
    availableModels,
    onModelSelect,
    controls,
    maxImageCount,
    controlsSchema: controlsSchemaOverride,
    controlsSchemaLoading: controlsSchemaLoadingOverride,
    controlsSchemaError: controlsSchemaErrorOverride,
    ...controlProps
  } = props;

  // 对 schema-driven 模式（如 video-gen）：Coordinator 内部按 providerId+mode+modelId 拉取
  // schema（命中 schemaCache 单例，与视图层的 useModeControlsSchema 共享缓存，不重复请求）。
  // 调用方可显式传 controlsSchema / controlsSchemaLoading / controlsSchemaError 覆盖。
  const isSchemaDriven = SCHEMA_DRIVEN_MODES.has(mode);
  const {
    schema: internalSchema,
    loading: internalSchemaLoading,
    error: internalSchemaError,
  } = useModeControlsSchema(providerId, mode, currentModel?.id, {
    enabled: isSchemaDriven && !!currentModel?.id,
  });

  const schemaProps =
    isSchemaDriven
      ? {
          controlsSchema:
            controlsSchemaOverride !== undefined ? controlsSchemaOverride : internalSchema,
          controlsSchemaLoading:
            controlsSchemaLoadingOverride !== undefined
              ? controlsSchemaLoadingOverride
              : internalSchemaLoading,
          controlsSchemaError:
            controlsSchemaErrorOverride !== undefined
              ? controlsSchemaErrorOverride
              : internalSchemaError,
        }
      : {};

  // 获取当前提供商的控件集
  const Controls = getProviderControls(providerId);

  switch (mode) {
    case 'chat':
      return (
        <Controls.ChatControls
          currentModel={currentModel}
          {...(controlProps as ChatControlsProps)}
        />
      );

    case 'image-gen':
      return (
        <Controls.ImageGenControls
          currentModel={currentModel}
          controls={controls}
          availableModels={availableModels}
          maxImageCount={maxImageCount}
          {...(controlProps as ImageGenControlsProps)}
          providerId={providerId}
        />
      );

    // 图片编辑模式
    case 'image-chat-edit':
    case 'image-inpainting':
    case 'image-background-edit':
    case 'image-recontext':
    // product-recontext shares ImageEditControls; the component detects the mode
    // variant internally (e.g. showRecontextCountHint) via the `mode` prop.
    case 'product-recontext':
      return (
        <Controls.ImageEditControls
          mode={mode}
          currentModel={currentModel}
          controls={controls}
          availableModels={availableModels}
          maxImageCount={maxImageCount}
          {...(controlProps as ImageEditControlsProps)}
          providerId={providerId}
        />
      );

    // 掩码编辑模式（使用专门的 ImageMaskEditControls）
    case 'image-mask-edit':
      return (
        <Controls.ImageMaskEditControls
          mode={mode}
          currentModel={currentModel}
          controls={controls}
          availableModels={availableModels}
          maxImageCount={maxImageCount}
          {...(controlProps as ImageMaskEditControlsProps)}
          providerId={providerId}
        />
      );

    case 'image-outpainting':
      return (
        <Controls.ImageOutpaintControls
          mode={mode}
          currentModel={currentModel}
          controls={controls}
          availableModels={availableModels}
          maxImageCount={maxImageCount}
          {...(controlProps as ImageOutpaintControlsProps)}
          providerId={providerId}
        />
      );

    case 'video-gen':
      return (
        <Controls.VideoGenControls
          currentModel={currentModel}
          availableModels={availableModels}
          onModelSelect={onModelSelect}
          controls={controls}
          {...(controlProps as VideoGenControlsProps)}
          {...schemaProps}
          providerId={providerId}
        />
      );

    case 'audio-gen':
      return (
        <Controls.AudioGenControls
          controls={controls}
          {...(controlProps as AudioGenControlsProps)}
          providerId={providerId}
        />
      );

    case 'pdf-extract':
      return <Controls.PdfExtractControls {...(controlProps as PdfExtractControlsProps)} />;

    case 'virtual-try-on':
      return (
        <Controls.VirtualTryOnControls
          mode={mode}
          currentModel={currentModel}
          controls={controls}
          availableModels={availableModels}
          maxImageCount={maxImageCount}
          {...(controlProps as VirtualTryOnControlsProps)}
          providerId={providerId}
        />
      );

    case 'multi-agent':
      return (
        <Controls.MultiAgentControls
          currentModel={currentModel}
          {...(controlProps as MultiAgentControlsProps)}
        />
      );

    // These modes operate through their own dedicated view surfaces and have no
    // right-panel parameter controls at this time.
    case 'image-upscale':
    case 'image-segmentation':
      return null;

    default: {
      // Compile-time exhaustiveness check: if a new AppMode value is added and
      // not handled above, TypeScript will flag `mode` as not assignable to `never`.
      const _exhaustive: never = mode;
      void _exhaustive;
      return null;
    }
  }
};

export default ModeControlsCoordinator;
