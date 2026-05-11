import React, { useState, useRef, useEffect, useMemo, useCallback, memo } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Sparkles, Layers, Bot, SlidersHorizontal, RotateCcw } from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import {
  ImageCarouselArrows,
  ImageCarouselThumbnails,
  type CarouselMediaItem,
} from '../common/ImageCarouselControls';
import { ImageCompare } from '../common/ImageCompare';
import { GenViewLayout } from '../common/GenViewLayout';
import { ThinkingBlock } from '../message/ThinkingBlock';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { useImageCarousel } from '../../hooks/useImageCarousel';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../chat/ChatEditInputArea';
import { useThinkingBlock } from '../../hooks/useThinkingBlock';
import { extractImageHistoryPrompts, useImageHistorySidebar } from '../common/ImageHistorySidebar';

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

// 复用 ImageEditView 的比较函数
const arePropsEqual = (prevProps: ImageRecontextViewProps, nextProps: ImageRecontextViewProps) => {
  if (prevProps.activeModelConfig?.id !== nextProps.activeModelConfig?.id) {
    return false;
  }
  if (prevProps.loadingState !== nextProps.loadingState) return false;
  if (prevProps.messages !== nextProps.messages) return false;
  if (prevProps.sessionId !== nextProps.sessionId) return false;
  if (prevProps.providerId !== nextProps.providerId) return false;
  return true;
};

// 复用 ImageEditMainCanvas 组件（从 ImageEditView 导入或复制）
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

