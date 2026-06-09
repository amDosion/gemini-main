import React, { useState, useRef, useEffect, useMemo, useCallback, memo } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import {
  Layers,
  AlertCircle,
  User,
  Bot,
  Sparkles,
  SlidersHorizontal,
  RotateCcw,
} from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageWorkspaceCanvas } from '../common/ImageWorkspaceCanvas';
import { GenViewLayout } from '../common/GenViewLayout';
import { ThinkingBlock } from '../message/ThinkingBlock';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { useAutoSelectGeneratedImageResult } from '../../hooks/useAutoSelectGeneratedImageResult';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../chat/ChatEditInputArea';
import { useThinkingBlock } from '../../hooks/useThinkingBlock';
import { CachedImage } from '../common/CachedImage';
import { getImageHistoryAttachmentPreviewUrl } from '../common/imageHistorySidebarHelpers';
import { getPreferredImageAttachmentUrl } from '../../utils/attachmentUrl';
import { useStableAttachmentImageUrl } from '../../hooks/useStableAttachmentImageUrl';
import { buildMessagesMediaSignature } from '../../utils/messageMediaSignature';

interface ImageBackgroundEditViewProps {
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
};

const BACKGROUND_EMPTY_STATE = (
  <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
    <Layers size={48} className="opacity-20" />
    <div>
      <h3 className="text-xl font-bold text-slate-500 mb-2">Background Editor</h3>
      <p className="text-sm opacity-60">上传图片并指定需要替换的背景区域</p>
    </div>
  </div>
);

const ImageEditMainCanvas = memo((props: ImageEditMainCanvasProps) => (
  <ImageWorkspaceCanvas
    {...props}
    headerIcon={Layers}
    headerIconClassName="text-blue-400"
    headerLabel="Background Editor"
    spinnerClassName="border-purple-500/30 border-t-purple-500"
    loadingText={{
      default: 'Processing Image...',
      uploading: '上传图片中...',
      loading: '背景编辑中，正在替换背景...',
      streaming: '流式处理中...',
    }}
    compareConfig={{
      beforeLabel: '原图',
      afterLabel: '背景编辑结果',
      accentColor: 'indigo',
    }}
    controlsAccentColor="indigo"
    emptyState={BACKGROUND_EMPTY_STATE}
  />
));

ImageEditMainCanvas.displayName = 'ImageEditMainCanvas';

