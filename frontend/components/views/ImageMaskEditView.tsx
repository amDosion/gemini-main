import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Layers } from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { GenViewLayout } from '../common/GenViewLayout';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { useAutoSelectGeneratedImageResult } from '../../hooks/useAutoSelectGeneratedImageResult';
import { useThinkingBlock } from '../../hooks/useThinkingBlock';
import { useMaskIO } from '../../hooks/useMaskIO';
import { MaskEditSidebar } from './maskedit/MaskEditSidebar';
import { MaskEditMain } from './maskedit/MaskEditMain';
import { getPreferredImageAttachmentUrl } from '../../utils/attachmentUrl';
import { useStableAttachmentImageUrl } from '../../hooks/useStableAttachmentImageUrl';
import { revokeManagedMediaObjectUrl } from '../../services/mediaCache';
import { buildMessagesMediaSignature } from '../../utils/messageMediaSignature';
import {
  drawOnMaskCanvas as drawOnMaskCanvasPure,
  generateMaskFromSelections as generateMaskFromSelectionsPure,
  getOrCreateMaskCanvas,
  drawDisplayCanvas,
  updateMaskCanvasUrl as updateMaskCanvasUrlPure,
} from './maskedit/maskDrawingHelpers';
import {
  type MaskTool,
  type SelectionRect,
  SEMANTIC_PERSON_CLASS_ID,
} from '../../utils/maskHelpers';

interface ImageMaskEditViewProps {
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

// MaskTool / MaskMode / SelectionRect / 3 helper 已抽离到 utils/maskHelpers（Step 1, 3）
// ImageEditMainCanvas 已抽离至 mask/MaskCanvasPainter + mask/MaskToolbar（Step 4-5）
// handleMaskModeChange / handleImportMask / handleClearMask 抽离至 hooks/useMaskIO（Step 3）

export const ImageMaskEditView: React.FC<ImageMaskEditViewProps> = ({
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
}) => {
  const { showError } = useToastContext();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Mounted flag：用于 generateMaskFromSelections 中 canvas.toBlob 异步回调，
  // 若组件已卸载则丢弃后续 object URL 创建，避免 blob URL 泄漏。
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // State for reference image
  const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
  const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);

  // 固定使用 image-mask-edit 模式
  const editMode: AppMode = 'image-mask-edit';

  // ✅ 参数面板状态
  const controls = useControlsState(editMode, activeModelConfig);

  // 重置参数（mask 编辑特有参数）
  const resetParams = useCallback(() => {
    controls.setEditMode('EDIT_MODE_INPAINT_INSERTION');
    controls.setMaskDilation(0.06);
    controls.setGuidanceScale(15.0);
    controls.setNumberOfImages(1);
    controls.setNegativePrompt('');
    controls.setOutputMimeType('image/png');
    controls.setOutputCompressionQuality(100);
  }, [controls]);

  // State for thinking block
  const {
    isOpen: isThinkingOpen,
    setIsOpen: setIsThinkingOpen,
    displayedContent: displayedThinkingContent,
  } = useThinkingBlock(messages, loadingState);

  const getStableCanvasUrlFromAttachment = useStableAttachmentImageUrl([], {
    retainedObjectUrl: activeImageUrl,
    createFileObjectUrls: true,
  });
  const messagesMediaSignature = buildMessagesMediaSignature(messages);