const ImageEditMainCanvas = memo(
  ({
    loadingState,
    isCompareMode,
    activeAttachments,
    activeImageUrl,
    originalImageUrl,
    zoom,
    isDragging,
    canvasStyle,
    onWheel,
    onMouseDown,
    onMouseMove,
    onMouseUp,
    onZoomIn,
    onZoomOut,
    onReset,
    onFullscreen,
    onExpand,
    onToggleCompare,
    carouselIndex,
    onCarouselPrev,
    onCarouselNext,
    onCarouselSelect,
    getStableUrl,
  }: ImageEditMainCanvasProps) => {
    const cursor = isCompareMode
      ? 'default'
      : isDragging
        ? 'grabbing'
        : activeImageUrl
          ? 'grab'
          : 'default';
    const isMultiImageMode = activeAttachments.length > 1;
    const currentDisplayUrl =
      isMultiImageMode && activeAttachments[carouselIndex]
        ? activeAttachments[carouselIndex].url ||
          activeAttachments[carouselIndex].tempUrl ||
          getStableUrl(activeAttachments[carouselIndex])
        : activeImageUrl;
    const carouselItems = useMemo<CarouselMediaItem[]>(
      () =>
        activeAttachments.map((att, idx) => {
          const thumbUrl = att.url || att.tempUrl || getStableUrl(att);
          return {
            id: att.id || `${idx}`,
            url: thumbUrl,
            thumbUrl,
            alt: `重上下文结果 ${idx + 1}`,
          };
        }),
      [activeAttachments, getStableUrl]
    );

    return (
      <div
        className="flex-1 w-full h-full select-none flex flex-col relative"
        onWheel={isCompareMode ? undefined : onWheel}
        onMouseDown={isCompareMode ? undefined : onMouseDown}
        onMouseMove={isCompareMode ? undefined : onMouseMove}
        onMouseUp={isCompareMode ? undefined : onMouseUp}
        onMouseLeave={isCompareMode ? undefined : onMouseUp}
        style={{ cursor }}
      >
        {/* Checkerboard Background */}
        <div
          className="absolute inset-0 opacity-20 pointer-events-none"
          style={{
            backgroundImage: `
                               linear-gradient(45deg, #334155 25%, transparent 25%), 
                               linear-gradient(-45deg, #334155 25%, transparent 25%), 
                               linear-gradient(45deg, transparent 75%, #334155 75%), 
                               linear-gradient(-45deg, transparent 75%, #334155 75%)
                           `,
            backgroundSize: '20px 20px',
            backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
          }}
        />

        {/* Canvas Header */}
        <div className="absolute top-4 left-4 z-10 pointer-events-none">
          <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-lg">
            <Sparkles size={12} className="text-yellow-400" />
            {isCompareMode
              ? '对比模式'
              : isMultiImageMode
                ? `重上下文结果 (${carouselIndex + 1}/${activeAttachments.length})`
                : activeAttachments.length > 0 && activeImageUrl === activeAttachments[0].url
                  ? 'Source Preview'
                  : 'Recontext Editor'}
            <span className="opacity-50">|</span>
            <span className="font-mono text-[10px] opacity-70">{Math.round(zoom * 100)}%</span>
          </div>
        </div>

        {/* Main Image Display */}
        <div className="flex-1 flex items-center justify-center p-0 w-full h-full">
          {loadingState !== 'idle' ? (
            (() => {
              let statusText = 'Processing Image...';
              if (loadingState === 'uploading') {
                statusText = '上传图片中...';
              } else if (loadingState === 'loading') {
                statusText = '重新上下文处理中，正在调整图片上下文...';
              } else if (loadingState === 'streaming') {
                statusText = '流式处理中...';
              }

              return (
                <div className="flex flex-col items-center gap-4 pointer-events-none">
                  <div className="relative">
                    <div className="w-20 h-20 border-4 border-yellow-500/30 border-t-yellow-500 rounded-full animate-spin"></div>
                  </div>
                  <p className="text-slate-400 animate-pulse">{statusText}</p>
                </div>
              );
            })()
          ) : isCompareMode && originalImageUrl && currentDisplayUrl ? (
            <div
              className="relative shadow-2xl transition-transform duration-75 ease-out"
              style={canvasStyle}
            >
              <ImageCompare
                beforeImage={originalImageUrl}
                afterImage={currentDisplayUrl}
                beforeLabel="原图"
                afterLabel="重上下文结果"
                accentColor="orange"
                className="max-w-none rounded-lg border border-slate-800"
                style={{ maxHeight: '80vh', maxWidth: '80vw' }}
              />
            </div>
          ) : currentDisplayUrl ? (
            <>
              <ImageCarouselArrows
                itemCount={activeAttachments.length}
                onPrev={onCarouselPrev}
                onNext={onCarouselNext}
              />
              <div
                className="relative shadow-2xl group transition-transform duration-75 ease-out"
                style={canvasStyle}
              >
                <img
                  src={currentDisplayUrl}
                  className="max-w-none rounded-lg border border-slate-800 pointer-events-none"
                  style={{ maxHeight: '70vh', maxWidth: '70vw' }}
                  alt="Main Canvas"
                />
              </div>
            </>
          ) : (
            <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
              <Sparkles size={48} className="opacity-20" />
              <div>
                <h3 className="text-xl font-bold text-slate-500 mb-2">Recontext Editor</h3>
                <p className="text-sm opacity-60">上传图片并调整其上下文环境</p>
              </div>
            </div>
          )}
        </div>

        {isMultiImageMode && loadingState === 'idle' && (
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 bg-slate-950/85 backdrop-blur-xl border border-slate-800 rounded-2xl shadow-2xl">
            <ImageCarouselThumbnails
              items={carouselItems}
              currentIndex={carouselIndex}
              onSelect={onCarouselSelect}
              accentTone="orange"
              thumbnailSize={52}
              panelClassName="flex items-center gap-2 py-2 px-3"
              counterClassName="ml-1 text-xs text-slate-400 font-mono"
            />
          </div>
        )}

        {/* Floating Controls */}
        {currentDisplayUrl && (
          <div className="absolute bottom-6 right-6 z-20">
            <ImageCanvasControls
              zoom={zoom}
              onZoomIn={onZoomIn}
              onZoomOut={onZoomOut}
              onReset={onReset}
              onFullscreen={onFullscreen}
              downloadUrl={currentDisplayUrl}
              onExpand={onExpand}
              onToggleCompare={onToggleCompare}
              isCompareMode={isCompareMode}
              accentColor="orange"
            />
          </div>
        )}
      </div>
    );
  }
);

ImageEditMainCanvas.displayName = 'ImageEditMainCanvas';

