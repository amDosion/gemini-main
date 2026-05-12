/**
 * Image Edit 主画布渲染组件。
 *
 * 已迁移到共享 ImageWorkspaceCanvas（components/common/ImageWorkspaceCanvas.tsx）。
 * 该组件保留为 ImageEditView 的视图特定包装：Wand2 + pink + 4-grid empty state。
 *
 * 1:1 行为保留——原始结构来自 `ImageEditView.tsx` L72-325。
 */

import React, { memo } from 'react';
import { Attachment } from '../../../types/types';
import { Crop, Layers, Palette, PenTool, Sparkles, Wand2 } from 'lucide-react';
import { ImageCarouselThumbnails } from '../../common/ImageCarouselControls';
import { ImageWorkspaceCanvas } from '../../common/ImageWorkspaceCanvas';

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

const EDIT_EMPTY_STATE = (
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
);

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
    carouselIndex,
    onCarouselPrev,
    onCarouselNext,
    onCarouselSelect,
    getStableUrl,
  }: ImageEditMainCanvasProps) => {
    return (
      <ImageWorkspaceCanvas
        loadingState={loadingState}
        isCompareMode={isCompareMode}
        activeAttachments={activeAttachments}
        activeImageUrl={activeImageUrl}
        originalImageUrl={originalImageUrl}
        zoom={zoom}
        isDragging={isDragging}
        canvasStyle={canvasStyle}
        onWheel={onWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onZoomIn={onZoomIn}
        onZoomOut={onZoomOut}
        onReset={onReset}
        onFullscreen={onFullscreen}
        onExpand={onExpand}
        onToggleCompare={onToggleCompare}
        headerIcon={Wand2}
        headerIconClassName="text-pink-400"
        headerLabel="Workspace"
        multiImageLabelPrefix="多图编辑"
        spinnerClassName="border-pink-500/30 border-t-pink-500"
        loadingText={{
          default: 'Processing Image...',
          uploading: '上传图片中...',
          loading: 'AI 正在处理图片...',
          streaming: '流式处理中...',
        }}
        compareConfig={{
          beforeLabel: '原图',
          afterLabel: '编辑结果',
          accentColor: 'pink',
        }}
        controlsAccentColor="pink"
        carousel={{
          carouselIndex,
          onCarouselPrev,
          onCarouselNext,
          onCarouselSelect,
          getStableUrl,
          renderThumbnails: ({ items, currentIndex, onSelect }) => (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20">
              <ImageCarouselThumbnails
                items={items}
                currentIndex={currentIndex}
                onSelect={onSelect}
                accentTone="pink"
                thumbnailSize={56}
                panelClassName="flex items-center gap-3 py-3 px-4 bg-black/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-xl"
                counterClassName="ml-2 text-xs text-slate-400 font-mono"
              />
            </div>
          ),
        }}
        emptyState={EDIT_EMPTY_STATE}
      />
    );
  }
);

ImageEditMainCanvas.displayName = 'ImageEditMainCanvas';
