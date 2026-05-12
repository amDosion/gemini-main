/**
 * ImageWorkspaceCanvas - 共享的图像编辑器画布组件
 *
 * 统一抽离自 ImageEditMainCanvas.tsx 与 ImageRecontextView / ImageInpaintingView /
 * ImageBackgroundEditView 的内联画布实现。1:1 行为保留。
 *
 * 调用方：
 *   - components/views/imageEdit/ImageEditMainCanvas.tsx
 *   - components/views/ImageRecontextView.tsx
 *   - components/views/ImageInpaintingView.tsx
 *   - components/views/ImageBackgroundEditView.tsx
 *
 * 支持的 4 种内置主体分支（按 loadingState / isCompareMode / 多图 / 单图 / 空 顺序）：
 *   1) loading - 旋转 spinner + 状态文本（spinner 颜色用 accent class 自定义）
 *   2) compare - <ImageCompare> 前后对比（标签/accent 由 props 控制）
 *   3) carousel - <ImageCarouselArrows> + <img> + 底部缩略图
 *   4) single image - 普通 <img> 显示
 *   5) empty - 由调用方通过 emptyState slot 提供
 *
 * 视图差异通过 props 控制：
 *   - 顶部 header pill 图标 / 标签 / 颜色
 *   - spinner 颜色 class（border-pink-500/30 等）
 *   - <ImageCompare> labels + accentColor
 *   - <ImageCanvasControls> accentColor
 *   - <ImageCarouselThumbnails> 渲染（slot：renderCarouselThumbnails）
 *   - empty state（slot：emptyState）
 *   - 多图模式标签（"多图编辑"/"重上下文结果"）
 */

import React, { memo, useMemo, type ReactNode } from 'react';
import { type LucideIcon } from 'lucide-react';
import { Attachment } from '../../types/types';
import { ImageCanvasControls } from './ImageCanvasControls';
import { ImageCarouselArrows, type CarouselMediaItem } from './ImageCarouselControls';
import { ImageCompare } from './ImageCompare';

export type WorkspaceAccentColor = 'pink' | 'orange' | 'emerald' | 'indigo';

export interface WorkspaceCompareConfig {
  beforeLabel: string;
  afterLabel: string;
  accentColor: WorkspaceAccentColor;
}

export interface WorkspaceLoadingTextMap {
  /** 默认 fallback，用于 loadingState='processing' 等未覆盖的情况 */
  default: string;
  uploading?: string;
  loading?: string;
  streaming?: string;
}

export interface ImageWorkspaceCanvasProps {
  // === 状态 ===
  loadingState: string;
  isCompareMode: boolean;
  activeAttachments: Attachment[];
  activeImageUrl: string | null;
  originalImageUrl: string | null;

  // === 缩放 / 拖拽 ===
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

  // === 头部 pill ===
  headerIcon: LucideIcon;
  /** 头部图标 className（仅颜色，e.g. "text-pink-400"） */
  headerIconClassName: string;
  /** 主标签，e.g. "Workspace" / "Recontext Editor" */
  headerLabel: string;
  /** 来源预览标签（默认 "Source Preview"） */
  sourcePreviewLabel?: string;
  /** 对比模式标签（默认 "对比模式"） */
  compareModeLabel?: string;
  /** 多图模式标签前缀，e.g. "多图编辑" / "重上下文结果"。提供则启用计数显示 */
  multiImageLabelPrefix?: string;

  // === Loading spinner ===
  /** spinner 颜色 class，e.g. "border-pink-500/30 border-t-pink-500" */
  spinnerClassName: string;
  /** Loading 状态对应的文本映射 */
  loadingText: WorkspaceLoadingTextMap;

  // === Compare ===
  compareConfig: WorkspaceCompareConfig;

  // === Controls ===
  controlsAccentColor: WorkspaceAccentColor;

  // === Carousel（可选） ===
  /** 提供则启用旋转木马模式 */
  carousel?: {
    carouselIndex: number;
    onCarouselPrev: () => void;
    onCarouselNext: () => void;
    onCarouselSelect: (index: number) => void;
    getStableUrl: (att: Attachment) => string | null;
    /** 缩略图 alt 文本生成器（默认 `缩略图 {idx+1}`） */
    altFor?: (idx: number) => string;
    /** 渲染底部缩略图 panel（覆盖默认） */
    renderThumbnails?: (params: {
      items: CarouselMediaItem[];
      currentIndex: number;
      onSelect: (index: number) => void;
    }) => ReactNode;
  };

  // === Empty state ===
  emptyState: ReactNode;

  // === 可选额外头部内容（如 Expand 的 "批次结果 (n)" pill） ===
  extraHeaderContent?: ReactNode;
}

/**
 * 共享的"图像工作区"画布组件
 */
