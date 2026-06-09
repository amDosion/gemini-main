/**
 * Chat Edit 专用输入区域组件
 *
 * 功能：
 * - 用于图片编辑、扩图、修复、视频生成、音频生成等模式的输入区域
 * - 处理附件上传、预览、删除
 * - 处理提示词输入和发送逻辑
 * - 支持画布图片的连续性逻辑（activeImageUrl）
 * - 使用 AttachmentPreview 组件显示附件
 * - 根据模式显示不同的按钮文本和图标
 */
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { ChatOptions, Attachment, AppMode, Message, ModelConfig } from '../../types/types';
import {
  Wand2,
  Image as ImageIcon,
  Paperclip,
  Expand,
  Crop,
  Sparkles,
  Send,
  Mic,
} from 'lucide-react';
import { processUserAttachments } from '../../hooks/handlers/attachmentUtils';
import { useClipboardAttachments } from '../../hooks/useClipboardAttachments';
import { ModeControlsSchema, useModeControlsSchema } from '../../hooks/useModeControlsSchema';
import {
  getUnsupportedParams,
  supportsBooleanParam,
} from '../../controls/shared/modeControlSchemaUtils';
import { AttachmentPreview } from './input/AttachmentPreview';
import {
  applyDefaultVideoAttachmentRoles,
  getVideoAttachmentRoleOptions,
} from './input/videoAttachmentRoleOptions';
import { getPreferredAttachmentUrl } from '../../utils/attachmentUrl';
import { ControlsState } from '../../controls/types';
import { useToastContext } from '../../contexts/ToastContext';

interface ChatEditInputAreaProps {
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  isLoading: boolean;
  onStop?: () => void;
  mode: AppMode; // 支持多种模式：image-chat-edit, image-outpainting, image-inpainting, video-gen, audio-gen 等
  // 附件相关（必需，由父组件统一管理）
  activeAttachments: Attachment[];
  onAttachmentsChange: (attachments: Attachment[]) => void;
  activeImageUrl: string | null; // 画布中的图片 URL（用于连续性逻辑）
  onActiveImageUrlChange: (url: string | null) => void;
  // ✅ 新增：画布图片对应的完整附件对象（包含元数据）
  activeCanvasAttachment?: Attachment | null;
  // 消息和会话相关（用于 processUserAttachments）
  messages: Message[];
  sessionId: string | null;
  // 初始值
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  providerId?: string;
  currentModel?: ModelConfig;
  controlsSchema?: ModeControlsSchema | null;
  /** controls 状态（由父 View 通过 useControlsState 创建，与参数面板共享同一实例） */
  controls: ControlsState;
  // 可选：自定义按钮文本和图标（如果不提供，会根据 mode 自动选择）
  buttonText?: string;
  buttonIcon?: React.ReactNode;
  loadingText?: string;
  placeholder?: string;
  // ✅ 多附件支持
  maxAttachments?: number; // 最大附件数量，默认 10
  externalDisabled?: boolean;
  externalDisabledReason?: string | null;
}

// 根据模式获取按钮文本和图标
const getModeButtonConfig = (mode: AppMode, hasAttachmentsOrImage: boolean) => {
  const configs: Partial<
    Record<
      AppMode,
      {
        text: string;
        loadingText: string;
        icon: React.ReactNode;
        placeholder: string;
      }
    >
  > = {
    'image-chat-edit': {
      text: hasAttachmentsOrImage ? '开始编辑' : '请先上传图片',
      loadingText: '编辑中...',
      icon: <Wand2 size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述你要对图片做的编辑...' : '请先上传图片...',
    },
    'image-outpainting': {
      text: hasAttachmentsOrImage ? '开始扩图' : '请先上传图片',
      loadingText: '扩图中...',
      icon: <Expand size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述扩展内容...' : '请先上传图片...',
    },
    'image-inpainting': {
      text: hasAttachmentsOrImage ? '开始修复' : '请先上传图片',
      loadingText: '修复中...',
      icon: <Wand2 size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述需要修复的区域...' : '请先上传图片...',
    },
    'image-mask-edit': {
      text: hasAttachmentsOrImage ? '开始 Mask 编辑' : '请先上传图片',
      loadingText: '编辑中...',
      icon: <Crop size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述遮罩区域的编辑...' : '请先上传图片...',
    },
    'image-recontext': {
      text: hasAttachmentsOrImage ? '重新上下文' : '请先上传图片',
      loadingText: '处理中...',
      icon: <Sparkles size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述新的上下文环境...' : '请先上传图片...',
    },
    'image-background-edit': {
      text: hasAttachmentsOrImage ? '替换背景' : '请先上传图片',
      loadingText: '处理中...',
      icon: <Wand2 size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述新的背景...' : '请先上传图片...',
    },
    'video-gen': {
      text: '生成视频',
      loadingText: '生成中...',
      icon: <Send size={18} />,
      placeholder: '描述你想生成的视频；可上传一张或多张图片，或上传视频作为参考...',
    },
    'audio-gen': {
      text: '生成语音',
      loadingText: '生成中...',
      icon: <Mic size={18} />,
      placeholder: '输入要转换为语音的文本...',
    },
  };

  return (
    configs[mode] ||
    configs['image-chat-edit'] || {
      text: hasAttachmentsOrImage ? '开始操作' : '请先上传图片',
      loadingText: '处理中...',
      icon: <Wand2 size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述操作内容...' : '请先上传图片...',
    }
  );
};

