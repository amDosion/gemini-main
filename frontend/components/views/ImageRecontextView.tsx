import React, { useState, useEffect, useMemo, useCallback, memo } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Sparkles, Layers, Bot, SlidersHorizontal, RotateCcw } from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageCarouselThumbnails } from '../common/ImageCarouselControls';
import { ImageWorkspaceCanvas } from '../common/ImageWorkspaceCanvas';
import { GenViewLayout } from '../common/GenViewLayout';
import { ThinkingBlock } from '../message/ThinkingBlock';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { useImageCarousel } from '../../hooks/useImageCarousel';
import { useAutoSelectGeneratedImageResult } from '../../hooks/useAutoSelectGeneratedImageResult';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../chat/ChatEditInputArea';
import { useThinkingBlock } from '../../hooks/useThinkingBlock';
import { extractImageHistoryPrompts, useImageHistorySidebar } from '../common/ImageHistorySidebar';
import { getPreferredImageAttachmentUrl, isTemporaryAttachmentUrl } from '../../utils/attachmentUrl';
import { useStableAttachmentImageUrl } from '../../hooks/useStableAttachmentImageUrl';
import { buildMessagesMediaSignature } from '../../utils/messageMediaSignature';

interface ImageRecontextViewProps {
  messages: Message[];
  setAppMode: (mode: AppMode) => void;
  onImageClick: (url: string) => void;
  loadingState: string;
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  onStop: () => void;
  activeModelConfig?: ModelConfig;
  visibleModels?: ModelConfig[];
  allVisibleModels?: ModelConfig[]; // 新增：完整模型列表
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  onExpandImage?: (url: string) => void;
  providerId?: string;
  sessionId?: string | null;
  onDeleteMessage?: (messageId: string) => void;
}

// 复用共享的 ImageWorkspaceCanvas（components/common/ImageWorkspaceCanvas.tsx）
type ImageEditMainCanvasProps = {
  loadingState: string;
  isCompareMode: boolean;
  activeAttachments: Attachment[];
  activeImageUrl: string | null;
  originalImageUrl: string | null;
  zoom: number;
  isDragging: boolean;
  canvasStyle: React.CSSProperties;
  onWheel: (e: React.WheelEvent) => void;
  onMouseDown: (e: React.MouseEvent) => void;
  onMouseMove: (e: React.MouseEvent) => void;
  onMouseUp: () => void;
  onZoomIn: (e?: React.MouseEvent) => void;
  onZoomOut: (e?: React.MouseEvent) => void;
  onReset: (e?: React.MouseEvent) => void;
  onFullscreen?: () => void;
  onExpand?: () => void;
  onToggleCompare?: () => void;
  carouselIndex: number;
  onCarouselPrev: () => void;
  onCarouselNext: () => void;
  onCarouselSelect: (index: number) => void;
  getStableUrl: (att: Attachment) => string | null;
};

const RECONTEXT_EMPTY_STATE = (
  <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
    <Sparkles size={48} className="opacity-20" />
    <div>
      <h3 className="text-xl font-bold text-slate-500 mb-2">Recontext Editor</h3>
      <p className="text-sm opacity-60">上传图片并调整其上下文环境</p>
    </div>
  </div>
);

const ImageEditMainCanvas = memo(
  ({
    carouselIndex,
    onCarouselPrev,
    onCarouselNext,
    onCarouselSelect,
    getStableUrl,
    ...rest
  }: ImageEditMainCanvasProps) => (
    <ImageWorkspaceCanvas
      {...rest}
      headerIcon={Sparkles}
      headerIconClassName="text-yellow-400"
      headerLabel="Recontext Editor"
      multiImageLabelPrefix="重上下文结果"
      spinnerClassName="border-yellow-500/30 border-t-yellow-500"
      loadingText={{
        default: 'Processing Image...',
        uploading: '上传图片中...',
        loading: '重新上下文处理中，正在调整图片上下文...',
        streaming: '流式处理中...',
      }}
      compareConfig={{
        beforeLabel: '原图',
        afterLabel: '重上下文结果',
        accentColor: 'orange',
      }}
      controlsAccentColor="orange"
      carousel={{
        carouselIndex,
        onCarouselPrev,
        onCarouselNext,
        onCarouselSelect,
        getStableUrl,
        altFor: (idx) => `重上下文结果 ${idx + 1}`,
        renderThumbnails: ({ items, currentIndex, onSelect }) => (
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 bg-slate-950/85 backdrop-blur-xl border border-slate-800 rounded-2xl shadow-2xl">
            <ImageCarouselThumbnails
              items={items}
              currentIndex={currentIndex}
              onSelect={onSelect}
              accentTone="orange"
              thumbnailSize={52}
              panelClassName="flex items-center gap-2 py-2 px-3"
              counterClassName="ml-1 text-xs text-slate-400 font-mono"
            />
          </div>
        ),
      }}
      emptyState={RECONTEXT_EMPTY_STATE}
    />
  )
);

