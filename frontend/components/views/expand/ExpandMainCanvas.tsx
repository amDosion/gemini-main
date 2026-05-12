/**
 * ImageExpandView 主画布区域（旋转木马 + 参数面板）。
 *
 * 1:1 抽离自 `ImageExpandView.tsx` L607-851 mainContent useMemo body。
 */

import React from 'react';
import { Expand } from 'lucide-react';
import { ViewSideParamsPanel } from '../../common/ViewSideParamsPanel';
import { ImageCanvasControls } from '../../common/ImageCanvasControls';
import { ImageResultCanvas } from '../../common/ImageResultCanvas';
import { type CarouselMediaItem } from '../../common/ImageCarouselControls';
import { ImageCompare } from '../../common/ImageCompare';
import ChatEditInputArea from '../../chat/ChatEditInputArea';
import { ModeControlsCoordinator } from '../../../coordinators/ModeControlsCoordinator';
import { Message, AppMode, Attachment, ChatOptions } from '../../../types/types';
import type { useImageCanvas } from '../../../hooks/useImageCanvas';
import type { useControlsState } from '../../../hooks/useControlsState';

type ImageCanvasState = ReturnType<typeof useImageCanvas>;
type ControlsState = ReturnType<typeof useControlsState>;

export interface ExpandMainCanvasProps {
  loadingState: string;
  isBatchError: boolean | undefined;
  displayImages: Attachment[];
  activeBatchMessage: Message | undefined;
  currentDisplayUrl: string | null;
  activeImageUrl: string | null;
  setActiveImageUrl: React.Dispatch<React.SetStateAction<string | null>>;
  originalImageUrl: string | null;
  isCompareMode: boolean;
  toggleCompare: () => void;
  canvas: ImageCanvasState;
  carouselIndex: number;
  carouselItems: CarouselMediaItem[];
  handleCarouselPrev: () => void;
  handleCarouselNext: () => void;
  handleCarouselSelect: (index: number) => void;
  onImageClick: (url: string) => void;
  controls: ControlsState;
  providerId?: string;
  resetParams: () => void;
  expandMode: AppMode;
  onStop: () => void;
  messages: Message[];
  currentSessionId?: string | null;
  initialAttachments?: Attachment[];
  handleSend: (
    text: string,
    options: ChatOptions,
    attachments: Attachment[],
    mode: AppMode
  ) => void;
  activeAttachments: Attachment[];
  setActiveAttachments: React.Dispatch<React.SetStateAction<Attachment[]>>;
}

export const ExpandMainCanvas: React.FC<ExpandMainCanvasProps> = ({
  loadingState,
  isBatchError,
  displayImages,
  activeBatchMessage,
  currentDisplayUrl,
  activeImageUrl,
  setActiveImageUrl,
  originalImageUrl,
  isCompareMode,
  toggleCompare,
  canvas,
  carouselIndex,
  carouselItems,
  handleCarouselPrev,
  handleCarouselNext,
  handleCarouselSelect,
  onImageClick,
  controls,
  providerId,
  resetParams,
  expandMode,
  onStop,
  messages,
  currentSessionId,
  initialAttachments,
  handleSend,
  activeAttachments,
  setActiveAttachments,
}) => {
  return (
    <div className="flex-1 flex flex-row h-full">
      <ImageResultCanvas
        loadingState={loadingState}
        isBatchError={isBatchError}
        errorTitle="扩图失败"
        errorMessage={activeBatchMessage?.content}
        displayImages={displayImages}
        carouselItems={carouselItems}
        carouselIndex={carouselIndex}
        handleCarouselPrev={handleCarouselPrev}
        handleCarouselNext={handleCarouselNext}
        handleCarouselSelect={handleCarouselSelect}
        onImageClick={onImageClick}
        altFor={(idx) => `扩图结果 ${idx + 1}`}
        canvas={canvas}
        mode="image-outpainting"
        accentColor="orange"
        controlsExtra={{
          onFullscreen: currentDisplayUrl ? () => onImageClick(currentDisplayUrl) : undefined,
          onToggleCompare: originalImageUrl ? toggleCompare : undefined,
          isCompareMode,
        }}
        spinnerColorClass="border-orange-500/30 border-t-orange-500"
        spinnerBadgeText="EXP"
        spinnerBadgeColorClass="text-orange-400"
        loadingTitle="扩图中..."
        accentIconClass="text-orange-400"
        carouselAccentTone="orange"
        wheelTarget="outer"
        compareSlot={
          originalImageUrl && currentDisplayUrl ? (
            <div
              className="relative shadow-2xl transition-transform duration-75 ease-out"
              style={canvas.canvasStyle}
            >
              <ImageCompare
                beforeImage={originalImageUrl}
                afterImage={currentDisplayUrl}
                beforeLabel="原图"
                afterLabel="扩图结果"
                accentColor="orange"
                className="max-w-none rounded-lg border border-slate-800"
                style={{ maxHeight: '70vh', maxWidth: '80vw' }}
              />
            </div>
          ) : null
        }
        sourcePreviewSlot={
          activeImageUrl ? (
            <div className="flex-1 flex items-center justify-center p-0 w-full h-full">
              <div
                className="relative shadow-2xl group transition-transform duration-75 ease-out"
                style={canvas.canvasStyle}
                onMouseDown={canvas.handleMouseDown}
                onMouseMove={canvas.handleMouseMove}
                onMouseUp={canvas.handleMouseUp}
                onMouseLeave={canvas.handleMouseUp}
              >
                <img
                  src={activeImageUrl}
                  className="max-w-none rounded-lg border border-slate-800 pointer-events-none"
                  style={{ maxHeight: '80vh', maxWidth: '80vw' }}
                  alt="Source Preview"
                />
                <ImageCanvasControls
                  variant="canvas"
                  className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                  zoom={canvas.zoom}
                  onZoomIn={canvas.handleZoomIn}
                  onZoomOut={canvas.handleZoomOut}
                  onReset={canvas.handleReset}
                  onFullscreen={() => onImageClick(activeImageUrl)}
                  downloadUrl={activeImageUrl}
                  accentColor="orange"
                />
              </div>
            </div>
          ) : null
        }
        emptyState={
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
              <Expand size={48} className="opacity-20" />
              <div>
                <h3 className="text-xl font-bold text-slate-500 mb-2">Out-Paint Workspace</h3>
                <p className="text-sm opacity-60">在右侧上传图片，设置参数后点击扩图</p>
              </div>
            </div>
          </div>
        }
      />

      <ViewSideParamsPanel
        title="扩图参数"
        iconClass="text-orange-400"
        resetParams={resetParams}
        controlsContent={
          <ModeControlsCoordinator
            mode={expandMode}
            providerId={providerId || 'google'}
            controls={controls}
          />
        }
        editAreaContent={
          <ChatEditInputArea
            onSend={handleSend}
            isLoading={loadingState !== 'idle'}
            onStop={onStop}
            mode={expandMode}
            activeAttachments={activeAttachments}
            onAttachmentsChange={setActiveAttachments}
            activeImageUrl={activeImageUrl}
            onActiveImageUrlChange={setActiveImageUrl}
            messages={messages}
            sessionId={currentSessionId ?? null}
            initialAttachments={initialAttachments}
            providerId={providerId}
            controls={controls}
          />
        }
      />
    </div>
  );
};
