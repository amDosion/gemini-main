/**
 * Image Edit 主画布渲染组件。
 *
 * 1:1 抽离自 `ImageEditView.tsx` L72-325（< 800 行合规拆分）。
 */

import React, { memo, useMemo } from 'react';
import { Attachment } from '../../../types/types';
import { Crop, Layers, Palette, PenTool, Sparkles, Wand2 } from 'lucide-react';
import { ImageCanvasControls } from '../../common/ImageCanvasControls';
import {
  ImageCarouselArrows,
  ImageCarouselThumbnails,
  type CarouselMediaItem,
} from '../../common/ImageCarouselControls';
import { ImageCompare } from '../../common/ImageCompare';

export type ImageEditMainCanvasProps = {
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
  // ✅ 旋转木马支持（多图预览）
  carouselIndex: number;
  onCarouselPrev: () => void;
  onCarouselNext: () => void;
  onCarouselSelect: (index: number) => void;
  getStableUrl: (att: Attachment) => string | null;
};

export const ImageEditMainCanvas = memo(
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
    // ✅ 旋转木马支持
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

    // ✅ 判断是否为多图模式（用户上传了多个附件）
    const isMultiImageMode = activeAttachments.length > 1;
    // 当前显示的图片 URL（优先使用 att.url，与 AttachmentPreview 一致）
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
            alt: `缩略图 ${idx + 1}`,
          };
        }),
      [activeAttachments, getStableUrl]
    );

    return (
      // RIGHT MAIN: Result / Canvas
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
            <Wand2 size={12} className="text-pink-400" />
            {isCompareMode
              ? '对比模式'
              : isMultiImageMode
                ? `多图编辑 (${carouselIndex + 1}/${activeAttachments.length})`
                : activeAttachments.length > 0 && activeImageUrl === activeAttachments[0].url
                  ? 'Source Preview'
                  : 'Workspace'}
            <span className="opacity-50">|</span>
            <span className="font-mono text-[10px] opacity-70">{Math.round(zoom * 100)}%</span>
          </div>
        </div>

        {/* Main Image Display with Transformations */}
        <div className="flex-1 flex items-center justify-center p-0 w-full relative overflow-hidden">
          {loadingState !== 'idle' ? (
            (() => {
              // 根据 loadingState 显示不同的过程信息
              let statusText = 'Processing Image...';

              if (loadingState === 'uploading') {
                statusText = '上传图片中...';
              } else if (loadingState === 'loading') {
                statusText = 'AI 正在处理图片...';
              } else if (loadingState === 'streaming') {
                statusText = '流式处理中...';
              }

              return (
                <div className="flex flex-col items-center gap-4 pointer-events-none">
                  <div className="relative">
                    <div className="w-20 h-20 border-4 border-pink-500/30 border-t-pink-500 rounded-full animate-spin"></div>
                  </div>
                  <p className="text-slate-400 animate-pulse">{statusText}</p>
                </div>
              );
            })()
          ) : isCompareMode && originalImageUrl && activeImageUrl ? (
            // 对比模式
            <div
              className="relative shadow-2xl transition-transform duration-75 ease-out"
              style={canvasStyle}
            >
              <ImageCompare
                beforeImage={originalImageUrl}
                afterImage={activeImageUrl}
                beforeLabel="原图"
                afterLabel="编辑结果"
                accentColor="pink"
                className="max-w-none rounded-lg border border-slate-800"
                style={{ maxHeight: '80vh', maxWidth: '80vw' }}
              />
            </div>
          ) : currentDisplayUrl ? (
            // ✅ 普通模式 / 多图旋转木马模式
            <>
              <ImageCarouselArrows
                itemCount={activeAttachments.length}
                onPrev={onCarouselPrev}
                onNext={onCarouselNext}
              />

              {/* 主图展示 */}
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
              <Crop size={48} className="opacity-20" />
              <div>
                <h3 className="text-xl font-bold text-slate-500 mb-2">Editor Workspace</h3>
                <p className="text-sm opacity-60 mb-4">
                  Attach an image below to start. Gemini allows advanced conversational editing:
                </p>
                <div className="grid grid-cols-2 gap-2 text-left text-xs opacity-50">
                  <div className="flex items-center gap-2">
                    <Palette size={12} /> Style Transfer
                  </div>
                  <div className="flex items-center gap-2">
                    <Sparkles size={12} /> Inpainting/Replacing
                  </div>
                  <div className="flex items-center gap-2">
                    <PenTool size={12} /> Sketch to Image
                  </div>
                  <div className="flex items-center gap-2">
                    <Layers size={12} /> Composition
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ✅ 底部缩略图导航（多图时显示）- 移到图片区域内部 */}
          {isMultiImageMode && loadingState === 'idle' && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20">
              <ImageCarouselThumbnails
                items={carouselItems}
                currentIndex={carouselIndex}
                onSelect={onCarouselSelect}
                accentTone="pink"
                thumbnailSize={56}
                panelClassName="flex items-center gap-3 py-3 px-4 bg-black/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-xl"
                counterClassName="ml-2 text-xs text-slate-400 font-mono"
              />
            </div>
          )}
        </div>

        {/* 浮动控制按钮 */}
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
              accentColor="pink"
            />
          </div>
        )}
      </div>
    );
  }
);

ImageEditMainCanvas.displayName = 'ImageEditMainCanvas';
