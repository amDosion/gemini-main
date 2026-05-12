/**
 * ImageResultCanvas - 共享的"结果查看器"画布组件
 *
 * 1:1 抽离自 ImageGenView.tsx mainContent useMemo 与 expand/ExpandMainCanvas.tsx 的
 * 左侧画布区域。两者拥有相同骨架，按 props 配置颜色 / 控件 / 文案 / slot。
 *
 * 调用方：
 *   - components/views/ImageGenView.tsx          (image-gen, emerald, GEN 徽章)
 *   - components/views/expand/ExpandMainCanvas.tsx (image-outpainting, orange, EXP 徽章)
 *
 * 与 ImageWorkspaceCanvas（chat-edit 风格画布）的区别：
 *   - 控件位置：本组件 hover-revealed 在图片本身的 top-3 right-3
 *               ImageWorkspaceCanvas 在画布外侧 bottom-6 right-6
 *   - 缩略图位置：本组件嵌入到主图所在的 absolute inset-0 容器内
 *               ImageWorkspaceCanvas 由 slot 渲染
 *   - 头部 pill：本组件只在多图时显示"批次结果 (n)"
 *               ImageWorkspaceCanvas 始终显示 header pill
 *   - 状态分支：本组件支持 isBatchError / displayImages.length
 *               ImageWorkspaceCanvas 支持 isCompareMode / activeAttachments
 *
 * 分支顺序：loading → batch-error → compare-slot (可选) → carousel (displayImages) →
 *           source-preview-slot (可选) → empty-state
 */

import React, { memo, type ReactNode } from 'react';
import { AlertCircle, Grid, Image as ImageIcon } from 'lucide-react';
import { Attachment, AppMode } from '../../types/types';
import { ImageCanvasControls } from './ImageCanvasControls';
import {
  ImageCarouselArrows,
  ImageCarouselThumbnails,
  type CarouselMediaItem,
  type CarouselAccentTone,
} from './ImageCarouselControls';

type ResultAccentColor = 'pink' | 'orange' | 'emerald' | 'indigo';

export interface ResultCanvasControlsExtra {
  onEdit?: () => void;
  onExpand?: () => void;
  onFullscreen?: () => void;
  onToggleCompare?: () => void;
  isCompareMode?: boolean;
}

export interface ImageResultCanvasProps {
  // === 状态 ===
  /** loadingState !== 'idle' 时显示 spinner */
  loadingState: string;
  /** 批次错误：显示错误面板 */
  isBatchError: boolean | undefined;
  /** 错误标题（默认"生成失败"） */
  errorTitle?: string;
  /** 错误消息（来自 activeBatchMessage?.content） */
  errorMessage?: string;

  // === 图片数据 ===
  /** 当前批次的所有图片（带 url） */
  displayImages: Attachment[];
  /** 旋转木马项目（与 displayImages 一一对应，缩略图 alt 由调用方决定） */
  carouselItems: CarouselMediaItem[];
  /** 当前旋转木马索引 */
  carouselIndex: number;
  /** 翻页回调 */
  handleCarouselPrev: () => void;
  handleCarouselNext: () => void;
  handleCarouselSelect: (index: number) => void;
  /** 双击主图回调 */
  onImageClick: (url: string) => void;
  /** 主图 alt 生成器（默认 `图片 {idx+1}`） */
  altFor?: (idx: number) => string;

  // === 缩放 / 拖拽（来自 useImageCanvas） ===
  canvas: {
    zoom: number;
    isDragging: boolean;
    canvasStyle: React.CSSProperties;
    handleWheel: (e: React.WheelEvent) => void;
    handleMouseDown: (e: React.MouseEvent) => void;
    handleMouseMove: (e: React.MouseEvent) => void;
    handleMouseUp: () => void;
    handleZoomIn: (e?: React.MouseEvent) => void;
    handleZoomOut: (e?: React.MouseEvent) => void;
    handleReset: (e?: React.MouseEvent) => void;
  };

