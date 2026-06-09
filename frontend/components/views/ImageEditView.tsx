import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Layers, Bot, Sparkles, MessageSquare, SlidersHorizontal, RotateCcw } from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageEditMainCanvas } from './imageEdit/ImageEditMainCanvas';
import { GenViewLayout } from '../common/GenViewLayout';
import { ThinkingBlock } from '../message/ThinkingBlock';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { useImageCarousel } from '../../hooks/useImageCarousel';
import { useAutoSelectGeneratedImageResult } from '../../hooks/useAutoSelectGeneratedImageResult';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../chat/ChatEditInputArea';
import { extractImageHistoryPrompts, useImageHistorySidebar } from '../common/ImageHistorySidebar';
import {
  getPreferredImageAttachmentUrl,
  isTemporaryAttachmentUrl,
} from '../../utils/attachmentUrl';
import { useThinkingBlock } from '../../hooks/useThinkingBlock';
import { useStableAttachmentImageUrl } from '../../hooks/useStableAttachmentImageUrl';
import { buildMessagesMediaSignature } from '../../utils/messageMediaSignature';

interface ImageEditViewProps {
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
  initialAttachments?: Attachment[];
  onExpandImage?: (url: string) => void; // Added prop
  providerId?: string;
  sessionId?: string | null; // ✅ 会话 ID，用于查询附件
  onDeleteMessage?: (messageId: string) => void;
}