const SCHEMA_BACKED_IMAGE_EDIT_MODES = new Set<AppMode>([
  'image-chat-edit',
  'image-mask-edit',
  'image-inpainting',
  'image-background-edit',
  'image-recontext',
  'image-outpainting',
  'virtual-try-on',
]);

const IMAGE_COUNT_OPTION_MODES = new Set<AppMode>([
  'image-chat-edit',
  'image-mask-edit',
  'image-inpainting',
  'image-background-edit',
  'image-recontext',
  'image-outpainting',
  'virtual-try-on',
]);

const VIDEO_EXTENSION_PROMPT_PLACEHOLDER =
  '全局/基础视频提示词：描述主体、风格、镜头和约束；延长分镜只写每段变化...';

// 根据模式选择 filePrefix（纯映射，无闭包依赖）
const MODE_FILE_PREFIX: Partial<Record<AppMode, string>> = {
  'image-chat-edit': 'canvas',
  'image-outpainting': 'expand',
  'image-inpainting': 'inpaint',
  'image-mask-edit': 'mask',
  'image-recontext': 'recontext',
  'image-background-edit': 'background',
  'video-gen': 'video',
  'audio-gen': 'audio',
};
const getFilePrefix = (mode: AppMode): string => MODE_FILE_PREFIX[mode] || 'file';

