/**
 * ImageMaskEditView 主区域：画布 (MaskCanvasPainter) + Mask 参数面板。
 *
 * 1:1 抽离自 `ImageMaskEditView.tsx` L1003-1110 mainContent useMemo body。
 */

import React from 'react';
import { ViewSideParamsPanel } from '../../common/ViewSideParamsPanel';
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
  displayCanvasRef: React.RefObject<HTMLCanvasElement | null>;
  maskInputDisabledReason: string | null;
}

export const MaskEditMain: React.FC<MaskEditMainProps> = ({
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
  displayCanvasRef,
  maskInputDisabledReason,
}) => {
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
        displayCanvasRef={displayCanvasRef}
      />

      <ViewSideParamsPanel
        title="Mask 参数"
        iconClass="text-purple-400"
        resetParams={resetParams}
        controlsContent={
          <ModeControlsCoordinator
            mode={editMode}
            providerId={providerId || 'google'}
            controls={controls}
          />
        }
        editAreaContent={
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
        }
      />
    </div>
  );
};
