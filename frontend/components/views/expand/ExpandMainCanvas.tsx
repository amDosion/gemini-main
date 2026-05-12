/**
 * ImageExpandView 主画布区域（旋转木马 + 参数面板）。
 *
 * 1:1 抽离自 `ImageExpandView.tsx` L607-851 mainContent useMemo body。
 */

import React from 'react';
import { AlertCircle, Expand, Grid, Image as ImageIcon } from 'lucide-react';
import { ViewSideParamsPanel } from '../../common/ViewSideParamsPanel';
import { ImageCanvasControls } from '../../common/ImageCanvasControls';
import {
  ImageCarouselArrows,
  ImageCarouselThumbnails,
  type CarouselMediaItem,
} from '../../common/ImageCarouselControls';
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
      <div
        className="flex-1 w-full h-full select-none flex flex-col relative"
        onWheel={isCompareMode ? undefined : canvas.handleWheel}
      >
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

        {loadingState !== 'idle' ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex flex-col items-center gap-6 p-8 rounded-3xl bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 shadow-2xl">
              <div className="relative">
                <div className="w-20 h-20 border-4 border-orange-500/30 border-t-orange-500 rounded-full animate-spin"></div>
                <div className="absolute inset-0 flex items-center justify-center text-xs font-mono text-orange-400 font-bold">
                  EXP
                </div>
              </div>
              <div className="text-center space-y-2">
                <p className="text-slate-200 font-medium text-lg">扩图中...</p>
                <p className="text-slate-500 text-sm">这可能需要几秒钟</p>
              </div>
            </div>
          </div>
        ) : isBatchError ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex flex-col items-center gap-4 text-center p-8 bg-slate-900/50 rounded-2xl border border-red-900/30">
              <AlertCircle size={48} className="text-red-500 opacity-80" />
              <div>
                <h3 className="text-lg font-bold text-slate-200">扩图失败</h3>
                <p className="text-sm text-red-400 mt-2 max-w-md">
                  {activeBatchMessage?.content || '未知错误'}
                </p>
              </div>
            </div>
          </div>
        ) : displayImages.length > 0 ? (
          <>
            <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden">
              <div
                className="flex-1 w-full flex items-center justify-center relative px-16 overflow-hidden"
                onMouseDown={isCompareMode ? undefined : canvas.handleMouseDown}
                onMouseMove={isCompareMode ? undefined : canvas.handleMouseMove}
                onMouseUp={isCompareMode ? undefined : canvas.handleMouseUp}
                onMouseLeave={isCompareMode ? undefined : canvas.handleMouseUp}
                style={{
                  cursor: isCompareMode
                    ? 'default'
                    : canvas.isDragging
                      ? 'grabbing'
                      : canvas.zoom > 1
                        ? 'grab'
                        : 'default',
                }}
              >
                <ImageCarouselArrows
                  itemCount={displayImages.length}
                  onPrev={handleCarouselPrev}
                  onNext={handleCarouselNext}
                />

                <div className="relative group max-w-full max-h-full flex items-center justify-center">
                  {isCompareMode && originalImageUrl && currentDisplayUrl ? (
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
                  ) : currentDisplayUrl ? (
                    <img
                      src={currentDisplayUrl}
                      className="block max-h-[70vh] max-w-full object-contain rounded-2xl shadow-2xl border border-slate-800/50 select-none"
                      style={canvas.canvasStyle}
                      onDoubleClick={() => onImageClick(currentDisplayUrl)}
                      alt={`扩图结果 ${carouselIndex + 1}`}
                      draggable={false}
                    />
                  ) : (
                    <div className="w-64 h-64 flex items-center justify-center text-slate-600 bg-slate-900 rounded-2xl">
                      <ImageIcon size={48} className="opacity-50" />
                    </div>
                  )}
                  {currentDisplayUrl && (
                    <ImageCanvasControls
                      variant="canvas"
                      mode="image-outpainting"
                      modeAware={false}
                      className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                      zoom={canvas.zoom}
                      onZoomIn={canvas.handleZoomIn}
                      onZoomOut={canvas.handleZoomOut}
                      onReset={canvas.handleReset}
                      onFullscreen={() => onImageClick(currentDisplayUrl)}
                      downloadUrl={currentDisplayUrl}
                      onToggleCompare={originalImageUrl ? toggleCompare : undefined}
                      isCompareMode={isCompareMode}
                      accentColor="orange"
                    />
                  )}
                </div>

                {canvas.zoom !== 1 && (
                  <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-slate-400 text-xs bg-black/60 px-3 py-1.5 rounded-full backdrop-blur pointer-events-none">
                    {Math.round(canvas.zoom * 100)}% · 拖拽移动 · 双击全屏
                  </div>
                )}
              </div>

              <ImageCarouselThumbnails
                items={carouselItems}
                currentIndex={carouselIndex}
                onSelect={handleCarouselSelect}
                accentTone="orange"
                panelClassName="flex items-center gap-3 py-4 px-4"
                counterClassName="ml-2 text-sm text-slate-400 font-mono"
              />
            </div>
          </>
        ) : activeImageUrl ? (
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
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
              <Expand size={48} className="opacity-20" />
              <div>
                <h3 className="text-xl font-bold text-slate-500 mb-2">Out-Paint Workspace</h3>
                <p className="text-sm opacity-60">在右侧上传图片，设置参数后点击扩图</p>
              </div>
            </div>
          </div>
        )}

        {displayImages.length > 1 && (
          <div className="absolute top-4 left-4 z-10 animate-[fadeIn_0.3s_ease-out] pointer-events-none">
            <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-xl">
              <Grid size={14} className="text-orange-400" />
              批次结果 ({displayImages.length})
            </div>
          </div>
        )}
      </div>

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