export const ImageEditView: React.FC<ImageEditViewProps> = ({
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
  initialAttachments,
  onExpandImage,
  providerId,
  sessionId: currentSessionId, // ✅ 接收 sessionId
  onDeleteMessage,
}) => {
  const { showError } = useToastContext();

  // State for reference image
  const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
  const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);
  // ✅ 新增：存储当前画布图片对应的完整附件对象（包含元数据）
  const [activeCanvasAttachment, setActiveCanvasAttachment] = useState<Attachment | null>(null);
  const [selectedHistoryMsgId, setSelectedHistoryMsgId] = useState<string | null>(null);
  const [carouselInitialIndex, setCarouselInitialIndex] = useState(0);

  // ✅ 包装 setActiveAttachments 以添加调试日志
  const handleAttachmentsChange = useCallback((newAtts: Attachment[]) => {
    if (newAtts.length > 0) {
      setSelectedHistoryMsgId(null);
    }
    setActiveAttachments(newAtts);
  }, []);

  // 固定使用 image-chat-edit 模式（此视图专门用于对话式编辑）
  const editMode: AppMode = 'image-chat-edit';

  // State for thinking block
  const {
    isOpen: isThinkingOpen,
    setIsOpen: setIsThinkingOpen,
    displayedContent: displayedThinkingContent,
  } = useThinkingBlock(messages, loadingState);

  const getStableCanvasUrlFromAttachment = useStableAttachmentImageUrl(activeAttachments, {
    createFileObjectUrls: false,
  });
  const messagesMediaSignature = buildMessagesMediaSignature(messages);

  // 对比模式状态
  const [isCompareMode, setIsCompareMode] = useState(false);

  // ✅ 参数面板状态（使用统一的 controls 状态）
  const controls = useControlsState(editMode, activeModelConfig);
  // 注意：prompt 和 textareaRef 现在由 ChatEditInputArea 管理

  // 重置参数
  const resetParams = useCallback(() => {
    controls.setAspectRatio('1:1');
    controls.setResolution('1K');
    controls.setNegativePrompt('');
    controls.setSeed(-1);
    controls.setOutputMimeType('image/png');
    controls.setOutputCompressionQuality(100);
  }, [controls]);

  // Pan & Zoom Hook（替代原有的手动状态管理）
  const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });

  const selectedCanvasMessage = useMemo(() => {
    if (selectedHistoryMsgId) {
      return messages.find((msg) => msg.id === selectedHistoryMsgId) || null;
    }
    if (activeAttachments.length > 0) return null;
    return (
      [...messages].reverse().find((msg) =>
        (msg.attachments || []).some((att) => {
          const stableUrl = getStableCanvasUrlFromAttachment(att);
          return Boolean(stableUrl);
        })
      ) || null
    );
  }, [
    activeAttachments.length,
    getStableCanvasUrlFromAttachment,
    messages,
    messagesMediaSignature,
    selectedHistoryMsgId,
  ]);

  const canvasDisplayAttachments = useMemo(() => {
    if (selectedCanvasMessage) {
      return (selectedCanvasMessage.attachments || []).filter((att) => {
        const stableUrl = getStableCanvasUrlFromAttachment(att);
        return Boolean(stableUrl);
      });
    }
    if (activeAttachments.length > 0) {
      return activeAttachments;
    }
    return [];
  }, [
    activeAttachments,
    getStableCanvasUrlFromAttachment,
    messagesMediaSignature,
    selectedCanvasMessage?.attachments,
  ]);

  const canvasCarouselResetKey = useMemo(() => {
    if (selectedCanvasMessage) {
      return selectedCanvasMessage.id;
    }
    if (activeAttachments.length > 0) {
      return activeAttachments
        .map((att) => att.id || getPreferredImageAttachmentUrl(att) || att.name)
        .join('|');
    }
    return null;
  }, [activeAttachments, selectedCanvasMessage?.id]);

  const {
    index: carouselIndex,
    goPrev: handleCarouselPrev,
    goNext: handleCarouselNext,
    select: handleCarouselSelect,
  } = useImageCarousel({
    itemCount: canvasDisplayAttachments.length,
    initialIndex: carouselInitialIndex,
    resetKey: canvasCarouselResetKey,
    keyboardEnabled: true,
    onNavigate: canvas.resetView,
  });

  useEffect(() => {
    const currentAttachment = canvasDisplayAttachments[carouselIndex];
    if (!currentAttachment) return;

    const currentUrl =
      getStableCanvasUrlFromAttachment(currentAttachment) ||
      currentAttachment.url ||
      currentAttachment.tempUrl;
    if (!currentUrl) return;

    if (currentUrl !== activeImageUrl) {
      setActiveImageUrl(currentUrl);
    }
    if (activeCanvasAttachment?.id !== currentAttachment.id) {
      setActiveCanvasAttachment(currentAttachment);
    }
  }, [
    activeCanvasAttachment?.id,
    activeImageUrl,
    canvasDisplayAttachments,
    carouselIndex,
    getStableCanvasUrlFromAttachment,
    messagesMediaSignature,
  ]);

  // Reset View when image changes
  useEffect(() => {
    canvas.resetView();
    setIsCompareMode(false);
  }, [activeImageUrl]);

  // Blob URL 生命周期由 useStableAttachmentImageUrl 统一管理。

  // 获取当前 AI 结果对应的用户上传原图（用于对比）
  const compareSourceImageUrl = useMemo(() => {
    if (
      !selectedCanvasMessage ||
      selectedCanvasMessage.role !== Role.MODEL ||
      canvasDisplayAttachments.length === 0
    ) {
      return null;
    }

    const selectedMessageIndex = messages.findIndex((msg) => msg.id === selectedCanvasMessage.id);
    if (selectedMessageIndex <= 0) {
      return null;
    }

    for (let i = selectedMessageIndex - 1; i >= 0; i -= 1) {
      const candidate = messages[i];
      if (candidate.role !== Role.USER || !candidate.attachments?.length) {
        continue;
      }

      for (const attachment of candidate.attachments) {
        const sourceUrl = getStableCanvasUrlFromAttachment(attachment);
        if (sourceUrl) {
          return sourceUrl;
        }
      }
    }

    return null;
  }, [
    canvasDisplayAttachments.length,
    getStableCanvasUrlFromAttachment,
    messages,
    messagesMediaSignature,
    selectedCanvasMessage,
  ]);

  // Sync initial attachments
  useEffect(() => {
    if (initialAttachments && initialAttachments.length > 0) {
      setActiveAttachments(initialAttachments);
      setCarouselInitialIndex(0);
      setActiveImageUrl(getStableCanvasUrlFromAttachment(initialAttachments[0]));
      // ✅ 同时保存完整的附件对象（包含元数据）
      setActiveCanvasAttachment(initialAttachments[0]);
    } else if (initialAttachments === undefined && activeAttachments.length === 0) {
      // 如果 initialAttachments 被清空（undefined），且当前没有附件，保持空状态
      // 但如果已经有附件（例如从消息中恢复），不要清空
    }
  }, [initialAttachments, getStableCanvasUrlFromAttachment]);

  // Sync uploaded attachment to main view
  // ✅ 与原始代码一致：只在有附件时设置画布图片，不清空画布
  // 原因：发送后附件预览会被清空，但画布应继续显示用户上传的图片，直到 AI 返回结果
  useEffect(() => {
    if (activeAttachments.length > 0) {
      const stableUrl = getStableCanvasUrlFromAttachment(activeAttachments[0]);
      setCarouselInitialIndex(0);
      setActiveImageUrl(stableUrl);
      // ✅ 同时保存完整的附件对象（包含元数据）
      setActiveCanvasAttachment(activeAttachments[0]);
    }
  }, [activeAttachments, getStableCanvasUrlFromAttachment]);

  // Auto-select latest result logic
  useEffect(() => {
    // 1. Initial Load: If no active image, pick latest from history
    // 优先从用户消息中获取（原始图片），如果没有则从模型消息中获取（编辑后的图片）
    if (activeAttachments.length === 0 && !activeImageUrl) {
      // 优先查找用户消息中的图片（对话式编辑的原始图片）
      const lastUserMsg = [...messages]
        .reverse()
        .find((m) => m.role === Role.USER && m.attachments?.length);
      const lastUserAttachment = lastUserMsg?.attachments?.[0];
      const lastUserUrl = lastUserAttachment
        ? getStableCanvasUrlFromAttachment(lastUserAttachment)
        : null;
      if (lastUserAttachment && lastUserUrl) {
        setCarouselInitialIndex(0);
        setActiveImageUrl(lastUserUrl);
        // ✅ 同时保存完整的附件对象（包含元数据）
        setActiveCanvasAttachment(lastUserAttachment);
      } else {
        // 如果没有用户消息，从模型消息中获取（编辑后的图片）
        const lastModelMsg = [...messages]
          .reverse()
          .find((m) => m.role === Role.MODEL && m.attachments?.length);
        const lastModelAttachment = lastModelMsg?.attachments?.[0];
        const lastModelUrl = lastModelAttachment
          ? getStableCanvasUrlFromAttachment(lastModelAttachment)
          : null;
        if (lastModelAttachment && lastModelUrl) {
          setCarouselInitialIndex(0);
          setActiveImageUrl(lastModelUrl);
          // ✅ 同时保存完整的附件对象（包含元数据）
          setActiveCanvasAttachment(lastModelAttachment);
        }
      }
    }
  }, [
    messages,
    messagesMediaSignature,
    activeAttachments.length,
    activeImageUrl,
    getStableCanvasUrlFromAttachment,
  ]);

  // 注意：handleGenerate 和 handleKeyDown 现在由 ChatEditInputArea 管理

  // ✅ ChatEditInputArea 已经处理了附件和参数，这里只需要直接转发
  const handleSend = useCallback(
    (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
      // ChatEditInputArea 已经处理了所有逻辑，直接转发即可
      onSend(text, options, attachments, editMode);
    },
    [onSend, editMode]
  );

  // Canvas 事件处理器现在由 useImageCanvas Hook 提供

  // Mobile History Toggle
  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

  const getHistoryAttachmentUrl = useCallback(
    (attachment: Attachment) => {
      return getStableCanvasUrlFromAttachment(attachment);
    },
    [getStableCanvasUrlFromAttachment]
  );

  const getMessageDisplayAttachments = useCallback(
    (attachments?: Attachment[]) => {
      return (attachments || []).filter((attachment) =>
        Boolean(getHistoryAttachmentUrl(attachment))
      );
    },
    [getHistoryAttachmentUrl]
  );

  const resolveHistoryCanvasUrl = useCallback(
    (sourceAttachment: Attachment | null | undefined, previewUrl: string | null | undefined) => {
      const stableUrl = sourceAttachment
        ? getStableCanvasUrlFromAttachment(sourceAttachment)
        : null;
      if (stableUrl) return stableUrl;

      const normalizedPreviewUrl = (previewUrl || '').trim();
      if (normalizedPreviewUrl && !isTemporaryAttachmentUrl(normalizedPreviewUrl)) {
        return normalizedPreviewUrl;
      }
      return null;
    },
    [getStableCanvasUrlFromAttachment]
  );

  const handleSelectGeneratedResult = useCallback(
    ({
      message,
      firstAttachment,
      firstUrl,
    }: {
      message: Message;
      firstAttachment: Attachment;
      firstUrl: string;
    }) => {
      setSelectedHistoryMsgId(message.id);
      setCarouselInitialIndex(0);
      handleCarouselSelect(0);
      setActiveImageUrl(firstUrl);
      setActiveCanvasAttachment(firstAttachment);
    },
    [handleCarouselSelect]
  );

  useAutoSelectGeneratedImageResult({
    messages,
    loadingState,
    getDisplayAttachments: getMessageDisplayAttachments,
    getAttachmentUrl: getHistoryAttachmentUrl,
    onSelectResult: handleSelectGeneratedResult,
  });

  const historyMessages = useMemo(() => {
    return messages.filter((msg) => {
      const isPlaceholder =
        !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
      return !isPlaceholder;
    });
    // 仅依赖 messages:memo 体未读取 messagesMediaSignature,带上它只会在签名变化时
    // 做无意义重算(过滤结果不变)。
  }, [messages]);

  const loadingHistoryContent = useMemo(() => {
    if (loadingState === 'idle') return null;

    let statusText = 'Processing request...';
    let statusIcon = <Bot size={16} className="text-slate-500" />;

    if (loadingState === 'uploading') {
      statusText = '上传图片中...';
      statusIcon = <Layers size={16} className="text-blue-400" />;
    } else if (loadingState === 'loading') {
      statusText = '对话式编辑中，AI 正在理解您的需求并生成图片...';
      statusIcon = <MessageSquare size={16} className="text-pink-400" />;
    } else if (loadingState === 'streaming') {
      statusText = '流式处理中...';
      statusIcon = <Sparkles size={16} className="text-pink-400 animate-pulse" />;
    }

    const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
    const thoughts = lastMessage?.thoughts || [];
    const textResponse = lastMessage?.textResponse;
    const hasTextContent = lastMessage?.content && lastMessage.content.trim().length > 0;
    const isThinkingComplete = loadingState === 'idle';

    return (
      <div className="rounded-xl border border-slate-700/50 bg-slate-900/60 p-3">
        <div className="flex items-start gap-2">
          <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0">
            {statusIcon}
          </div>
          <div className="rounded-xl text-xs text-slate-400 flex-1">
            <div className={`font-medium mb-1 ${loadingState !== 'idle' ? 'animate-pulse' : ''}`}>
              {statusText}
            </div>

            {displayedThinkingContent && (
              <div className="mt-2">
                <ThinkingBlock
                  content={displayedThinkingContent}
                  isOpen={isThinkingOpen}
                  onToggle={() => setIsThinkingOpen(!isThinkingOpen)}
                  isComplete={isThinkingComplete}
                />
              </div>
            )}

            {hasTextContent && !thoughts.length && !textResponse && (
              <div className="mt-2 pt-2 border-t border-slate-700/50 text-slate-500 italic">
                {lastMessage.content.substring(0, 100)}
                {lastMessage.content.length > 100 ? '...' : ''}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }, [displayedThinkingContent, isThinkingOpen, loadingState, messages]);

  const { sidebarExtraHeader, sidebarContent } = useImageHistorySidebar({
    items: historyMessages,
    sessionId: currentSessionId,
    onDeleteMessage,
    activeImageUrl,
    selectedMessageId: selectedHistoryMsgId,
    onSelectedMessageIdChange: setSelectedHistoryMsgId,
    disableFallbackSelection: activeAttachments.length > 0 || loadingState !== 'idle',
    onMobileHistoryOpenChange: setIsMobileHistoryOpen,
    modelLabel: activeModelConfig?.name || 'AI',
    accent: 'pink',
    emptyText: 'No edit history yet.',
    getDisplayAttachments: getMessageDisplayAttachments,
    getAttachmentUrl: getHistoryAttachmentUrl,
    extractPrompts: extractImageHistoryPrompts,
    loadingContent: loadingHistoryContent,
    onSelectItem: ({ message, firstImage, firstImageSourceAttachment }) => {
      setSelectedHistoryMsgId(message.id);
      setCarouselInitialIndex(0);
      handleCarouselSelect(0);
      const nextUrl = resolveHistoryCanvasUrl(firstImageSourceAttachment, firstImage);
      if (nextUrl) {
        setActiveImageUrl(nextUrl);
        if (firstImageSourceAttachment) {
          setActiveCanvasAttachment(firstImageSourceAttachment);
        }
      }
    },
    onSelectPreviewAttachment: ({ message, attachment, sourceAttachment, displayUrl, index }) => {
      setSelectedHistoryMsgId(message.id);
      setCarouselInitialIndex(index);
      handleCarouselSelect(index);
      const nextUrl = resolveHistoryCanvasUrl(sourceAttachment, displayUrl || attachment.url);
      if (nextUrl) {
        setActiveImageUrl(nextUrl);
        if (sourceAttachment) {
          setActiveCanvasAttachment(sourceAttachment);
        }
      }
    },
  });

  const toggleCompare = useCallback(() => setIsCompareMode((prev) => !prev), []);
  const handleFullscreen = useCallback(() => {
    if (activeImageUrl) onImageClick(activeImageUrl);
  }, [activeImageUrl, onImageClick]);
  const handleExpand = useCallback(() => {
    if (activeImageUrl && onExpandImage) onExpandImage(activeImageUrl);
  }, [activeImageUrl, onExpandImage]);
  const canCompareWithSource = Boolean(
    compareSourceImageUrl &&
    activeImageUrl &&
    compareSourceImageUrl !== activeImageUrl &&
    selectedCanvasMessage?.role === Role.MODEL
  );

  // ✅ 主区域：两栏布局（画布 + 参数面板）
  const mainContent = useMemo(
    () => (
      <div className="flex-1 flex flex-row h-full">
        {/* ========== 左侧：画布区域 ========== */}
        <ImageEditMainCanvas
          loadingState={loadingState}
          isCompareMode={isCompareMode}
          activeAttachments={canvasDisplayAttachments}
          activeImageUrl={activeImageUrl}
          originalImageUrl={compareSourceImageUrl}
          zoom={canvas.zoom}
          isDragging={canvas.isDragging}
          canvasStyle={canvas.canvasStyle}
          onWheel={canvas.handleWheel}
          onMouseDown={canvas.handleMouseDown}
          onMouseMove={canvas.handleMouseMove}
          onMouseUp={canvas.handleMouseUp}
          onZoomIn={canvas.handleZoomIn}
          onZoomOut={canvas.handleZoomOut}
          onReset={canvas.handleReset}
          onFullscreen={activeImageUrl ? handleFullscreen : undefined}
          onExpand={onExpandImage && activeImageUrl ? handleExpand : undefined}
          onToggleCompare={canCompareWithSource ? toggleCompare : undefined}
          // ✅ 旋转木马支持
          carouselIndex={carouselIndex}
          onCarouselPrev={handleCarouselPrev}
          onCarouselNext={handleCarouselNext}
          onCarouselSelect={handleCarouselSelect}
          getStableUrl={getStableCanvasUrlFromAttachment}
        />

        {/* ========== 右侧：参数面板 ========== */}
        <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
          {/* 编辑参数头部 */}
          <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={14} className="text-pink-400" />
              <span className="text-xs font-bold text-white">编辑参数</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={resetParams}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                title="重置为默认值"
              >
                <RotateCcw size={12} />
              </button>
            </div>
          </div>

          {/* 参数滚动区 */}
          <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
            {/* 编辑参数面板（始终显示） */}
            <ModeControlsCoordinator
              mode={editMode}
              providerId={providerId || 'google'}
              currentModel={activeModelConfig}
              controls={controls}
              availableModels={allVisibleModels}
            />
          </div>

          {/* 底部固定区：使用 ChatEditInputArea 组件（始终显示） */}
          <ChatEditInputArea
            onSend={handleSend}
            isLoading={loadingState !== 'idle'}
            onStop={onStop}
            mode={editMode}
            activeAttachments={activeAttachments}
            onAttachmentsChange={handleAttachmentsChange}
            activeImageUrl={activeImageUrl}
            onActiveImageUrlChange={setActiveImageUrl}
            activeCanvasAttachment={activeCanvasAttachment}
            messages={messages}
            sessionId={currentSessionId ?? null}
            initialPrompt={initialPrompt}
            initialAttachments={initialAttachments}
            providerId={providerId}
            currentModel={activeModelConfig}
            controls={controls}
          />
        </div>
      </div>
    ),
    [
      loadingState,
      isCompareMode,
      activeAttachments,
      canvasDisplayAttachments,
      activeImageUrl,
      activeCanvasAttachment,
      compareSourceImageUrl,
      canCompareWithSource,
      canvas,
      handleFullscreen,
      handleExpand,
      toggleCompare,
      onExpandImage,
      handleSend,
      editMode,
      onStop,
      messages,
      currentSessionId,
      initialPrompt,
      initialAttachments,
      providerId,
      activeModelConfig,
      allVisibleModels,
      resetParams,
      carouselIndex,
      handleCarouselPrev,
      handleCarouselNext,
      handleCarouselSelect,
      getStableCanvasUrlFromAttachment,
      controls,
    ]
  );

  return (
    <GenViewLayout
      isMobileHistoryOpen={isMobileHistoryOpen}
      setIsMobileHistoryOpen={setIsMobileHistoryOpen}
      sidebarTitle="History"
      sidebarHeaderIcon={<Layers size={14} />}
      sidebarExtraHeader={sidebarExtraHeader}
      sidebar={sidebarContent}
      main={mainContent}
    />
  );
};