  const [isCompareMode, setIsCompareMode] = useState(false);
  const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });
  const getDisplayableImageAttachments = useCallback((attachments?: Attachment[]) => {
    return (attachments ?? []).filter((att) =>
      Boolean(att.file || getPreferredImageAttachmentUrl(att))
    );
  }, []);
  const handleSelectGeneratedResult = useCallback(({ firstUrl }: { firstUrl: string }) => {
    setActiveImageUrl(firstUrl);
  }, []);

  // ✅ Mask 工具状态（默认 select 矩形选择工具）
  const [activeMaskTool, setActiveMaskTool] = useState<MaskTool>('select');
  const [brushSize, setBrushSize] = useState(20); // 默认画笔大小 20px
  const [isMaskInverted, setIsMaskInverted] = useState(false); // 前景/背景切换
  const [isPreviewingMask, setIsPreviewingMask] = useState(false); // 正在加载自动 mask 预览
  // maskMode 使用 controls.maskMode，以便在发送请求时能够正确传递给后端

  // ✅ 选区状态（支持多个矩形）
  const [selectionRects, setSelectionRects] = useState<SelectionRect[]>([]);
  const [currentSelectionRect, setCurrentSelectionRect] = useState<SelectionRect | null>(null);
  const [isSelecting, setIsSelecting] = useState(false);
  const [maskPreviewUrl, setMaskPreviewUrl] = useState<string | null>(null);
  const [maskPreviewNotice, setMaskPreviewNotice] = useState<string | null>(null);
  const [maskPreviewError, setMaskPreviewError] = useState<string | null>(null);
  const [maskRequestDataUrl, setMaskRequestDataUrl] = useState<string | null>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  // ✅ 画笔/橡皮擦状态
  const [isPainting, setIsPainting] = useState(false);
  const maskCanvasRef = useRef<HTMLCanvasElement | null>(null); // 存储画笔绘制的 mask 数据
  const [maskCanvasUrl, setMaskCanvasUrl] = useState<string | null>(null); // mask canvas 的 object URL（用于触发 useEffect）
  const lastBrushPosRef = useRef<{ x: number; y: number } | null>(null); // 上一次画笔位置（用于连续绘制）
  // 贝塞尔曲线控制点历史（用于平滑绘制）
  const brushPointsRef = useRef<Array<{ x: number; y: number }>>([]);
  // 显示用的 canvas ref（用于直接 DOM 更新，避免 React 重渲染）
  const displayCanvasRef = useRef<HTMLCanvasElement | null>(null);

  // ✅ 性能优化：RAF 节流相关
  const rafIdRef = useRef<number | null>(null); // requestAnimationFrame ID
  const pendingDrawRef = useRef<{ x: number; y: number; isEraser: boolean } | null>(null); // 待绘制的数据
  const hasBrushContentRef = useRef<boolean>(false); // 是否有画笔内容（避免全图扫描）
  const maskCompositeCanvasRef = useRef<HTMLCanvasElement | null>(null); // 复用的合成 canvas
  const maskPreviewBlobUrlRef = useRef<string | null>(null); // 存储 maskCanvasUrl 的 blob URL 用于清理
  const maskPreviewUrlRef = useRef<string | null>(null); // 存储 maskPreviewUrl 的 blob URL 用于清理（避免循环依赖）

  // ✅ 性能优化：光标位置使用 ref + 直接 DOM 更新（避免 React 重渲染）
  const brushCursorRef = useRef<HTMLDivElement | null>(null);
  const brushCursorPosRef = useRef<{ x: number; y: number } | null>(null);

  // Mask 工具回调
  const handleMaskToolChange = useCallback((tool: MaskTool) => {
    setActiveMaskTool(tool);
  }, []);

  const handleBrushSizeChange = useCallback((size: number) => {
    setBrushSize(size);
  }, []);

  const handleToggleMaskInvert = useCallback(() => {
    setIsMaskInverted((prev) => !prev);
  }, []);

  // ✅ 画笔光标位置更新（使用 ref + 直接 DOM 更新，避免 React 重渲染）
  const handleBrushCursorMove = useCallback(
    (pos: { x: number; y: number } | null) => {
      brushCursorPosRef.current = pos;
      const cursorEl = brushCursorRef.current;
      if (!cursorEl) return;

      if (pos) {
        cursorEl.style.display = 'block';
        cursorEl.style.left = `${pos.x - brushSize / 2}px`;
        cursorEl.style.top = `${pos.y - brushSize / 2}px`;
      } else {
        cursorEl.style.display = 'none';
      }
    },
    [brushSize]
  );

  const getMaskCanvas = useCallback(() => getOrCreateMaskCanvas(imageRef, maskCanvasRef), []);
  const updateDisplayCanvas = useCallback(
    () => drawDisplayCanvas(maskCanvasRef, displayCanvasRef),
    []
  );
  const updateMaskCanvasUrlCb = useCallback(() => {
    updateMaskCanvasUrlPure({
      maskCanvasRef,
      hasBrushContentRef,
      maskPreviewBlobUrlRef,
      setMaskCanvasUrl,
      onAfterUpdate: updateDisplayCanvas,
    });
  }, [updateDisplayCanvas]);

  // ✅ 在 mask canvas 上绘制（贝塞尔曲线平滑笔画，纯函数已抽离）
  const drawOnMaskCanvas = useCallback(
    (x: number, y: number, isEraser: boolean = false, isStart: boolean = false) => {
      drawOnMaskCanvasPure({
        x,
        y,
        isEraser,
        isStart,
        getMaskCanvas,
        imageRef,
        brushSize,
        brushPointsRef,
        hasBrushContentRef,
        lastBrushPosRef,
      });
    },
    [getMaskCanvas, brushSize]
  );

  // ✅ 画笔/橡皮擦事件处理
  const handleBrushStart = useCallback(
    (e: React.MouseEvent) => {
      if (activeMaskTool !== 'brush' && activeMaskTool !== 'eraser') return;

      const rect = e.currentTarget.getBoundingClientRect();
      const x = (e.clientX - rect.left) / canvas.zoom;
      const y = (e.clientY - rect.top) / canvas.zoom;

      setIsPainting(true);
      lastBrushPosRef.current = null; // 开始新笔画时重置
      brushPointsRef.current = []; // 重置贝塞尔曲线点历史
      drawOnMaskCanvas(x, y, activeMaskTool === 'eraser', true); // isStart = true
      // 直接更新显示 canvas（不触发 React 重渲染）
      updateDisplayCanvas();
    },
    [activeMaskTool, canvas.zoom, drawOnMaskCanvas, updateDisplayCanvas]
  );

  // ✅ 使用 RAF 节流的画笔移动处理（将多次 mousemove 合并为每帧一次绘制）
  const handleBrushMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isPainting) return;

      const rect = e.currentTarget.getBoundingClientRect();
      const x = (e.clientX - rect.left) / canvas.zoom;
      const y = (e.clientY - rect.top) / canvas.zoom;

      // 存储待绘制数据
      pendingDrawRef.current = { x, y, isEraser: activeMaskTool === 'eraser' };

      // 如果没有 pending 的 RAF，则请求一个
      if (rafIdRef.current === null) {
        rafIdRef.current = requestAnimationFrame(() => {
          const pending = pendingDrawRef.current;
          if (pending) {
            drawOnMaskCanvas(pending.x, pending.y, pending.isEraser);
            updateDisplayCanvas();
            pendingDrawRef.current = null;
          }
          rafIdRef.current = null;
        });
      }
    },
    [isPainting, activeMaskTool, canvas.zoom, drawOnMaskCanvas, updateDisplayCanvas]
  );

  const handleBrushEnd = useCallback(() => {
    if (!isPainting) return;

    // 取消未完成的 RAF
    if (rafIdRef.current !== null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }

    // 处理最后一个待绘制的点
    const pending = pendingDrawRef.current;
    if (pending) {
      drawOnMaskCanvas(pending.x, pending.y, pending.isEraser);
      updateDisplayCanvas();
      pendingDrawRef.current = null;
    }

    setIsPainting(false);
    lastBrushPosRef.current = null;
    updateMaskCanvasUrlCb();
  }, [isPainting, drawOnMaskCanvas, updateDisplayCanvas, updateMaskCanvasUrlCb]);

  // P0 #2 Step 3：handleMaskModeChange / handleImportMask / handleClearMask 抽离至 useMaskIO
  const { handleMaskModeChange, handleImportMask, handleClearMask } = useMaskIO({
    controls,
    activeImageUrl,
    providerId,
    showError,
    setters: {
      setMaskRequestDataUrl,
      setMaskPreviewNotice,
      setMaskPreviewError,
      setSelectionRects,
      setCurrentSelectionRect,
      setIsPreviewingMask,
      setMaskPreviewUrl,
      setMaskCanvasUrl,
    },
    refs: {
      imageRef,
      maskCanvasRef,
      displayCanvasRef,
      hasBrushContentRef,
      maskPreviewBlobUrlRef,
      maskPreviewUrlRef,
    },
  });

  // ✅ 生成 Mask 图像（纯函数已抽离至 maskDrawingHelpers）
  const generateMaskFromSelections = useCallback(
    (rects: SelectionRect[], inverted: boolean = false) => {
      generateMaskFromSelectionsPure({
        rects,
        inverted,
        imageRef,
        maskCanvasRef,
        hasBrushContentRef,
        maskCompositeCanvasRef,
        maskPreviewUrlRef,
        isMountedRef,
        setMaskPreviewUrl,
        setMaskRequestDataUrl,
        setMaskPreviewError,
        showError,
      });
    },
    [showError]
  );

  // ✅ 选区开始（考虑缩放比例）
  const handleSelectionStart = useCallback(
    (e: React.MouseEvent) => {
      if (activeMaskTool !== 'select') return;

      const rect = e.currentTarget.getBoundingClientRect();
      // 除以缩放比例，转换到图片原始坐标系
      const x = (e.clientX - rect.left) / canvas.zoom;
      const y = (e.clientY - rect.top) / canvas.zoom;

      setIsSelecting(true);
      setCurrentSelectionRect({
        startX: x,
        startY: y,
        endX: x,
        endY: y,
      });
    },
    [activeMaskTool, canvas.zoom]
  );

  // ✅ 选区移动（考虑缩放比例）
  const handleSelectionMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isSelecting || activeMaskTool !== 'select') return;

      const rect = e.currentTarget.getBoundingClientRect();
      // 除以缩放比例，转换到图片原始坐标系
      const x = (e.clientX - rect.left) / canvas.zoom;
      const y = (e.clientY - rect.top) / canvas.zoom;

      setCurrentSelectionRect((prev: SelectionRect | null) =>
        prev
          ? {
              ...prev,
              endX: x,
              endY: y,
            }
          : null
      );
    },
    [isSelecting, activeMaskTool, canvas.zoom]
  );

  // ✅ 选区结束
  // 注意：只设置 state，mask 生成由 useEffect 统一处理，避免冗余调用
  const handleSelectionEnd = useCallback(() => {
    if (!isSelecting || !currentSelectionRect) return;

    setIsSelecting(false);

    const width = Math.abs(currentSelectionRect.endX - currentSelectionRect.startX);
    const height = Math.abs(currentSelectionRect.endY - currentSelectionRect.startY);

    // 只有当选区大小有效时才添加到数组
    if (width > 5 && height > 5) {
      const newRects = [...selectionRects, currentSelectionRect];
      setSelectionRects(newRects);
      // mask 生成由 useEffect (line ~1315) 统一处理
    }

    setCurrentSelectionRect(null);
  }, [isSelecting, currentSelectionRect, selectionRects]);

  // ✅ 删除单个选区
  // 注意：只设置 state，mask 生成/清除由 useEffect 统一处理
  const handleDeleteSelection = useCallback(
    (index: number) => {
      const newRects = selectionRects.filter((_, i) => i !== index);
      setSelectionRects(newRects);
      // 当没有选区且没有画笔数据时，useEffect 会清除 maskPreviewUrl
      // mask 生成由 useEffect (line ~1315) 统一处理
    },
    [selectionRects]
  );

  // ✅ 当反转模式变化、选区变化或画笔数据变化时，重新生成 mask
  // 使用 maskCanvasUrl 作为画笔数据变化的触发器
  useEffect(() => {
    const hasBrushData = maskCanvasUrl !== null;
    const isAutoMaskMode = controls.maskMode !== 'MASK_MODE_USER_PROVIDED';

    if (selectionRects.length > 0 || hasBrushData) {
      // 有选区或画笔数据时生成 mask（仅在手动模式下有效）
      generateMaskFromSelections(selectionRects, isMaskInverted);
    } else if (!isAutoMaskMode) {
      // 手动模式下，既没有选区也没有画笔数据时，清除 mask 预览
      // 注意：自动 mask 模式下，maskPreviewUrl 由 API 返回设置，不应在此清除
      if (maskPreviewUrlRef.current) {
        revokeManagedMediaObjectUrl(maskPreviewUrlRef.current);
        maskPreviewUrlRef.current = null;
      }
      setMaskPreviewUrl(null);
      setMaskPreviewNotice(null);
      setMaskPreviewError(null);
      setMaskRequestDataUrl(null);
    }
    // 自动 mask 模式下，保留 API 返回的 maskPreviewUrl
  }, [
    isMaskInverted,
    selectionRects,
    generateMaskFromSelections,
    maskCanvasUrl,
    controls.maskMode,
  ]);

  // ✅ 当 maskCanvasUrl 变化时，同步更新显示 canvas
  useEffect(() => {
    if (maskCanvasUrl && maskCanvasRef.current) {
      updateDisplayCanvas();
    }
  }, [maskCanvasUrl, updateDisplayCanvas]);

  // ✅ 组件卸载时清理 blob URL
  useEffect(() => {
    return () => {
      // 清理 maskCanvasUrl 的 blob URL
      if (maskPreviewBlobUrlRef.current) {
        revokeManagedMediaObjectUrl(maskPreviewBlobUrlRef.current);
      }
      // 清理 maskPreviewUrl 的 blob URL
      if (maskPreviewUrlRef.current) {
        revokeManagedMediaObjectUrl(maskPreviewUrlRef.current);
      }
      // 取消未完成的 RAF
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, []);

  useEffect(() => {
    canvas.resetView();
    setIsCompareMode(false);
    handleClearMask();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeImageUrl]); // canvas.resetView 是稳定的函数，不需要作为依赖

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

  // ✅ ChatEditInputArea 已处理 raw 附件；Mask 模式在这里追加官方 SDK 需要的 mask reference。
  const handleSend = useCallback(
    (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
      const nextOptions: ChatOptions = { ...options };
      let nextAttachments = attachments;

      if (controls.maskMode === 'MASK_MODE_USER_PROVIDED') {
        if (!maskRequestDataUrl) {
          showError('请先绘制、导入或选择自动 Mask');
          return;
        }

        const maskAttachment: Attachment = {
          id: `mask-${Date.now()}`,
          name: 'mask.png',
          mimeType: 'image/png',
          url: maskRequestDataUrl,
          tempUrl: maskRequestDataUrl,
          role: 'mask',
          uploadStatus: 'pending',
        };
        nextOptions.maskMode = 'MASK_MODE_USER_PROVIDED';
        nextAttachments = [
          ...attachments.filter((attachment) => attachment.role !== 'mask'),
          maskAttachment,
        ];
      } else if (controls.maskMode === 'MASK_MODE_SEMANTIC') {
        nextOptions.segmentationClasses = [SEMANTIC_PERSON_CLASS_ID];
      }

      onSend(text, nextOptions, nextAttachments, editMode);
    },
    [controls.maskMode, editMode, maskRequestDataUrl, onSend, showError]
  );

  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

  const sidebarContent = useMemo(
    () => (
      <MaskEditSidebar
        scrollRef={scrollRef}
        messages={messages}
        activeModelConfig={activeModelConfig}
        loadingState={loadingState}
        activeImageUrl={activeImageUrl}
        setActiveImageUrl={setActiveImageUrl}
        setActiveAttachments={setActiveAttachments}
        displayedThinkingContent={displayedThinkingContent}
        isThinkingOpen={isThinkingOpen}
        setIsThinkingOpen={setIsThinkingOpen}
      />
    ),
    [
      messages,
      loadingState,
      activeModelConfig,
      activeImageUrl,
      displayedThinkingContent,
      isThinkingOpen,
      setIsThinkingOpen,
    ]
  );

  const toggleCompare = useCallback(() => setIsCompareMode((prev) => !prev), []);
  const handleFullscreen = useCallback(() => {
    if (activeImageUrl) onImageClick(activeImageUrl);
  }, [activeImageUrl, onImageClick]);
  const handleExpand = useCallback(() => {
    if (activeImageUrl && onExpandImage) onExpandImage(activeImageUrl);
  }, [activeImageUrl, onExpandImage]);
  const maskInputDisabledReason = useMemo(() => {
    if (!activeImageUrl) return null;
    if (controls.maskMode !== 'MASK_MODE_USER_PROVIDED') return null;
    if (maskRequestDataUrl) return null;
    return '请先绘制或导入 Mask，或选择自动前景/背景/人物分割';
  }, [activeImageUrl, controls.maskMode, maskRequestDataUrl]);

  // ✅ 主区域：两栏布局（画布 + 参数面板）
  const mainContent = useMemo(
    () => (
      <MaskEditMain
        loadingState={loadingState}
        isCompareMode={isCompareMode}
        activeAttachments={activeAttachments}
        setActiveAttachments={setActiveAttachments}
        activeImageUrl={activeImageUrl}
        setActiveImageUrl={setActiveImageUrl}
        originalImageUrl={originalImageUrl}
        canvas={canvas}
        handleFullscreen={handleFullscreen}
        handleExpand={handleExpand}
        toggleCompare={toggleCompare}
        onExpandImage={onExpandImage}
        controls={controls}
        providerId={providerId}
        resetParams={resetParams}
        editMode={editMode}
        onStop={onStop}
        messages={messages}
        currentSessionId={currentSessionId}
        initialPrompt={initialPrompt}
        initialAttachments={initialAttachments}
        handleSend={handleSend}
        activeMaskTool={activeMaskTool}
        handleMaskToolChange={handleMaskToolChange}
        brushSize={brushSize}
        handleBrushSizeChange={handleBrushSizeChange}
        handleMaskModeChange={handleMaskModeChange}
        handleImportMask={handleImportMask}
        handleClearMask={handleClearMask}
        isPreviewingMask={isPreviewingMask}
        isMaskInverted={isMaskInverted}
        handleToggleMaskInvert={handleToggleMaskInvert}
        selectionRects={selectionRects}
        currentSelectionRect={currentSelectionRect}
        isSelecting={isSelecting}
        handleSelectionStart={handleSelectionStart}
        handleSelectionMove={handleSelectionMove}
        handleSelectionEnd={handleSelectionEnd}
        handleDeleteSelection={handleDeleteSelection}
        maskPreviewUrl={maskPreviewUrl}
        maskPreviewNotice={maskPreviewNotice}
        maskPreviewError={maskPreviewError}
        imageRef={imageRef}
        handleBrushStart={handleBrushStart}
        handleBrushMove={handleBrushMove}
        handleBrushEnd={handleBrushEnd}
        isPainting={isPainting}
        maskCanvasUrl={maskCanvasUrl}
        brushCursorRef={brushCursorRef}
        handleBrushCursorMove={handleBrushCursorMove}
        maskCanvasRef={maskCanvasRef}
        displayCanvasRef={displayCanvasRef}
        maskInputDisabledReason={maskInputDisabledReason}
      />
    ),
    [
      loadingState,
      isCompareMode,
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
      activeMaskTool,
      handleMaskToolChange,
      brushSize,
      handleBrushSizeChange,
      handleMaskModeChange,
      handleImportMask,
      handleClearMask,
      isMaskInverted,
      handleToggleMaskInvert,
      selectionRects,
      currentSelectionRect,
      isSelecting,
      handleSelectionStart,
      handleSelectionMove,
      handleSelectionEnd,
      handleDeleteSelection,
      maskPreviewUrl,
      maskPreviewNotice,
      maskPreviewError,
      isPreviewingMask,
      handleBrushStart,
      handleBrushMove,
      handleBrushEnd,
      isPainting,
      maskCanvasUrl,
      handleBrushCursorMove,
      maskInputDisabledReason,
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
