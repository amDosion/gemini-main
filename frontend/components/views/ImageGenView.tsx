import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import {
  Image as ImageIcon,
  Layers,
  Clock,
  SlidersHorizontal,
  RotateCcw,
  Sparkles,
} from 'lucide-react';
import { GenViewLayout } from '../common/GenViewLayout';
import { ImageResultCanvas } from '../common/ImageResultCanvas';
import { type CarouselMediaItem } from '../common/ImageCarouselControls';
import { ThinkingBlock } from '../message/ThinkingBlock';
import { AttachmentPreview } from '../chat/input/AttachmentPreview';
import { useControlsState } from '../../hooks/useControlsState';
import { useModeControlsSchema } from '../../hooks/useModeControlsSchema';
import {
  getUnsupportedParams,
  supportsBooleanParam,
} from '../../controls/shared/modeControlSchemaUtils';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { useImageCarousel } from '../../hooks/useImageCarousel';
import { processUserAttachments } from '../../hooks/handlers/attachmentUtils';
import { useClipboardAttachments } from '../../hooks/useClipboardAttachments';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import { useImageHistorySidebar } from '../common/ImageHistorySidebar';
import { getPreferredImageAttachmentUrl, revokeAttachmentObjectUrls } from '../../utils/attachmentUrl';
import { useThinkingBlock } from '../../hooks/useThinkingBlock';

interface ImageGenViewProps {
  messages: Message[];
  setAppMode: (mode: AppMode) => void;
  onImageClick: (url: string) => void;
  loadingState: string;
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  onStop: () => void;
  activeModelConfig?: ModelConfig;
  visibleModels?: ModelConfig[]; // 当前模式下可见的模型列表
  allVisibleModels?: ModelConfig[]; // ✅ 新增：完整模型列表
  initialPrompt?: string;
  onEditImage?: (url: string, attachment?: Attachment) => void;
  onExpandImage?: (url: string, attachment?: Attachment) => void; // ✅ 修复：添加可选的 attachment 参数
  providerId?: string;
  sessionId?: string | null;
  onDeleteMessage?: (messageId: string) => void;
}

const extractHistoryPrompts = (
  msg: Message
): { originalPrompt: string; enhancedPrompt: string } => {
  const rawContent = (msg.content || '').trim();
  const attachmentEnhancedPrompt = msg.attachments
    ?.find((att) => att.enhancedPrompt?.trim())
    ?.enhancedPrompt?.trim();

  let originalPrompt = rawContent;
  let optimizedPrompt = msg.enhancedPrompt?.trim() || attachmentEnhancedPrompt || '';

  const promptPairMatch = rawContent.match(/^📝\s*([\s\S]*?)(?:\n✨\s*([\s\S]*))?$/);
  if (promptPairMatch) {
    originalPrompt = (promptPairMatch[1] || '').trim();
    if (!optimizedPrompt && promptPairMatch[2]) {
      optimizedPrompt = promptPairMatch[2].trim();
    }
  } else {
    const originalOnlyMatch = rawContent.match(/^📝\s*([\s\S]*)$/);
    if (originalOnlyMatch) {
      originalPrompt = originalOnlyMatch[1].trim();
    }

    if (!optimizedPrompt) {
      const optimizedOnlyMatch = rawContent.match(/^✨\s*([\s\S]*)$/);
      if (optimizedOnlyMatch) {
        optimizedPrompt = optimizedOnlyMatch[1].trim();
      }
    }
  }

  return {
    originalPrompt: originalPrompt || 'Generated Image Batch',
    enhancedPrompt: optimizedPrompt,
  };
};

