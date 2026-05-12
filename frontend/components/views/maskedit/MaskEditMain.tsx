/**
 * ImageMaskEditView 主区域：画布 (MaskCanvasPainter) + Mask 参数面板。
 *
 * 1:1 抽离自 `ImageMaskEditView.tsx` L1003-1110 mainContent useMemo body。
 */

import React from 'react';
import { RotateCcw, SlidersHorizontal } from 'lucide-react';
import { Message, AppMode, Attachment, ChatOptions } from '../../../types/types';
import { ModeControlsCoordinator } from '../../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../../chat/ChatEditInputArea';
import { MaskCanvasPainter } from '../mask/MaskCanvasPainter';
import type { useImageCanvas } from '../../../hooks/useImageCanvas';
import type { useControlsState } from '../../../hooks/useControlsState';
import type { MaskTool, MaskMode, SelectionRect } from '../../../utils/maskHelpers';

type ImageCanvasState = ReturnType<typeof useImageCanvas>;
type ControlsState = ReturnType<typeof useControlsState>;

export interface MaskEditMainProps {
  loadingState: string;
  isCompareMode: boolean;
  activeAttachments: Attachment[];
  setActiveAttachments: React.Dispatch<React.SetStateAction<Attachment[]>>;
  activeImageUrl: string | null;
  setActiveImageUrl: React.Dispatch<React.SetStateAction<string | null>>;
  originalImageUrl: string | null;
  canvas: ImageCanvasState;
  handleFullscreen: () => void;
  handleExpand: () => void;
  toggleCompare: () => void;
  onExpandImage?: (url: string) => void;
  controls: ControlsState;
  providerId?: string;
  resetParams: () => void;
  editMode: AppMode;
  onStop: () => void;
  messages: Message[];
  currentSessionId?: string | null;
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  handleSend: (
    text: string,
    options: ChatOptions,
    attachments: Attachment[],
    mode: AppMode
  ) => void;
  activeMaskTool: MaskTool;
  handleMaskToolChange: (tool: MaskTool) => void;
  brushSize: number;
  handleBrushSizeChange: (size: number) => void;
  handleMaskModeChange: (mode: MaskMode) => void | Promise<void>;
  handleImportMask: () => void;
  handleClearMask: () => void;
  isPreviewingMask: boolean;
  isMaskInverted: boolean;
  handleToggleMaskInvert: () => void;
  selectionRects: SelectionRect[];
  currentSelectionRect: SelectionRect | null;
  isSelecting: boolean;
  handleSelectionStart: (e: React.MouseEvent) => void;
  handleSelectionMove: (e: React.MouseEvent) => void;
  handleSelectionEnd: () => void;
  handleDeleteSelection: (index: number) => void;
  maskPreviewUrl: string | null;
  maskPreviewNotice: string | null;
  maskPreviewError: string | null;
  imageRef: React.RefObject<HTMLImageElement | null>;
  handleBrushStart: (e: React.MouseEvent) => void;
  handleBrushMove: (e: React.MouseEvent) => void;
  handleBrushEnd: () => void;
  isPainting: boolean;
  maskCanvasUrl: string | null;
  brushCursorRef: React.RefObject<HTMLDivElement | null>;
  handleBrushCursorMove: (pos: { x: number; y: number } | null) => void;
  maskCanvasRef: React.RefObject<HTMLCanvasElement | null>;
  displayCanvasRef: React.RefObject<HTMLCanvasElement | null>;
  maskInputDisabledReason: string | null;
}

export const MaskEditMain: React.FC<MaskEditMainProps> = (props) => {
  const {
    loadingState,
    isCompareMode,
    activeAttachments,
    setActiveAttachments,
    activeImageUrl,
    setActiveImageUrl,
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
    isPreviewingMask,
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
    imageRef,
    handleBrushStart,
    handleBrushMove,
    handleBrushEnd,
    isPainting,
    maskCanvasUrl,
    brushCursorRef,
    handleBrushCursorMove,
    maskCanvasRef,
    displayCanvasRef,
    maskInputDisabledReason,
  } = props;

  return (
    <div className="flex-1 flex flex-row h-full">
      <MaskCanvasPainter
        loadingState={loadingState}
        isCompareMode={isCompareMode}
        activeAttachments={activeAttachments}
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
        activeMaskTool={activeMaskTool}
        onMaskToolChange={handleMaskToolChange}
        brushSize={brushSize}
        onBrushSizeChange={handleBrushSizeChange}
        maskMode={controls.maskMode}
        onMaskModeChange={handleMaskModeChange}
        onImportMask={handleImportMask}
        onClearMask={handleClearMask}
        isPreviewingMask={isPreviewingMask}
        isMaskInverted={isMaskInverted}
        onToggleMaskInvert={handleToggleMaskInvert}
        selectionRects={selectionRects}
        currentSelectionRect={currentSelectionRect}
        isSelecting={isSelecting}
        onSelectionStart={handleSelectionStart}
        onSelectionMove={handleSelectionMove}
        onSelectionEnd={handleSelectionEnd}
        onDeleteSelection={handleDeleteSelection}
        maskPreviewUrl={maskPreviewUrl}
        maskPreviewNotice={maskPreviewNotice}
        maskPreviewError={maskPreviewError}
        imageRef={imageRef}
        onBrushStart={handleBrushStart}
        onBrushMove={handleBrushMove}
        onBrushEnd={handleBrushEnd}
        isPainting={isPainting}
        maskCanvasUrl={maskCanvasUrl}
        brushCursorRef={brushCursorRef}
        onBrushCursorMove={handleBrushCursorMove}
        maskCanvasRef={maskCanvasRef}
        displayCanvasRef={displayCanvasRef}
      />

      <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={14} className="text-purple-400" />
            <span className="text-xs font-bold text-white">Mask 参数</span>
          </div>
          <button
            onClick={resetParams}
            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
            title="重置为默认值"
          >
            <RotateCcw size={12} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
          <ModeControlsCoordinator
            mode={editMode}
            providerId={providerId || 'google'}
            controls={controls}
          />
        </div>

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
          externalDisabled={Boolean(maskInputDisabledReason)}
          externalDisabledReason={maskInputDisabledReason}
        />
      </div>
    </div>
  );
};