export const ImageBackgroundEditView: React.FC<ImageBackgroundEditViewProps> = ({
  messages,
  setAppMode,
  onImageClick,
  loadingState,
  onSend,
  onStop,
  activeModelConfig,
  initialPrompt,
  initialAttachments,
  onExpandImage,
  providerId,
  sessionId: currentSessionId,
}) => {
  const { showError } = useToastContext();
  const scrollRef = useRef<HTMLDivElement>(null);

  // State for reference image
  const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
  const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);

  // 固定使用 image-background-edit 模式
  const editMode: AppMode = 'image-background-edit';

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

  const getStableCanvasUrlFromAttachment = useStableAttachmentImageUrl([], {
    retainedObjectUrl: activeImageUrl,
    createFileObjectUrls: false,
  });
  const messagesMediaSignature = buildMessagesMediaSignature(messages);

  const [isCompareMode, setIsCompareMode] = useState(false);
  const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });
  // 解构出 canvas 的稳定成员（内部均为 useCallback/useMemo），用于 mainContent 的
  // 依赖数组，避免直接依赖每次 render 都改变身份的 canvas 对象导致 useMemo 失效。
  const {
    zoom: canvasZoom,
    isDragging: canvasIsDragging,
    canvasStyle,
    handleWheel,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    handleZoomIn,
    handleZoomOut,
    handleReset,
    resetView,
  } = canvas;
  const getDisplayableImageAttachments = useCallback((attachments?: Attachment[]) => {
    return (attachments ?? []).filter((att) =>
      Boolean(att.file || getPreferredImageAttachmentUrl(att))
    );
  }, []);
  const handleSelectGeneratedResult = useCallback(({ firstUrl }: { firstUrl: string }) => {
    setActiveImageUrl(firstUrl);
  }, []);

  useEffect(() => {
    resetView();
    setIsCompareMode(false);
  }, [activeImageUrl, resetView]);

  const originalImageUrl = useMemo(() => {
    const lastUserMsg = [...messages]
      .reverse()
      .find((m) => m.role === Role.USER && m.attachments?.length);
    const attachment = lastUserMsg?.attachments?.[0];
    return attachment ? getStableCanvasUrlFromAttachment(attachment) : null;
  }, [getStableCanvasUrlFromAttachment, messages, messagesMediaSignature]);

  useEffect(() => {
    if (initialAttachments && initialAttachments.length > 0) {
      setActiveAttachments(initialAttachments);
      setActiveImageUrl(getStableCanvasUrlFromAttachment(initialAttachments[0]));
    }
  }, [initialAttachments, getStableCanvasUrlFromAttachment]);

  useEffect(() => {
    if (activeAttachments.length > 0) {
      setActiveImageUrl(getStableCanvasUrlFromAttachment(activeAttachments[0]));
    }
  }, [activeAttachments, getStableCanvasUrlFromAttachment]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    requestAnimationFrame(() => {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth',
      });
    });
  }, [messages, messagesMediaSignature, activeAttachments]);

  useEffect(() => {
    if (activeAttachments.length === 0 && !activeImageUrl) {
      const lastUserMsg = [...messages]
        .reverse()
        .find((m) => m.role === Role.USER && m.attachments?.length);
      const lastUserUrl = lastUserMsg?.attachments?.[0]
        ? getStableCanvasUrlFromAttachment(lastUserMsg.attachments[0])
        : null;
      if (lastUserMsg && lastUserUrl) {
        setActiveImageUrl(lastUserUrl);
      } else {
        const lastModelMsg = [...messages]
          .reverse()
          .find((m) => m.role === Role.MODEL && m.attachments?.length);
        const lastModelUrl = lastModelMsg?.attachments?.[0]
          ? getStableCanvasUrlFromAttachment(lastModelMsg.attachments[0])
          : null;
        if (lastModelMsg && lastModelUrl) {
          setActiveImageUrl(lastModelUrl);
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

  useAutoSelectGeneratedImageResult({
    messages,
    loadingState,
    getDisplayAttachments: getDisplayableImageAttachments,
    getAttachmentUrl: getStableCanvasUrlFromAttachment,
    onSelectResult: handleSelectGeneratedResult,
  });

  // ✅ ChatEditInputArea 已经处理了附件和参数，这里只需要直接转发
  const handleSend = useCallback(
    (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
      onSend(text, options, attachments, editMode);
    },
    [onSend, editMode]
  );

  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

  const sidebarContent = useMemo(
    () => (
      <div ref={scrollRef} className="flex-1 p-4 space-y-6 overflow-y-auto custom-scrollbar">
        {messages.map((msg) => {
          const isPlaceholder =
            !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
          if (isPlaceholder) return null;

          return (
            <div
              key={msg.id}
              className={`flex flex-col gap-2 ${msg.role === Role.USER ? 'items-end' : 'items-start'}`}
            >
              <div className="flex items-center gap-2 text-xs text-slate-500 px-1">
                {msg.role === Role.USER ? <User size={12} /> : <Bot size={12} />}
                <span>{msg.role === Role.USER ? 'You' : activeModelConfig?.name || 'AI'}</span>
              </div>
              <div
                className={`p-3 rounded-2xl max-w-full text-sm shadow-sm ${
                  msg.role === Role.USER
                    ? 'bg-slate-800 text-slate-200 rounded-tr-sm'
                    : 'bg-slate-800/50 text-slate-300 border border-slate-700/50 rounded-tl-sm'
                }`}
              >
                {msg.content && <p className="mb-2">{msg.content}</p>}
                {msg.attachments?.map((att, idx) => {
                  const previewId = att.id || `${msg.id}-${idx}`;
                  const sourceAttachment = att.id ? att : { ...att, id: previewId };
                  const imageUrl = getImageHistoryAttachmentPreviewUrl(
                    sourceAttachment,
                    previewId,
                    getStableCanvasUrlFromAttachment(sourceAttachment) ||
                      getPreferredImageAttachmentUrl(sourceAttachment)
                  );
                  if (!imageUrl) return null;
                  return (
                    <div
                      key={idx}
                      onClick={() => {
                        setActiveAttachments([sourceAttachment]);
                        setActiveImageUrl(imageUrl);
                      }}
                      className={`relative group mt-1 rounded-lg overflow-hidden border cursor-pointer transition-all ${
                        activeImageUrl === imageUrl
                          ? 'ring-2 ring-blue-500 border-transparent'
                          : 'border-slate-700 hover:border-slate-500'
                      }`}
                    >
                      <CachedImage
                        source={{
                          ...sourceAttachment,
                          attachmentId: previewId,
                          url: imageUrl,
                        }}
                        src={imageUrl}
                        className="w-full h-32 object-cover bg-slate-900"
                        alt="thumbnail"
                      />
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                        {activeImageUrl === imageUrl && (
                          <div className="bg-blue-500 w-2 h-2 rounded-full absolute top-2 right-2 shadow-sm" />
                        )}
                      </div>
                    </div>
                  );
                })}
                {msg.isError && (
                  <div className="flex items-center gap-2 text-red-400 text-xs mt-1">
                    <AlertCircle size={12} /> Error generating
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {loadingState !== 'idle' &&
          (() => {
            let statusText = 'Processing request...';
            let statusIcon = <Bot size={16} className="text-slate-500" />;

            if (loadingState === 'uploading') {
              statusText = '上传图片中...';
              statusIcon = <Layers size={16} className="text-blue-400" />;
            } else if (loadingState === 'loading') {
              statusText = '背景编辑中，正在替换背景...';
              statusIcon = <Layers size={16} className="text-blue-400" />;
            } else if (loadingState === 'streaming') {
              statusText = '流式处理中...';
              statusIcon = <Sparkles size={16} className="text-blue-400 animate-pulse" />;
            }

            const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
            const thoughts = lastMessage?.thoughts || [];
            const textResponse = lastMessage?.textResponse;
            const hasTextContent = lastMessage?.content && lastMessage.content.trim().length > 0;
            const isThinkingComplete = loadingState === 'idle';

            return (
              <div className="flex items-start gap-2">
                <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0">
                  {statusIcon}
                </div>
                <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400 flex-1">
                  <div
                    className={`font-medium mb-1 ${loadingState !== 'idle' ? 'animate-pulse' : ''}`}
                  >
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
            );
          })()}
        <div />
      </div>
    ),
    [
      messages,
      loadingState,
      activeModelConfig?.name,
      activeImageUrl,
      activeAttachments,
      getStableCanvasUrlFromAttachment,
      displayedThinkingContent,
      isThinkingOpen,
    ]
  );

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
          activeAttachments={activeAttachments}
          activeImageUrl={activeImageUrl}
          originalImageUrl={originalImageUrl}
          zoom={canvasZoom}
          isDragging={canvasIsDragging}
          canvasStyle={canvasStyle}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onReset={handleReset}
          onFullscreen={activeImageUrl ? handleFullscreen : undefined}
          onExpand={onExpandImage && activeImageUrl ? handleExpand : undefined}
          onToggleCompare={originalImageUrl ? toggleCompare : undefined}
        />

        {/* ========== 右侧：参数面板 ========== */}
        <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
          {/* 头部 */}
          <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={14} className="text-blue-400" />
              <span className="text-xs font-bold text-white">背景参数</span>
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
      activeAttachments,
      activeImageUrl,
      originalImageUrl,
      canvasZoom,
      canvasIsDragging,
      canvasStyle,
      handleWheel,
      handleMouseDown,
      handleMouseMove,
      handleMouseUp,
      handleZoomIn,
      handleZoomOut,
      handleReset,
      handleFullscreen,
      handleExpand,
      toggleCompare,
      onExpandImage,
      controls,
      providerId,
      resetParams,
      editMode,
      activeModelConfig,
      onStop,
      messages,
      currentSessionId,
      initialPrompt,
      initialAttachments,
      handleSend,
    ]
  );

  return (
    <GenViewLayout
      isMobileHistoryOpen={isMobileHistoryOpen}
      setIsMobileHistoryOpen={setIsMobileHistoryOpen}
      sidebarTitle="History"
      sidebarHeaderIcon={<Layers size={14} />}
      sidebar={sidebarContent}
      main={mainContent}
    />
  );
};