export const ImageGenView: React.FC<ImageGenViewProps> = ({
  messages,
  setAppMode,
  onImageClick,
  loadingState,
  onSend,
  onStop,
  activeModelConfig,
  visibleModels = [],
  allVisibleModels = [], // ✅ 新增
  initialPrompt,
  onEditImage,
  onExpandImage,
  providerId,
  sessionId,
  onDeleteMessage,
}) => {
  // Track selected MESSAGE ID (Batch)
  const [selectedMsgId, setSelectedMsgId] = useState<string | null>(null);
  // Mobile History Toggle
  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
  const [carouselInitialIndex, setCarouselInitialIndex] = useState(0);

  // ✅ 使用统一的状态管理 hook
  const controls = useControlsState('image-gen', activeModelConfig);

  // ✅ 图片缩放 hook（用于单图放大查看）
  const canvas = useImageCanvas({ minZoom: 0.5, maxZoom: 5, initialZoom: 1 });
  const { resetView } = canvas;

  // ✅ 本地 UI 状态
  const [prompt, setPrompt] = useState(initialPrompt || '');
  const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const activeAttachmentsRef = useRef<Attachment[]>(activeAttachments);

  const isLoading = loadingState !== 'idle';

  useEffect(() => {
    activeAttachmentsRef.current = activeAttachments;
  }, [activeAttachments]);

  useEffect(() => {
    return () => {
      activeAttachmentsRef.current.forEach((attachment) => {
        revokeAttachmentObjectUrls(attachment);
      });
    };
  }, []);

  const removeReferenceAttachment = useCallback((id: string) => {
    setActiveAttachments((current) => {
      const attachmentToRemove = current.find((attachment) => attachment.id === id);
      revokeAttachmentObjectUrls(attachmentToRemove);
      return current.filter((attachment) => attachment.id !== id);
    });
  }, []);

  const { handlePaste: handleAttachmentPaste } = useClipboardAttachments({
    mode: 'image-gen',
    attachments: activeAttachments,
    onAttachmentsChange: setActiveAttachments,
    maxAttachments: 10,
    acceptedTypes: 'image/*',
    disabled: isLoading,
  });

  // ✅ 思考过程状态 — 由 useThinkingBlock 提供（含 typewriter + isOpen 控制）
  const {
    isOpen: isThinkingOpen,
    setIsOpen: setIsThinkingOpen,
    displayedContent: displayedThinkingContent,
  } = useThinkingBlock(messages, loadingState);

  // ✅ 检测提供商类型
  const isOpenAI = providerId === 'openai';

  // ✅ 从 schema 获取最大图片数量（按模型动态调整）
  const { schema: genSchema } = useModeControlsSchema(
    providerId,
    'image-gen',
    activeModelConfig?.id,
    // 等 activeModelConfig 就绪才 fetch，避免 mount 时 modelId 未定义的浪费请求
    { enabled: !!activeModelConfig?.id }
  );
  const schemaMaxCount = (genSchema?.constraints as Record<string, unknown>)?.max_image_count;
  const maxImageCount = typeof schemaMaxCount === 'number' ? schemaMaxCount : isOpenAI ? 1 : 4;
  const supportsOutputMimeControls = Boolean(genSchema?.paramOptions?.output_mime_type?.length);
  const supportsOutputFormatControls = Boolean(genSchema?.paramOptions?.output_format?.length);
  const supportsOpenAiQualityControls = Boolean(genSchema?.paramOptions?.quality?.length);
  const supportsOpenAiBackgroundControls = Boolean(genSchema?.paramOptions?.background?.length);
  const supportsOpenAiModerationControls = Boolean(genSchema?.paramOptions?.moderation?.length);
  const supportsOpenAiCompressionControls = Boolean(
    genSchema?.numericRanges?.output_compression_quality
  );
  const unsupportedParams = useMemo(() => getUnsupportedParams(genSchema), [genSchema]);
  const supportsImageStyle = !unsupportedParams.has('style');
  const supportsNegativePrompt = !unsupportedParams.has('negative_prompt');
  const supportsPromptExtend = !unsupportedParams.has('prompt_extend');
  const supportsAddMagicSuffix = !unsupportedParams.has('add_magic_suffix');
  const supportsThinkingMode =
    !unsupportedParams.has('thinking_mode') && supportsBooleanParam(genSchema, 'thinking_mode');
  const supportsEnableSequential =
    providerId === 'tongyi' &&
    !unsupportedParams.has('enable_sequential') &&
    supportsBooleanParam(genSchema, 'enable_sequential');
  const effectiveMaxImageCount =
    supportsEnableSequential && !controls.enableSequential
      ? Math.min(maxImageCount, 4)
      : maxImageCount;

  useEffect(() => {
    if (controls.numberOfImages > effectiveMaxImageCount) {
      controls.setNumberOfImages(effectiveMaxImageCount);
    }
  }, [controls.numberOfImages, effectiveMaxImageCount, controls]);

  // ✅ 重置参数
  const resetParams = useCallback(() => {
    controls.setStyle('None');
    controls.setNumberOfImages(1);
    controls.setAspectRatio('1:1');
    controls.setResolution('1K');
    controls.setNegativePrompt('');
    controls.setSeed(-1);
    controls.setOutputMimeType('image/png');
    controls.setOutputCompressionQuality(100);
    controls.setQuality('auto');
    controls.setBackground('auto');
    controls.setModeration('auto');
    controls.setOutputFormat('png');
    controls.setEnhancePrompt(false);
    controls.setEnableSequential(false);
  }, [controls]);

  const prevLoadingStateRef = useRef(loadingState);
  useEffect(() => {
    const prevState = prevLoadingStateRef.current;
    prevLoadingStateRef.current = loadingState;

    if (loadingState === 'loading') {
      setSelectedMsgId(null);
      setCarouselInitialIndex(0);
      setIsMobileHistoryOpen(false);
    }
    // When loading just finished, force select the latest result
    if (prevState !== 'idle' && loadingState === 'idle') {
      setSelectedMsgId(null); // null = show historyBatches[0] (latest)
      setCarouselInitialIndex(0);
    }
  }, [loadingState]);

  // 1. Group History by Message (Batch)
  const historyBatches = useMemo(() => {
    return messages
      .filter(
        (m) => m.role === Role.MODEL && ((m.attachments && m.attachments.length > 0) || m.isError)
      )
      .reverse();
  }, [messages]);

  // 2. Determine Active Batch to Display
  const activeBatchMessage = useMemo(() => {
    if (selectedMsgId) {
      return historyBatches.find((m) => m.id === selectedMsgId);
    }
    return historyBatches[0];
  }, [selectedMsgId, historyBatches]);

  const getGeneratedAttachmentUrl = useCallback(
    (attachment: Attachment) => getPreferredImageAttachmentUrl(attachment),
    []
  );

	  const getDisplayImageAttachments = useCallback(
	    (attachments?: Attachment[]) => {
	      return (attachments || []).filter((attachment) =>
	        Boolean(attachment.file || getGeneratedAttachmentUrl(attachment))
	      );
	    },
	    [getGeneratedAttachmentUrl]
	  );

	  const displayImages = useMemo(() => {
	    return getDisplayImageAttachments(activeBatchMessage?.attachments).map((att, index) => {
	      const fallbackId = att.id || `${activeBatchMessage?.id || 'image-gen'}-${index}`;
	      const sourceAttachment = att.id ? att : { ...att, id: fallbackId };
	      const displayUrl = getGeneratedAttachmentUrl(sourceAttachment);
	      if (displayUrl) {
	        return displayUrl === sourceAttachment.url
	          ? sourceAttachment
	          : { ...sourceAttachment, url: displayUrl };
	      }
	      return sourceAttachment;
	    });
	  }, [
	    activeBatchMessage?.attachments,
	    activeBatchMessage?.id,
	    getDisplayImageAttachments,
	    getGeneratedAttachmentUrl,
	  ]);

  const carouselItems = useMemo<CarouselMediaItem[]>(
    () =>
	      displayImages.map((att, idx) => ({
	        id: att.id || `${idx}`,
	        url: att.url || null,
	        thumbUrl: att.url || null,
	        source: {
	          ...att,
	          attachmentId: att.id,
	          url: att.url || undefined,
	        },
	        alt: `缩略图 ${idx + 1}`,
	      })),
    [displayImages]
  );

  const {
    index: carouselIndex,
    goPrev: handleCarouselPrev,
    goNext: handleCarouselNext,
    select: handleCarouselSelect,
  } = useImageCarousel({
    itemCount: displayImages.length,
    initialIndex: carouselInitialIndex,
    resetKey: activeBatchMessage?.id || null,
    keyboardEnabled: true,
    onNavigate: canvas.resetView,
  });

  // 批次切换时同步重置画布
  useEffect(() => {
    resetView();
  }, [activeBatchMessage?.id, resetView]);

  const activeImageUrl = displayImages[carouselIndex]?.url || null;
  const isBatchError = activeBatchMessage?.isError;

  // ✅ 生成处理函数
  const handleGenerate = useCallback(async () => {
    if (!prompt.trim() || isLoading) return;

    const options: ChatOptions = {
      enableSearch: false,
      enableThinking: controls.enableThinking,
      enableCodeExecution: false,
      // 基础参数
      imageAspectRatio: controls.aspectRatio,
      imageResolution: controls.resolution,
      numberOfImages: Math.min(controls.numberOfImages, effectiveMaxImageCount),
      imageStyle: supportsImageStyle && controls.style !== 'None' ? controls.style : undefined,
      // Google Imagen 高级参数
      negativePrompt: supportsNegativePrompt ? controls.negativePrompt || undefined : undefined,
      seed: controls.seed !== -1 ? controls.seed : undefined,
      ...(supportsOutputMimeControls
        ? {
            outputMimeType: controls.outputMimeType,
            // PNG 是无损格式，不需要压缩质量参数，仅 JPEG 时传递
            ...(controls.outputMimeType === 'image/jpeg'
              ? { outputCompressionQuality: controls.outputCompressionQuality }
              : {}),
          }
        : {}),
      ...(supportsOpenAiQualityControls ? { quality: controls.quality } : {}),
      ...(supportsOpenAiBackgroundControls ? { background: controls.background } : {}),
      ...(supportsOpenAiModerationControls ? { moderation: controls.moderation } : {}),
      ...(supportsOutputFormatControls
        ? {
            outputFormat: controls.outputFormat,
            ...((controls.outputFormat === 'jpeg' || controls.outputFormat === 'webp') &&
            supportsOpenAiCompressionControls
              ? { outputCompressionQuality: controls.outputCompressionQuality }
              : {}),
          }
        : {}),
      enhancePrompt: controls.enhancePrompt,
      enhancePromptModel: controls.enhancePromptModel || undefined,
      enhancePromptThinkingLevel: controls.enhancePrompt
        ? controls.enhancePromptThinkingLevel
        : undefined,
      // TongYi 专用参数
      ...(providerId === 'tongyi' && supportsPromptExtend
        ? { promptExtend: controls.promptExtend }
        : {}),
      ...(providerId === 'tongyi' && supportsAddMagicSuffix
        ? { addMagicSuffix: controls.addMagicSuffix }
        : {}),
      ...(providerId === 'tongyi' && supportsEnableSequential
        ? { enableSequential: controls.enableSequential }
        : {}),
      ...(providerId === 'tongyi' && supportsThinkingMode && !controls.enableSequential
        ? { thinkingMode: controls.thinkingMode }
        : {}),
    };

    const finalAttachments = await processUserAttachments(
      activeAttachments,
      null,
      messages,
      sessionId || null,
      'reference'
    );

    onSend(prompt, options, finalAttachments, 'image-gen');
    setPrompt(''); // 发送后清空提示词
    setActiveAttachments([]);
  }, [
    activeAttachments,
    controls,
    isLoading,
    messages,
    onSend,
    prompt,
    sessionId,
    supportsOutputMimeControls,
    supportsOutputFormatControls,
    supportsOpenAiBackgroundControls,
    supportsOpenAiCompressionControls,
    supportsOpenAiModerationControls,
    supportsOpenAiQualityControls,
    supportsAddMagicSuffix,
    supportsImageStyle,
    supportsNegativePrompt,
    supportsPromptExtend,
    supportsThinkingMode,
    supportsEnableSequential,
    effectiveMaxImageCount,
    providerId,
  ]);

  // ✅ 键盘快捷键
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleGenerate();
      }
    },
    [handleGenerate]
  );

  // Sidebar header icon and extra header
  const sidebarHeaderIcon = <Clock size={14} />;

  const { sidebarExtraHeader, sidebarContent } = useImageHistorySidebar({
    items: historyBatches,
    sessionId,
    onDeleteMessage,
    activeImageUrl,
    selectedMessageId: selectedMsgId,
    onSelectedMessageIdChange: setSelectedMsgId,
    onMobileHistoryOpenChange: setIsMobileHistoryOpen,
    modelLabel: activeModelConfig?.name || 'AI',
    accent: 'emerald',
    emptyText: 'No generation history.',
    fallbackSelection: 'first',
    getDisplayAttachments: getDisplayImageAttachments,
	    getAttachmentUrl: getGeneratedAttachmentUrl,
    extractPrompts: extractHistoryPrompts,
    onSelectItem: ({ message }) => {
      setSelectedMsgId(message.id);
      setCarouselInitialIndex(0);
      handleCarouselSelect(0);
    },
    onSelectPreviewAttachment: ({ message, attachment, index }) => {
      setSelectedMsgId(message.id);
      setCarouselInitialIndex(index);
      handleCarouselSelect(index);
    },
  });

  // ✅ 主区域：两栏布局（结果显示 + 控制面板）
  // 注意：GenViewLayout 的 main 容器已有 overflow-hidden，这里不需要重复
  const mainContent = useMemo(
    () => (
      <div className="flex-1 flex flex-row h-full">
        {/* ========== 左侧：结果显示区 ========== */}
        <ImageResultCanvas
          loadingState={loadingState}
          isBatchError={isBatchError}
          errorTitle="生成失败"
          errorMessage={activeBatchMessage?.content}
          displayImages={displayImages}
          carouselItems={carouselItems}
          carouselIndex={carouselIndex}
          handleCarouselPrev={handleCarouselPrev}
          handleCarouselNext={handleCarouselNext}
          handleCarouselSelect={handleCarouselSelect}
          onImageClick={onImageClick}
          altFor={(idx) => `生成图片 ${idx + 1}`}
          canvas={canvas}
          mode="image-gen"
          accentColor="pink"
          controlsExtra={{
            onEdit: onEditImage
              ? () => onEditImage(displayImages[carouselIndex].url!, displayImages[carouselIndex])
              : undefined,
            onExpand: onExpandImage
              ? () => onExpandImage(displayImages[carouselIndex].url!, displayImages[carouselIndex])
              : undefined,
            onFullscreen: () => onImageClick(displayImages[carouselIndex].url!),
          }}
          spinnerColorClass="border-emerald-500/30 border-t-emerald-500"
          spinnerBadgeText="GEN"
          spinnerBadgeColorClass="text-emerald-400"
          loadingWrapperExtraClass="max-w-lg w-full"
          accentIconClass="text-emerald-400"
          carouselAccentTone="emerald"
          wheelTarget="carousel"
          loadingExtraContent={
            displayedThinkingContent && (
              <div className="w-full mt-2">
                <ThinkingBlock
                  content={displayedThinkingContent}
                  isOpen={isThinkingOpen}
                  onToggle={() => setIsThinkingOpen(!isThinkingOpen)}
                  isComplete={false}
                />
              </div>
            )
          }
          floatingExtraContent={
            displayedThinkingContent && (
              <div className="absolute bottom-4 left-4 right-4 z-10 max-w-lg">
                <ThinkingBlock
                  content={displayedThinkingContent}
                  isOpen={isThinkingOpen}
                  onToggle={() => setIsThinkingOpen(!isThinkingOpen)}
                  isComplete={true}
                />
              </div>
            )
          }
          emptyState={
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
                <ImageIcon size={48} className="opacity-20" />
                <div>
                  <h3 className="text-xl font-bold text-slate-500 mb-2">Image Generator</h3>
                  <p className="text-sm opacity-60">在右侧输入提示词，设置参数后点击生成</p>
                </div>
              </div>
            </div>
          }
        />

        {/* ========== 中间：控制面板 ========== */}
        <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
          {/* 头部 */}
          <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={14} className="text-emerald-400" />
              <span className="text-xs font-bold text-white">生成参数</span>
            </div>
            <button
              onClick={resetParams}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
              title="重置为默认值"
            >
              <RotateCcw size={12} />
            </button>
          </div>

          {/* 参数滚动区 - 通过 ModeControlsCoordinator 分发对应的参数组件 */}
          <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
            <ModeControlsCoordinator
              mode="image-gen"
              providerId={providerId || 'google'}
              currentModel={activeModelConfig}
              controls={controls}
              availableModels={allVisibleModels}
              maxImageCount={maxImageCount}
            />
          </div>

          {/* 底部固定区：提示词 + 生成按钮 */}
          <div className="border-t border-slate-800 p-3 space-y-2 bg-slate-900/80">
            <AttachmentPreview
              attachments={activeAttachments}
              removeAttachment={removeReferenceAttachment}
            />
            {/* 提示词输入 - 自动调整高度 */}
            <textarea
              ref={textareaRef}
              value={prompt}
              onChange={(e) => {
                setPrompt(e.target.value);
                // 自动调整高度
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 300) + 'px';
              }}
              onPaste={handleAttachmentPaste}
              onKeyDown={handleKeyDown}
              placeholder="描述你想要生成的图片..."
              className="w-full min-h-[80px] max-h-[300px] bg-slate-800/80 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 overflow-y-auto"
            />

            {/* 生成按钮 */}
            <button
              onClick={handleGenerate}
              disabled={!prompt.trim() || isLoading}
              className="w-full py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <Sparkles size={18} />
                  生成图片
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    ),
    [
      isLoading,
      isBatchError,
      displayImages,
      displayedThinkingContent,
      isThinkingOpen,
      activeBatchMessage,
      activeAttachments,
      onImageClick,
      onEditImage,
      onExpandImage,
      prompt,
      controls,
      handleGenerate,
      handleAttachmentPaste,
      handleKeyDown,
      removeReferenceAttachment,
      maxImageCount,
      resetParams,
      providerId,
      activeModelConfig,
      carouselIndex,
      carouselItems,
      handleCarouselPrev,
      handleCarouselNext,
      handleCarouselSelect,
      canvas,
    ]
  );

  return (
    <GenViewLayout
      isMobileHistoryOpen={isMobileHistoryOpen}
      setIsMobileHistoryOpen={setIsMobileHistoryOpen}
      sidebarTitle="History"
      sidebarHeaderIcon={sidebarHeaderIcon}
      sidebarExtraHeader={sidebarExtraHeader}
      sidebar={sidebarContent}
      main={mainContent}
    />
  );
};