export const ImageRecontextView = memo(
  ({
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
  }: ImageRecontextViewProps) => {
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

    // Stable canvas URL
    const canvasObjectUrlRef = useRef<string | null>(null);
    const canvasObjectUrlFileRef = useRef<File | null>(null);

    const getStableCanvasUrlFromAttachment = useCallback((att: Attachment) => {
      if (att.file) {
        const file = att.file;
        if (!canvasObjectUrlRef.current || canvasObjectUrlFileRef.current !== file) {
          if (canvasObjectUrlRef.current) URL.revokeObjectURL(canvasObjectUrlRef.current);
          canvasObjectUrlRef.current = URL.createObjectURL(file);
          canvasObjectUrlFileRef.current = file;
        }
        return canvasObjectUrlRef.current;
      }
      return att.url || att.tempUrl || null;
    }, []);

    useEffect(() => {
      return () => {
        if (canvasObjectUrlRef.current) {
          URL.revokeObjectURL(canvasObjectUrlRef.current);
          canvasObjectUrlRef.current = null;
          canvasObjectUrlFileRef.current = null;
        }
      };
    }, []);

    const [lastProcessedMsgId, setLastProcessedMsgId] = useState<string | null>(null);
    const [isCompareMode, setIsCompareMode] = useState(false);
    const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });
    const getDisplayableImageAttachments = useCallback((attachments?: Attachment[]) => {
      return (attachments ?? []).filter((att) => Boolean(att.url || att.tempUrl || att.file));
    }, []);

    const historyMessages = useMemo(() => {
      return messages.filter((msg) => {
        const isPlaceholder =
          !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
        return !isPlaceholder;
      });
    }, [messages]);

    const canvasCarouselResetKey = useMemo(
      () => canvasAttachments.map((att) => att.id || att.url || att.tempUrl || att.name).join('|'),
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
        currentAttachment.url ||
        currentAttachment.tempUrl ||
        getStableCanvasUrlFromAttachment(currentAttachment);
      if (currentUrl && currentUrl !== activeImageUrl) {
        setActiveImageUrl(currentUrl);
      }
    }, [activeImageUrl, canvasAttachments, carouselIndex, getStableCanvasUrlFromAttachment]);

    useEffect(() => {
      canvas.resetView();
      setIsCompareMode(false);
    }, [activeImageUrl]);

    useEffect(() => {
      if (canvasObjectUrlRef.current && activeImageUrl !== canvasObjectUrlRef.current) {
        URL.revokeObjectURL(canvasObjectUrlRef.current);
        canvasObjectUrlRef.current = null;
        canvasObjectUrlFileRef.current = null;
      }
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
              sourceAttachment.url ||
              sourceAttachment.tempUrl ||
              getStableCanvasUrlFromAttachment(sourceAttachment)
            );
          }
        }
      }

      const lastUserMsg = [...messages]
        .reverse()
        .find((m) => m.role === Role.USER && m.attachments?.length);
      const sourceAttachment = getDisplayableImageAttachments(lastUserMsg?.attachments)[0];
      return sourceAttachment
        ? sourceAttachment.url ||
            sourceAttachment.tempUrl ||
            getStableCanvasUrlFromAttachment(sourceAttachment)
        : null;
    }, [
      getDisplayableImageAttachments,
      getStableCanvasUrlFromAttachment,
      messages,
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

      if (loadingState === 'idle' && messages.length > 0) {
        const lastMsg = messages[messages.length - 1];
        if (lastMsg.id !== lastProcessedMsgId) {
          const displayAttachments = getDisplayableImageAttachments(lastMsg.attachments);
          if (lastMsg.role === Role.MODEL && displayAttachments.length > 0) {
            setCarouselInitialIndex(0);
            setCanvasAttachments(displayAttachments);
            setActiveImageUrl(getStableCanvasUrlFromAttachment(displayAttachments[0]));
            setLastProcessedMsgId(lastMsg.id);
          } else if (lastMsg.isError) {
            setLastProcessedMsgId(lastMsg.id);
          }
        }
      }
    }, [
      messages,
      activeAttachments.length,
      loadingState,
      lastProcessedMsgId,
      activeImageUrl,
      getDisplayableImageAttachments,
      getStableCanvasUrlFromAttachment,
    ]);

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
      onSelectItem: ({ message, displayAttachments, firstImage }) => {
        setSelectedHistoryMsgId(message.id);
        if (firstImage) {
          setCarouselInitialIndex(0);
          setCanvasAttachments(displayAttachments);
          handleCarouselSelect(0);
          setActiveImageUrl(firstImage);
        }
      },
      onSelectPreviewAttachment: ({ message, displayAttachments, attachment, index }) => {
        setSelectedHistoryMsgId(message.id);
        setCarouselInitialIndex(index);
        setCanvasAttachments(displayAttachments);
        handleCarouselSelect(index);
        setActiveImageUrl(attachment.url);
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
  },
  arePropsEqual
);