  // === 控件 (ImageCanvasControls) ===
  /** 模式（用于 mode-aware 按钮显示），透传给 ImageCanvasControls */
  mode: AppMode;
  /** 控件主题色 */
  accentColor: ResultAccentColor;
  /** 视图特定的操作回调（onEdit / onExpand / onToggleCompare / onFullscreen / isCompareMode） */
  controlsExtra?: ResultCanvasControlsExtra;

  // === Loading spinner 配置 ===
  /** spinner 颜色 class，e.g. "border-emerald-500/30 border-t-emerald-500" */
  spinnerColorClass: string;
  /** spinner 中心的徽章文本，e.g. "GEN" / "EXP" */
  spinnerBadgeText: string;
  /** 徽章文字颜色 class，e.g. "text-emerald-400" */
  spinnerBadgeColorClass: string;
  /** Loading 标题（默认"生成中..."） */
  loadingTitle?: string;
  /** Loading 副标题（默认"这可能需要几秒钟"） */
  loadingSubtitle?: string;
  /** Loading 包裹层额外 class（GenView 需 "max-w-lg w-full"，Expand 不需要） */
  loadingWrapperExtraClass?: string;

  // === 多图批次提示 pill 配置 ===
  /** "批次结果 (n)" 图标颜色 class，e.g. "text-emerald-400" */
  accentIconClass: string;

  // === 缩略图配置 ===
  /** 缩略图组件 accentTone，e.g. "emerald" / "orange" */
  carouselAccentTone: CarouselAccentTone;

  // === Slots ===
  /** 空状态（无图片、无错误、未 loading 时显示） */
  emptyState: ReactNode;
  /** 对比模式分支（仅 Expand 使用，渲染 <ImageCompare>；nullable） */
  compareSlot?: ReactNode;
  /** 源图预览分支（仅 Expand 使用，无 displayImages 但有 activeImageUrl 时显示；nullable） */
  sourcePreviewSlot?: ReactNode;
  /** Loading 容器内部额外内容（GenView 在 spinner 下方显示 inline ThinkingBlock） */
  loadingExtraContent?: ReactNode;
  /** Loading 结束后的浮动内容（GenView 在画布底部显示 ThinkingBlock 浮层） */
  floatingExtraContent?: ReactNode;

  /**
   * 滚轮 (onWheel) 监听目标：
   *   - 'outer'：监听最外层 wrapper（Expand 行为，loading/error/empty 状态也响应滚轮）
   *   - 'carousel'：仅在 displayImages.length > 0 的内层 carousel 容器监听（GenView 行为）
   * 默认 'carousel'。
   */
  wheelTarget?: 'outer' | 'carousel';
}

/**
 * 共享的"结果查看器"画布
 */