ImageEditMainCanvas.displayName = 'ImageEditMainCanvas';

export const ImageRecontextView: React.FC<ImageRecontextViewProps> = ({
    messages,
    setAppMode,
    onImageClick,
    loadingState,
    onSend,
    onStop,
    activeModelConfig,
    visibleModels = [],
    allVisibleModels = [],
    initialPrompt,
    initialAttachments,
    onExpandImage,
    providerId,
    sessionId: currentSessionId,
    onDeleteMessage,
  }) => {
    const { showError } = useToastContext();
    const [selectedHistoryMsgId, setSelectedHistoryMsgId] = useState<string | null>(null);

    // State for reference image
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
    const [canvasAttachments, setCanvasAttachments] = useState<Attachment[]>([]);
    const [carouselInitialIndex, setCarouselInitialIndex] = useState(0);
    const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);

    // 固定使用 image-recontext 模式
    const editMode: AppMode = 'image-recontext';

    // ✅ 参数面板状态
    const controls = useControlsState(editMode, activeModelConfig);

    // 重置参数
    const resetParams = useCallback(() => {
      controls.setAspectRatio('1:1');
      controls.setResolution('1K');
      controls.setNegativePrompt('');
      controls.setSeed(-1);
    }, [controls]);

    // State for thinking block
    const {
      isOpen: isThinkingOpen,
      setIsOpen: setIsThinkingOpen,
      displayedContent: displayedThinkingContent,
    } = useThinkingBlock(messages, loadingState);
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

    const getStableCanvasUrlFromAttachment = useStableAttachmentImageUrl([], {
      retainedObjectUrl: activeImageUrl,
      createFileObjectUrls: false,
    });
    const messagesMediaSignature = buildMessagesMediaSignature(messages);

    const [isCompareMode, setIsCompareMode] = useState(false);
    const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });
    const getDisplayableImageAttachments = useCallback((attachments?: Attachment[]) => {
      return (attachments ?? []).filter((att) =>
        Boolean(att.file || getPreferredImageAttachmentUrl(att))
      );
    }, []);

    const handleSelectGeneratedResult = useCallback(
      ({
        message,
        attachments,
        firstUrl,
      }: {
        message: Message;
        attachments: Attachment[];
        firstUrl: string;
      }) => {
        setSelectedHistoryMsgId(message.id);
        setCarouselInitialIndex(0);
        setCanvasAttachments(attachments);
        setActiveImageUrl(firstUrl);
      },
      []
    );

    const historyMessages = useMemo(() => {
      return messages.filter((msg) => {
        const isPlaceholder =
          !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
        return !isPlaceholder;
      });
    }, [messages, messagesMediaSignature]);

    const canvasCarouselResetKey = useMemo(
      () =>
        canvasAttachments
          .map((att) => att.id || getPreferredImageAttachmentUrl(att) || att.name)
          .join('|'),
      [canvasAttachments]
    );
    const {
      index: carouselIndex,
      goPrev: handleCarouselPrev,
      goNext: handleCarouselNext,
      select: handleCarouselSelect,
    } = useImageCarousel({
      itemCount: canvasAttachments.length,
      initialIndex: carouselInitialIndex,
      resetKey: canvasCarouselResetKey,
      keyboardEnabled: true,
      onNavigate: canvas.resetView,
    });

    useEffect(() => {
      const currentAttachment = canvasAttachments[carouselIndex];
      if (!currentAttachment) return;

      const currentUrl =
        getStableCanvasUrlFromAttachment(currentAttachment) ||
        currentAttachment.url ||
        currentAttachment.tempUrl;
      if (currentUrl && currentUrl !== activeImageUrl) {
        setActiveImageUrl(currentUrl);
      }
    }, [
      activeImageUrl,
      canvasAttachments,
      carouselIndex,
      getStableCanvasUrlFromAttachment,
      messagesMediaSignature,
    ]);

    useEffect(() => {
      canvas.resetView();
      setIsCompareMode(false);
    }, [activeImageUrl]);

    const originalImageUrl = useMemo(() => {
      if (selectedHistoryMsgId) {
        const selectedMessageIndex = messages.findIndex((msg) => msg.id === selectedHistoryMsgId);
        const selectedMessage = selectedMessageIndex >= 0 ? messages[selectedMessageIndex] : null;
        if (selectedMessage?.role === Role.MODEL) {
          for (let i = selectedMessageIndex - 1; i >= 0; i -= 1) {
            const candidate = messages[i];
            if (candidate.role !== Role.USER || !candidate.attachments?.length) {
              continue;
            }

            const sourceAttachment = getDisplayableImageAttachments(candidate.attachments)[0];
            if (!sourceAttachment) {
              continue;
            }
            return (
              getStableCanvasUrlFromAttachment(sourceAttachment) ||
              sourceAttachment.url ||
              sourceAttachment.tempUrl ||
              null
            );
          }
        }
      }

      const lastUserMsg = [...messages]
        .reverse()
        .find((m) => m.role === Role.USER && m.attachments?.length);
      const sourceAttachment = getDisplayableImageAttachments(lastUserMsg?.attachments)[0];
      return sourceAttachment
        ? getStableCanvasUrlFromAttachment(sourceAttachment) ||
            sourceAttachment.url ||
            sourceAttachment.tempUrl ||
            null
        : null;
    }, [
      getDisplayableImageAttachments,
      getStableCanvasUrlFromAttachment,
      messages,
      messagesMediaSignature,
      selectedHistoryMsgId,
    ]);

    useEffect(() => {
      if (initialAttachments && initialAttachments.length > 0) {
        const displayAttachments = getDisplayableImageAttachments(initialAttachments);
        setActiveAttachments(initialAttachments);
        setCarouselInitialIndex(0);
        setCanvasAttachments(displayAttachments);
        setActiveImageUrl(
          getStableCanvasUrlFromAttachment(displayAttachments[0] ?? initialAttachments[0])
        );
      }
    }, [initialAttachments, getDisplayableImageAttachments, getStableCanvasUrlFromAttachment]);

    useEffect(() => {
      if (activeAttachments.length > 0) {
        const displayAttachments = getDisplayableImageAttachments(activeAttachments);
        setCarouselInitialIndex(0);
        setCanvasAttachments(displayAttachments);
        setActiveImageUrl(
          getStableCanvasUrlFromAttachment(displayAttachments[0] ?? activeAttachments[0])
        );
      }
    }, [activeAttachments, getDisplayableImageAttachments, getStableCanvasUrlFromAttachment]);

    useEffect(() => {
      if (activeAttachments.length === 0 && !activeImageUrl) {
        const lastImageMsg = [...messages]
          .reverse()
          .find((m) => getDisplayableImageAttachments(m.attachments).length > 0);
        const displayAttachments = getDisplayableImageAttachments(lastImageMsg?.attachments);
        if (displayAttachments.length > 0) {
          setCarouselInitialIndex(0);
          setCanvasAttachments(displayAttachments);
          setActiveImageUrl(getStableCanvasUrlFromAttachment(displayAttachments[0]));
        }
      }
    }, [
      messages,
      messagesMediaSignature,
      activeAttachments.length,
      activeImageUrl,
      getDisplayableImageAttachments,
      getStableCanvasUrlFromAttachment,
    ]);

    useAutoSelectGeneratedImageResult({
      messages,
      loadingState,
      getDisplayAttachments: getDisplayableImageAttachments,
      getAttachmentUrl: getStableCanvasUrlFromAttachment,
      onSelectResult: handleSelectGeneratedResult,
    });

    const resolveHistoryCanvasUrl = useCallback(
      (sourceAttachment: Attachment | null | undefined, previewUrl: string | null | undefined) => {
        const stableUrl = sourceAttachment ? getStableCanvasUrlFromAttachment(sourceAttachment) : null;
        if (stableUrl) return stableUrl;

        const normalizedPreviewUrl = (previewUrl || '').trim();
        if (normalizedPreviewUrl && !isTemporaryAttachmentUrl(normalizedPreviewUrl)) {
          return normalizedPreviewUrl;
        }
        return null;
      },
      [getStableCanvasUrlFromAttachment]
    );

    // ✅ ChatEditInputArea 已经处理了附件和参数，这里只需要直接转发
    const handleSend = useCallback(
      (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
        onSend(text, options, attachments, editMode);
      },
      [onSend, editMode]
    );

    const loadingHistoryContent = useMemo(() => {
      if (loadingState === 'idle') return null;

      let statusText = 'Processing request...';
      let statusIcon = <Bot size={16} className="text-slate-500" />;

      if (loadingState === 'uploading') {
        statusText = '上传图片中...';
        statusIcon = <Layers size={16} className="text-blue-400" />;
      } else if (loadingState === 'loading') {
        statusText = '重新上下文处理中，正在调整图片上下文...';
        statusIcon = <Sparkles size={16} className="text-yellow-400" />;
      } else if (loadingState === 'streaming') {
        statusText = '流式处理中...';
        statusIcon = <Sparkles size={16} className="text-yellow-400 animate-pulse" />;
      }

      const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
      const thoughts = lastMessage?.thoughts || [];
      const textResponse = lastMessage?.textResponse;
      const hasTextContent = lastMessage?.content && lastMessage.content.trim().length > 0;

      return (
        <div className="flex items-start gap-2">
          <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0">
            {statusIcon}
          </div>
          <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400 flex-1">
            <div className="font-medium mb-1 animate-pulse">{statusText}</div>

            {displayedThinkingContent && (
              <div className="mt-2">
                <ThinkingBlock
                  content={displayedThinkingContent}
                  isOpen={isThinkingOpen}
                  onToggle={() => setIsThinkingOpen(!isThinkingOpen)}
                  isComplete={false}
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
      );
    }, [displayedThinkingContent, isThinkingOpen, loadingState, messages]);

    const { sidebarExtraHeader, sidebarContent } = useImageHistorySidebar({
      items: historyMessages,
      sessionId: currentSessionId,
      onDeleteMessage,
      activeImageUrl,
      selectedMessageId: selectedHistoryMsgId,
      onSelectedMessageIdChange: setSelectedHistoryMsgId,
      onMobileHistoryOpenChange: setIsMobileHistoryOpen,
      modelLabel: activeModelConfig?.name || 'AI',
      accent: 'orange',
      emptyText: 'No recontext history yet.',
      getDisplayAttachments: getDisplayableImageAttachments,
      getAttachmentUrl: getStableCanvasUrlFromAttachment,
      extractPrompts: extractImageHistoryPrompts,
      loadingContent: loadingHistoryContent,
      onSelectItem: ({ message, displayAttachments, firstImage, firstImageSourceAttachment }) => {
        setSelectedHistoryMsgId(message.id);
        const nextUrl = resolveHistoryCanvasUrl(firstImageSourceAttachment, firstImage);
        if (nextUrl) {
          setCarouselInitialIndex(0);
          setCanvasAttachments(displayAttachments);
          handleCarouselSelect(0);
          setActiveImageUrl(nextUrl);
        }
      },
      onSelectPreviewAttachment: ({
        message,
        displayAttachments,
        attachment,
        sourceAttachment,
        displayUrl,
        index,
      }) => {
        setSelectedHistoryMsgId(message.id);
        setCarouselInitialIndex(index);
        setCanvasAttachments(displayAttachments);
        handleCarouselSelect(index);
        const nextUrl = resolveHistoryCanvasUrl(sourceAttachment, displayUrl || attachment.url);
        if (nextUrl) {
          setActiveImageUrl(nextUrl);
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

    // ✅ 主区域：两栏布局（画布 + 参数面板）
    const mainContent = useMemo(
      () => (
        <div className="flex-1 flex flex-row h-full">
          {/* ========== 左侧：画布区域 ========== */}
          <ImageEditMainCanvas
            loadingState={loadingState}
            isCompareMode={isCompareMode}
            activeAttachments={canvasAttachments}
            activeImageUrl={activeImageUrl}
            originalImageUrl={originalImageUrl}
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
            onToggleCompare={originalImageUrl ? toggleCompare : undefined}
            carouselIndex={carouselIndex}
            onCarouselPrev={handleCarouselPrev}
            onCarouselNext={handleCarouselNext}
            onCarouselSelect={handleCarouselSelect}
            getStableUrl={getStableCanvasUrlFromAttachment}
          />

          {/* ========== 右侧：参数面板 ========== */}
          <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
            {/* 头部 */}
            <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <SlidersHorizontal size={14} className="text-yellow-400" />
                <span className="text-xs font-bold text-white">上下文参数</span>
              </div>
              <button
                onClick={resetParams}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                title="重置为默认值"
              >
                <RotateCcw size={12} />
              </button>
            </div>

            {/* 参数滚动区 */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
              <ModeControlsCoordinator
                mode={editMode}
                providerId={providerId || 'google'}
                controls={controls}
              />
            </div>

            {/* 底部固定区：使用 ChatEditInputArea 组件 */}
            <ChatEditInputArea
              onSend={handleSend}
              isLoading={loadingState !== 'idle'}
              onStop={onStop}
              mode={editMode}
              activeAttachments={activeAttachments}
              onAttachmentsChange={setActiveAttachments}
              activeImageUrl={activeImageUrl}
              onActiveImageUrlChange={setActiveImageUrl}
              messages={messages}
              sessionId={currentSessionId ?? null}
              initialPrompt={initialPrompt}
              initialAttachments={initialAttachments}
              providerId={providerId}
              controls={controls}
            />
          </div>
        </div>
      ),
      [
        loadingState,
        isCompareMode,
        canvasAttachments,
        activeAttachments,
        activeImageUrl,
        originalImageUrl,
        canvas,
        handleFullscreen,
        handleExpand,
        toggleCompare,
        onExpandImage,
        controls,
        providerId,
        resetParams,
        editMode,
        onStop,
        messages,
        currentSessionId,
        initialPrompt,
        initialAttachments,
        handleSend,
        carouselIndex,
        handleCarouselPrev,
        handleCarouselNext,
        handleCarouselSelect,
        getStableCanvasUrlFromAttachment,
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