export const ImageWorkspaceCanvas = memo(
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
    headerIcon: HeaderIcon,
    headerIconClassName,
    headerLabel,
    sourcePreviewLabel = 'Source Preview',
    compareModeLabel = '对比模式',
    multiImageLabelPrefix,
    spinnerClassName,
    loadingText,
    compareConfig,
    controlsAccentColor,
    carousel,
    emptyState,
    extraHeaderContent,
  }: ImageWorkspaceCanvasProps) => {
    const cursor = isCompareMode
      ? 'default'
      : isDragging
        ? 'grabbing'
        : activeImageUrl
          ? 'grab'
          : 'default';

    const carouselEnabled = !!carousel;
    const isMultiImageMode = carouselEnabled && activeAttachments.length > 1;
    const currentDisplayUrl =
      carouselEnabled && isMultiImageMode && activeAttachments[carousel!.carouselIndex]
        ? activeAttachments[carousel!.carouselIndex].url ||
          activeAttachments[carousel!.carouselIndex].tempUrl ||
          carousel!.getStableUrl(activeAttachments[carousel!.carouselIndex])
        : activeImageUrl;

    const carouselItems = useMemo<CarouselMediaItem[]>(() => {
      if (!carouselEnabled) return [];
      const altFor = carousel!.altFor || ((idx: number) => `缩略图 ${idx + 1}`);
      return activeAttachments.map((att, idx) => {
        const thumbUrl = att.url || att.tempUrl || carousel!.getStableUrl(att);
        return {
          id: att.id || `${idx}`,
          url: thumbUrl,
          thumbUrl,
          alt: altFor(idx),
        };
      });
    }, [activeAttachments, carouselEnabled, carousel]);

    // 计算头部 label
    const computedHeaderLabel = isCompareMode
      ? compareModeLabel
      : isMultiImageMode && multiImageLabelPrefix
        ? `${multiImageLabelPrefix} (${carousel!.carouselIndex + 1}/${activeAttachments.length})`
        : activeAttachments.length > 0 && activeImageUrl === activeAttachments[0].url
          ? sourcePreviewLabel
          : headerLabel;

    // 计算 loading 状态文本
    const statusText =
      (loadingState === 'uploading' && loadingText.uploading) ||
      (loadingState === 'loading' && loadingText.loading) ||
      (loadingState === 'streaming' && loadingText.streaming) ||
      loadingText.default;

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
            <HeaderIcon size={12} className={headerIconClassName} />
            {computedHeaderLabel}
            <span className="opacity-50">|</span>
            <span className="font-mono text-[10px] opacity-70">{Math.round(zoom * 100)}%</span>
          </div>
        </div>

        {extraHeaderContent}

        {/* Main Image Display with Transformations */}
        <div className="flex-1 flex items-center justify-center p-0 w-full relative overflow-hidden">
          {loadingState !== 'idle' ? (
            <div className="flex flex-col items-center gap-4 pointer-events-none">
              <div className="relative">
                <div
                  className={`w-20 h-20 border-4 ${spinnerClassName} rounded-full animate-spin`}
                ></div>
              </div>
              <p className="text-slate-400 animate-pulse">{statusText}</p>
            </div>
          ) : isCompareMode && originalImageUrl && currentDisplayUrl ? (
            <div
              className="relative shadow-2xl transition-transform duration-75 ease-out"
              style={canvasStyle}
            >
              <ImageCompare
                beforeImage={originalImageUrl}
                afterImage={currentDisplayUrl}
                beforeLabel={compareConfig.beforeLabel}
                afterLabel={compareConfig.afterLabel}
                accentColor={compareConfig.accentColor}
                className="max-w-none rounded-lg border border-slate-800"
                style={{ maxHeight: '80vh', maxWidth: '80vw' }}
              />
            </div>
          ) : currentDisplayUrl ? (
            <>
              {carouselEnabled && (
                <ImageCarouselArrows
                  itemCount={activeAttachments.length}
                  onPrev={carousel!.onCarouselPrev}
                  onNext={carousel!.onCarouselNext}
                />
              )}
              <div
                className="relative shadow-2xl group transition-transform duration-75 ease-out"
                style={canvasStyle}
              >
                <img
                  src={currentDisplayUrl}
                  className="max-w-none rounded-lg border border-slate-800 pointer-events-none"
                  style={
                    carouselEnabled
                      ? { maxHeight: '70vh', maxWidth: '70vw' }
                      : { maxHeight: '80vh', maxWidth: '80vw' }
                  }
                  alt="Main Canvas"
                />
              </div>
            </>
          ) : (
            emptyState
          )}
        </div>

        {/* 底部缩略图导航（多图时显示） */}
        {carouselEnabled &&
          isMultiImageMode &&
          loadingState === 'idle' &&
          carousel!.renderThumbnails &&
          carousel!.renderThumbnails({
            items: carouselItems,
            currentIndex: carousel!.carouselIndex,
            onSelect: carousel!.onCarouselSelect,
          })}

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
              accentColor={controlsAccentColor}
            />
          </div>
        )}
      </div>
    );
  }
);

ImageWorkspaceCanvas.displayName = 'ImageWorkspaceCanvas';