const ChatEditInputArea: React.FC<ChatEditInputAreaProps> = ({
  onSend,
  isLoading,
  onStop,
  mode = 'image-chat-edit',
  activeAttachments,
  onAttachmentsChange,
  activeImageUrl,
  onActiveImageUrlChange,
  activeCanvasAttachment, // ✅ 新增：画布图片对应的完整附件对象
  messages,
  sessionId,
  initialPrompt,
  initialAttachments,
  providerId = 'google',
  currentModel,
  controlsSchema,
  controls,
  buttonText,
  buttonIcon,
  loadingText,
  placeholder,
  maxAttachments = 10, // ✅ 默认最多 10 张图片
  externalDisabled = false,
  externalDisabledReason = null,
}) => {
  const { showError } = useToastContext();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const requiresAttachmentForMode = !['video-gen', 'audio-gen'].includes(mode);
  const requiresPromptForMode = mode !== 'image-outpainting';
  const supportsAttachments = mode !== 'audio-gen';
  const normalizedProviderId = (providerId || '').trim().toLowerCase();
  const shouldUseImageEditSchema =
    ['openai', 'tongyi'].includes(normalizedProviderId) && SCHEMA_BACKED_IMAGE_EDIT_MODES.has(mode);
  const fetchedImageEditSchema = useModeControlsSchema(providerId, mode, currentModel?.id, {
    enabled: shouldUseImageEditSchema && controlsSchema === undefined,
  });
  const effectiveControlsSchema =
    controlsSchema === undefined ? fetchedImageEditSchema.schema : controlsSchema;
  const attachmentAccept = useMemo(() => {
    if (mode !== 'video-gen') {
      return 'image/*';
    }

    const accepts = ['image/*', 'video/*'];
    const supportsAudio = effectiveControlsSchema?.videoContract?.attachmentSlots?.some(
      (slot) => slot.enabled !== false && slot.kind === 'audio'
    );
    if (supportsAudio) {
      accepts.push('audio/*');
    }
    return accepts.join(',');
  }, [effectiveControlsSchema, mode]);
  const shouldUseOpenAIImageEditSchema =
    normalizedProviderId === 'openai' && SCHEMA_BACKED_IMAGE_EDIT_MODES.has(mode);
  const openAIParamOptions = shouldUseOpenAIImageEditSchema
    ? (effectiveControlsSchema?.paramOptions ?? {})
    : {};
  const tongyiUnsupportedParams = useMemo(
    () =>
      normalizedProviderId === 'tongyi'
        ? getUnsupportedParams(effectiveControlsSchema)
        : new Set<string>(),
    [effectiveControlsSchema, normalizedProviderId]
  );
  const supportsTongyiNegativePrompt = !tongyiUnsupportedParams.has('negative_prompt');
  const supportsTongyiPromptExtend = !tongyiUnsupportedParams.has('prompt_extend');
  const supportsTongyiThinkingMode =
    !tongyiUnsupportedParams.has('thinking_mode') &&
    supportsBooleanParam(effectiveControlsSchema, 'thinking_mode');
  const supportsOpenAIQualityControls = Boolean(openAIParamOptions.quality?.length);
  const supportsOpenAIBackgroundControls = Boolean(openAIParamOptions.background?.length);
  const supportsOpenAIModerationControls = Boolean(openAIParamOptions.moderation?.length);
  const supportsOpenAIOutputFormatControls = Boolean(openAIParamOptions.output_format?.length);
  const supportsOpenAICompressionControls = Boolean(
    effectiveControlsSchema?.numericRanges?.output_compression_quality
  );

  // 提示词状态（仅此组件内部管理）
  const [prompt, setPrompt] = useState(initialPrompt || '');

  // 同步初始值
  useEffect(() => {
    if (initialPrompt) setPrompt(initialPrompt);
  }, [initialPrompt]);

  // 同步初始附件（仅在组件挂载时执行一次）
  useEffect(() => {
    if (initialAttachments !== undefined && initialAttachments.length > 0) {
      onAttachmentsChange(initialAttachments);
      const firstUrl = getPreferredAttachmentUrl(initialAttachments[0]);
      onActiveImageUrlChange(firstUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 只在挂载时执行一次

  const { handlePaste: handleAttachmentPaste, appendFiles } = useClipboardAttachments({
    mode,
    attachments: activeAttachments,
    onAttachmentsChange,
    maxAttachments,
    acceptedTypes: attachmentAccept,
    disabled: isLoading || !supportsAttachments,
    onError: showError,
  });

  const getAttachmentRoleOptions = useCallback(
    (attachment: Attachment) => {
      if (mode !== 'video-gen') return [];
      return getVideoAttachmentRoleOptions(effectiveControlsSchema, attachment);
    },
    [effectiveControlsSchema, mode]
  );

  const handleAttachmentRoleChange = useCallback(
    (attachmentId: string, role: string) => {
      onAttachmentsChange(
        activeAttachments.map((attachment) =>
          attachment.id === attachmentId
            ? {
                ...attachment,
                role,
              }
            : attachment
        )
      );
    },
    [activeAttachments, onAttachmentsChange]
  );

  // 文件上传处理（✅ 支持多文件选择）
  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files || files.length === 0) return;

      appendFiles(files);
      if (e.target) e.target.value = '';
    },
    [appendFiles]
  );

  // 删除附件
  const removeAttachment = useCallback(
    (id: string) => {
      // ✅ 注意：不在这里 revoke Blob URL
      // 原因：如果附件已经发送到消息中，消息可能仍在使用这个 Blob URL
      // 只有在确认附件不再被使用时才 revoke（例如消息被删除时）

      const newAtts = activeAttachments.filter((att) => att.id !== id);
      onAttachmentsChange(newAtts);

      // 如果删除后没有附件了，清空 activeImageUrl（由父组件管理）
      if (newAtts.length === 0) {
        onActiveImageUrlChange(null);
      }
    },
    [activeAttachments, onAttachmentsChange, onActiveImageUrlChange]
  );

  // ✅ 注意：不在这里清理 Blob URLs
  // 原因：用户消息中的附件可能仍在使用这些 Blob URL
  // Blob URL 的清理应该由消息生命周期管理，而不是组件卸载时清理

  // 发送逻辑
  const handleGenerate = useCallback(async () => {
    const missingRequiredPrompt = requiresPromptForMode && !prompt.trim();
    const missingRequiredAttachment =
      requiresAttachmentForMode && activeAttachments.length === 0 && !activeImageUrl;
    if (externalDisabled) {
      if (externalDisabledReason) {
        showError(externalDisabledReason);
      }
      return;
    }
    if (missingRequiredPrompt || isLoading || missingRequiredAttachment) return;

    try {
      // 逻辑：
      // 1. 如果用户上传了附件，使用上传的附件（优先，不传递 activeImageUrl）
      // 2. 如果没有上传附件，使用画布中的图片（CONTINUITY LOGIC，传递 activeImageUrl）
      // 3. processUserAttachments 会自动处理这个逻辑

      // ✅ 互斥逻辑：有附件用附件，没附件用画布图片
      const requestAttachments =
        mode === 'video-gen'
          ? applyDefaultVideoAttachmentRoles(effectiveControlsSchema, activeAttachments)
          : activeAttachments;

      const finalAttachments = await processUserAttachments(
        requestAttachments, // 用户上传的附件
        activeAttachments.length > 0 ? null : activeImageUrl, // 有附件时不用画布图片
        messages,
        sessionId,
        getFilePrefix(mode)
      );

      if (requiresAttachmentForMode && finalAttachments.length === 0) {
        showError('未能读取当前图片，请重新选择历史图片或重新上传附件');
        return;
      }

      const effectiveNumberOfImages =
        mode === 'image-outpainting' && controls.outpaintMode === 'upscale'
          ? 1
          : controls.numberOfImages;
      const openAIContinuationResponseId =
        normalizedProviderId === 'openai' &&
        SCHEMA_BACKED_IMAGE_EDIT_MODES.has(mode) &&
        activeAttachments.length === 0
          ? activeCanvasAttachment?.openaiResponseId
          : undefined;
      const supportsOutputMimeOptions =
        !['image-recontext', 'product-recontext', 'video-gen', 'audio-gen'].includes(mode) &&
        normalizedProviderId !== 'openai' &&
        !supportsOpenAIOutputFormatControls;

      // 构建 ChatOptions
      const options: ChatOptions = {
        enableSearch: false,
        enableThinking: controls.enableThinking,
        enableCodeExecution: false,
        ...(mode === 'video-gen'
          ? {
              aspectRatio: controls.aspectRatio,
              resolution: controls.resolution,
              seconds: controls.videoSeconds,
              videoInputStrategy: controls.videoInputStrategy || undefined,
              videoExtensionCount:
                controls.videoExtensionCount > 0 ? controls.videoExtensionCount : undefined,
              storyboardShotSeconds: controls.storyboardShotSeconds,
              generateAudio: controls.generateAudio,
              subtitleMode: controls.subtitleMode || undefined,
              subtitleLanguage: controls.subtitleLanguage || undefined,
              subtitleScript:
                !controls.generateAudio && controls.subtitleMode !== 'none'
                  ? controls.subtitleScript.trim() || undefined
                  : undefined,
              storyboardPrompt: controls.storyboardPrompt.trim() || undefined,
              storyboardSegments: controls.storyboardSegments
                .slice(0, Math.max(0, controls.videoExtensionCount))
                .map((segment) => segment.trim())
                .filter(Boolean),
            }
          : {
              imageAspectRatio: controls.aspectRatio,
              imageResolution: controls.resolution,
            }),
        ...(IMAGE_COUNT_OPTION_MODES.has(mode) ? { numberOfImages: effectiveNumberOfImages } : {}),
        negativePrompt:
          normalizedProviderId === 'tongyi' && !supportsTongyiNegativePrompt
            ? undefined
            : controls.negativePrompt || undefined,
        seed: controls.seed !== -1 ? controls.seed : undefined,
        ...(supportsOutputMimeOptions
          ? {
              outputMimeType: controls.outputMimeType,
              // PNG 是无损格式，不需要压缩质量参数，仅 JPEG 时传递
              ...(controls.outputMimeType === 'image/jpeg'
                ? { outputCompressionQuality: controls.outputCompressionQuality }
                : {}),
            }
          : {}),
        enhancePrompt: controls.enhancePrompt,
        enhancePromptModel: controls.enhancePromptModel || undefined,
        enhancePromptThinkingLevel: controls.enhancePrompt
          ? controls.enhancePromptThinkingLevel
          : undefined,
        ...(supportsOpenAIQualityControls ? { quality: controls.quality } : {}),
        ...(supportsOpenAIBackgroundControls ? { background: controls.background } : {}),
        ...(supportsOpenAIModerationControls ? { moderation: controls.moderation } : {}),
        ...(supportsOpenAIOutputFormatControls
          ? {
              outputFormat: controls.outputFormat,
              ...((controls.outputFormat === 'jpeg' || controls.outputFormat === 'webp') &&
              supportsOpenAICompressionControls
                ? { outputCompressionQuality: controls.outputCompressionQuality }
                : {}),
            }
          : {}),
        ...(openAIContinuationResponseId
          ? { openaiPreviousResponseId: openAIContinuationResponseId }
          : {}),
        ...(normalizedProviderId === 'tongyi' &&
        SCHEMA_BACKED_IMAGE_EDIT_MODES.has(mode) &&
        supportsTongyiPromptExtend
          ? { promptExtend: controls.promptExtend }
          : {}),
        ...(normalizedProviderId === 'tongyi' &&
        SCHEMA_BACKED_IMAGE_EDIT_MODES.has(mode) &&
        supportsTongyiThinkingMode
          ? { thinkingMode: controls.thinkingMode }
          : {}),
      };

      // ✅ Mask 编辑模式特有参数
      if (mode === 'image-mask-edit') {
        options.editMode = controls.editMode;
        options.maskDilation = controls.maskDilation;
        options.guidanceScale = controls.guidanceScale;
        options.maskMode = controls.maskMode; // Vertex AI MaskReferenceConfig.mask_mode
      }

      // ✅ Outpainting 模式特有参数（传递给 ExpandService）
      if (mode === 'image-outpainting') {
        type OutpaintOptions = Omit<ChatOptions, 'upscaleFactor'> & {
          outpaintMode?: 'ratio' | 'scale' | 'offset' | 'upscale';
          xScale?: number;
          yScale?: number;
          leftOffset?: number;
          rightOffset?: number;
          topOffset?: number;
          bottomOffset?: number;
          outputRatio?: string;
          upscaleFactor?: 'x2' | 'x3' | 'x4';
        };
        const outpaintOptions = options as OutpaintOptions;
        // 扩图模式：ratio | scale | offset | upscale
        outpaintOptions.outpaintMode = controls.outpaintMode;

        // 根据扩图模式传递不同的参数
        if (controls.outpaintMode === 'scale') {
          // 缩放模式：x_scale, y_scale
          outpaintOptions.xScale = controls.xScale;
          outpaintOptions.yScale = controls.yScale;
        } else if (controls.outpaintMode === 'offset') {
          // 偏移模式：left_offset, right_offset, top_offset, bottom_offset
          outpaintOptions.leftOffset = controls.offsetPixels.left;
          outpaintOptions.rightOffset = controls.offsetPixels.right;
          outpaintOptions.topOffset = controls.offsetPixels.top;
          outpaintOptions.bottomOffset = controls.offsetPixels.bottom;
        } else if (controls.outpaintMode === 'ratio') {
          // 比例模式：使用 aspectRatio
          outpaintOptions.outputRatio = controls.aspectRatio;
        } else if (controls.outpaintMode === 'upscale') {
          // 放大模式：upscale_factor
          outpaintOptions.upscaleFactor = controls.upscaleFactor;
        }
      }

      onSend(prompt, options, finalAttachments, mode);
      setPrompt(''); // 发送后清空提示词

      // 发送后清空附件预览
      if (activeAttachments.length > 0) {
        onAttachmentsChange([]);
      }
    } catch (error) {
      showError('处理附件失败，请重试');
    }
  }, [
    prompt,
    isLoading,
    activeAttachments,
    activeImageUrl,
    activeCanvasAttachment,
    effectiveControlsSchema,
    messages,
    mode,
    normalizedProviderId,
    sessionId,
    controls,
    onSend,
    showError,
    onAttachmentsChange,
    requiresAttachmentForMode,
    requiresPromptForMode,
    externalDisabled,
    externalDisabledReason,
    supportsOpenAIBackgroundControls,
    supportsOpenAICompressionControls,
    supportsOpenAIModerationControls,
    supportsOpenAIOutputFormatControls,
    supportsOpenAIQualityControls,
    supportsTongyiNegativePrompt,
    supportsTongyiPromptExtend,
    supportsTongyiThinkingMode,
  ]);

  // 键盘快捷键
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleGenerate();
      }
    },
    [handleGenerate]
  );

  // 根据模式获取按钮配置
  const hasAttachmentsOrImage = activeAttachments.length > 0 || !!activeImageUrl;
  const modeConfig = useMemo(
    () => getModeButtonConfig(mode, hasAttachmentsOrImage),
    [mode, hasAttachmentsOrImage]
  );

  // 使用自定义文本或模式默认文本
  const finalButtonText = buttonText || modeConfig.text;
  const finalLoadingText = loadingText || modeConfig.loadingText;
  const finalButtonIcon = buttonIcon || modeConfig.icon;
  const isVideoExtensionEnabled = mode === 'video-gen' && controls.videoExtensionCount > 0;
  const finalPlaceholder =
    placeholder ||
    (isVideoExtensionEnabled ? VIDEO_EXTENSION_PROMPT_PLACEHOLDER : modeConfig.placeholder);

  // 判断是否必须有附件（video-gen 参考图可选）
  const isDisabled =
    (requiresPromptForMode && !prompt.trim()) ||
    isLoading ||
    externalDisabled ||
    (requiresAttachmentForMode && activeAttachments.length === 0 && !activeImageUrl);
  const attachmentTitle =
    activeAttachments.length >= maxAttachments
      ? `已达到最大数量 (${maxAttachments})`
      : mode === 'video-gen'
        ? '点击上传图片或视频（支持多选，作为视频参考）'
        : '点击上传图片（支持多选）';

  return (
    <div className="border-t border-slate-800 p-3 space-y-2 bg-slate-900/80">
      {/* 附件预览 - 使用 AttachmentPreview 组件（仅在需要附件的模式显示） */}
      {supportsAttachments && (
        <AttachmentPreview
          attachments={activeAttachments}
          removeAttachment={removeAttachment}
          getRoleOptions={mode === 'video-gen' ? getAttachmentRoleOptions : undefined}
          onRoleChange={mode === 'video-gen' ? handleAttachmentRoleChange : undefined}
        />
      )}

      {/* 提示词输入 */}
      <textarea
        ref={textareaRef}
        value={prompt}
        onChange={(e) => {
          setPrompt(e.target.value);
          e.target.style.height = 'auto';
          e.target.style.height = Math.min(e.target.scrollHeight, 150) + 'px';
        }}
        onPaste={handleAttachmentPaste}
        onKeyDown={handleKeyDown}
        placeholder={finalPlaceholder}
        className="w-full min-h-[40px] max-h-[150px] bg-slate-800/80 border border-slate-700 rounded-lg p-2.5 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 overflow-y-auto"
      />

      {/* 上传按钮 + 操作按钮 */}
      <div className="flex gap-2 items-center">
        {/* 上传按钮（仅在需要附件的模式显示，✅ 支持多文件选择） */}
        {supportsAttachments && (
          <label
            className={`p-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 cursor-pointer transition-colors border border-indigo-500/50 flex-shrink-0 shadow-lg relative ${
              activeAttachments.length >= maxAttachments ? 'opacity-50 cursor-not-allowed' : ''
            }`}
            title={attachmentTitle}
          >
            <input
              type="file"
              accept={attachmentAccept}
              multiple={maxAttachments > 1}
              className="hidden"
              onChange={handleFileSelect}
              disabled={activeAttachments.length >= maxAttachments}
            />
            {activeAttachments.length === 0 ? (
              <ImageIcon size={18} className="text-white" />
            ) : (
              <div className="relative">
                <Paperclip size={18} className="text-white" />
                {/* ✅ 显示附件计数 */}
                <span className="absolute -top-2 -right-2 bg-pink-500 text-white text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                  {activeAttachments.length}
                </span>
              </div>
            )}
          </label>
        )}

        {/* 操作按钮（编辑/生成/扩图等） */}
        <button
          onClick={handleGenerate}
          disabled={isDisabled}
          className={`${supportsAttachments ? 'flex-1' : 'w-full'} py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {isLoading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              {finalLoadingText}
            </>
          ) : (
            <>
              {finalButtonIcon}
              {finalButtonText}
            </>
          )}
        </button>
      </div>

      {externalDisabledReason && (
        <div className="text-[11px] text-amber-400">{externalDisabledReason}</div>
      )}
    </div>
  );
};

export default ChatEditInputArea;