export const ImageResultCanvas = memo(
  ({
    loadingState,
    isBatchError,
    errorTitle = '生成失败',
    errorMessage,
    displayImages,
    carouselItems,
    carouselIndex,
    handleCarouselPrev,
    handleCarouselNext,
    handleCarouselSelect,
    onImageClick,
    altFor,
    canvas,
    mode,
    accentColor,
    controlsExtra,
    spinnerColorClass,
    spinnerBadgeText,
    spinnerBadgeColorClass,
    loadingTitle = '生成中...',
    loadingSubtitle = '这可能需要几秒钟',
    loadingWrapperExtraClass,
    accentIconClass,
    carouselAccentTone,
    emptyState,
    compareSlot,
    sourcePreviewSlot,
    loadingExtraContent,
    floatingExtraContent,
    wheelTarget = 'carousel',
  }: ImageResultCanvasProps) => {
    const isLoading = loadingState !== 'idle';
    const isCompareMode = controlsExtra?.isCompareMode ?? false;
    const currentImage = displayImages[carouselIndex];
    const currentUrl = currentImage?.url || null;

    const loadingWrapperClass = `flex flex-col items-center gap-6 p-8 rounded-3xl bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 shadow-2xl${
      loadingWrapperExtraClass ? ` ${loadingWrapperExtraClass}` : ''
    }`;

    const outerOnWheel =
      wheelTarget === 'outer'
        ? isCompareMode
          ? undefined
          : canvas.handleWheel
        : undefined;
    const carouselOnWheel =
      wheelTarget === 'carousel' ? canvas.handleWheel : undefined;

    return (
      <div
        className="flex-1 w-full h-full select-none flex flex-col relative"
        onWheel={outerOnWheel}
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

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className={loadingWrapperClass}>
              <div className="relative">
                <div
                  className={`w-20 h-20 border-4 ${spinnerColorClass} rounded-full animate-spin`}
                ></div>
                <div
                  className={`absolute inset-0 flex items-center justify-center text-xs font-mono ${spinnerBadgeColorClass} font-bold`}
                >
                  {spinnerBadgeText}
                </div>
              </div>
              <div className="text-center space-y-2">
                <p className="text-slate-200 font-medium text-lg">{loadingTitle}</p>
                <p className="text-slate-500 text-sm">{loadingSubtitle}</p>
              </div>
              {loadingExtraContent}
            </div>
          </div>
        ) : isBatchError ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex flex-col items-center gap-4 text-center p-8 bg-slate-900/50 rounded-2xl border border-red-900/30">
              <AlertCircle size={48} className="text-red-500 opacity-80" />
              <div>
                <h3 className="text-lg font-bold text-slate-200">{errorTitle}</h3>
                <p className="text-sm text-red-400 mt-2 max-w-md">
                  {errorMessage || '未知错误'}
                </p>
              </div>
            </div>
          </div>
        ) : displayImages.length > 0 ? (
          <>
            <div
              className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden"
              onWheel={carouselOnWheel}
            >
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
                  {compareSlot && isCompareMode ? (
                    compareSlot
                  ) : currentUrl ? (
                    <img
                      src={currentUrl}
                      className="block max-h-[70vh] max-w-full object-contain rounded-2xl shadow-2xl border border-slate-800/50 select-none"
                      style={canvas.canvasStyle}
                      onDoubleClick={() => onImageClick(currentUrl)}
                      alt={altFor ? altFor(carouselIndex) : `图片 ${carouselIndex + 1}`}
                      draggable={false}
                    />
                  ) : (
                    <div className="w-64 h-64 flex items-center justify-center text-slate-600 bg-slate-900 rounded-2xl">
                      <ImageIcon size={48} className="opacity-50" />
                    </div>
                  )}
                  {currentUrl && (
                    <ImageCanvasControls
                      variant="canvas"
                      mode={mode}
                      modeAware={false}
                      className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                      zoom={canvas.zoom}
                      onZoomIn={canvas.handleZoomIn}
                      onZoomOut={canvas.handleZoomOut}
                      onReset={canvas.handleReset}
                      onEdit={controlsExtra?.onEdit}
                      onExpand={controlsExtra?.onExpand}
                      onFullscreen={
                        controlsExtra?.onFullscreen ?? (() => onImageClick(currentUrl))
                      }
                      downloadUrl={currentUrl}
                      onToggleCompare={controlsExtra?.onToggleCompare}
                      isCompareMode={isCompareMode}
                      accentColor={accentColor}
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
                accentTone={carouselAccentTone}
                panelClassName="flex items-center gap-3 py-4 px-4"
                counterClassName="ml-2 text-sm text-slate-400 font-mono"
              />
            </div>
          </>
        ) : sourcePreviewSlot ? (
          sourcePreviewSlot
        ) : (
          emptyState
        )}

        {/* 批次结果 pill（多图时） */}
        {displayImages.length > 1 && (
          <div className="absolute top-4 left-4 z-10 animate-[fadeIn_0.3s_ease-out] pointer-events-none">
            <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-xl">
              <Grid size={14} className={accentIconClass} />
              批次结果 ({displayImages.length})
            </div>
          </div>
        )}

        {/* 浮动额外内容（GenView 在生成完成后展示 ThinkingBlock） */}
        {!isLoading && floatingExtraContent}
      </div>
    );
  }
);

ImageResultCanvas.displayName = 'ImageResultCanvas';
