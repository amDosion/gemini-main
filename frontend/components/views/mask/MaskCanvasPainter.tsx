/**
 * Mask 编辑器主画布渲染组件。
 *
 * 1:1 抽离自 `ImageMaskEditView.tsx` 内部 ImageEditMainCanvas memo（L70-589）
 * （JIRA-frontend-view-decomposition.md P0 #2 Step 5）。
 *
 * 重命名：ImageEditMainCanvas → MaskCanvasPainter（聚焦于 mask 画布绘制语义；
 * 注：与 ImageEditView 内同名组件无关 — 那里也有独立的 ImageEditMainCanvas）。
 *
 * 职责：
 * - 棋盘背景 + 标题胶囊（Mask Editor / Source Preview / 对比模式）
 * - 主图（imageRef）+ 自动 mask 覆盖层（auto background/foreground/semantic）+
 *   状态徽章（loading / error / notice）
 * - 矩形选区可视化（普通模式 vs 反转模式 SVG mask）+ 撤销序号按钮
 * - 选区/画笔/橡皮擦交互层 + 自定义圆形光标（brushCursorRef DOM 直更新）
 * - 画笔实时绘制 canvas（displayCanvasRef）；持久化 mask canvas 由父组件管理
 * - 底部 MaskToolbar（Step 4 抽离）+ 右下浮动 ImageCanvasControls
 * - 右下角小窗 mask 预览缩略图
 *
 * 1:1 行为等价：UI 类名/事件/DOM 结构均保留。
 */

import React, { memo, useMemo } from 'react';
import { Crop, AlertCircle, Wand2, Loader2 } from 'lucide-react';
import { Attachment } from '../../../types/types';
import { CachedImage } from '../../common/CachedImage';
import { ImageCompare } from '../../common/ImageCompare';
import { ImageCanvasControls } from '../../common/ImageCanvasControls';
import {
  type MaskTool,
  type MaskMode,
  type SelectionRect,
  getMaskModeDisplayLabel,
} from '../../../utils/maskHelpers';
import { MaskToolbar } from './MaskToolbar';
import { MaskPreviewImage } from './MaskPreviewImage';

export type MaskCanvasPainterProps = {
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
  // Mask 工具栏支持
  activeMaskTool: MaskTool;
  onMaskToolChange: (tool: MaskTool) => void;
  brushSize: number;
  onBrushSizeChange: (size: number) => void;
  // Mask 自动提取模式（Vertex AI mask_mode）
  maskMode: MaskMode;
  onMaskModeChange: (mode: MaskMode) => void;
  onImportMask?: () => void;
  onClearMask?: () => void;
  isPreviewingMask?: boolean;
  // Mask 反转（前景/背景切换）
  isMaskInverted: boolean;
  onToggleMaskInvert: () => void;
  // 选区和 Mask 预览支持（支持多个矩形）
  selectionRects: SelectionRect[];
  currentSelectionRect: SelectionRect | null;
  onSelectionStart: (e: React.MouseEvent) => void;
  onSelectionMove: (e: React.MouseEvent) => void;
  onSelectionEnd: () => void;
  onDeleteSelection: (index: number) => void;
  maskPreviewUrl: string | null;
  maskPreviewNotice: string | null;
  maskPreviewError: string | null;
  imageRef: React.RefObject<HTMLImageElement | null>;
  // 画笔/橡皮擦绑定支持
  onBrushStart: (e: React.MouseEvent) => void;
  onBrushMove: (e: React.MouseEvent) => void;
  onBrushEnd: () => void;
  isPainting: boolean;
  // 画笔绘制的 mask canvas URL
  maskCanvasUrl: string | null;
  // 画笔光标 ref（直接 DOM 更新，避免 React 重渲染）
  brushCursorRef: React.RefObject<HTMLDivElement | null>;
  onBrushCursorMove: (pos: { x: number; y: number } | null) => void;
  // 显示用的 canvas ref（用于直接 DOM 更新，避免 React 重渲染）
  displayCanvasRef: React.RefObject<HTMLCanvasElement | null>;
};

export const MaskCanvasPainter = memo(
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
    activeMaskTool,
    onMaskToolChange,
    brushSize,
    onBrushSizeChange,
    maskMode,
    onMaskModeChange,
    onImportMask,
    onClearMask,
    isPreviewingMask,
    isMaskInverted,
    onToggleMaskInvert,
    selectionRects,
    currentSelectionRect,
    onSelectionStart,
    onSelectionMove,
    onSelectionEnd,
    onDeleteSelection,
    maskPreviewUrl,
    maskPreviewNotice,
    maskPreviewError,
    imageRef,
    onBrushStart,
    onBrushMove,
    onBrushEnd,
    isPainting,
    maskCanvasUrl,
    brushCursorRef,
    onBrushCursorMove,
    displayCanvasRef,
  }: MaskCanvasPainterProps) => {
    // 根据当前工具设置光标样式
    const cursor = useMemo(() => {
      if (isCompareMode) return 'default';
      if (!activeImageUrl) return 'default';

      switch (activeMaskTool) {
        case 'move':
          return isDragging ? 'grabbing' : 'grab';
        case 'brush':
        case 'eraser':
        case 'select':
        default:
          return 'crosshair';
      }
    }, [isCompareMode, activeImageUrl, activeMaskTool, isDragging]);

    const isAutoMaskMode = maskMode !== 'MASK_MODE_USER_PROVIDED';
    const maskModeLabel = getMaskModeDisplayLabel(maskMode);

    return (
      <div
        className="flex-1 w-full h-full select-none flex flex-col relative"
        onWheel={isCompareMode ? undefined : onWheel}
        onMouseDown={isCompareMode || activeMaskTool !== 'move' ? undefined : onMouseDown}
        onMouseMove={isCompareMode || activeMaskTool !== 'move' ? undefined : onMouseMove}
        onMouseUp={isCompareMode || activeMaskTool !== 'move' ? undefined : onMouseUp}
        onMouseLeave={isCompareMode || activeMaskTool !== 'move' ? undefined : onMouseUp}
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
            <Crop size={12} className="text-purple-400" />
            {isCompareMode
              ? '对比模式'
              : activeAttachments.length > 0 && activeImageUrl === activeAttachments[0].url
                ? 'Source Preview'
                : 'Mask Editor'}
            <span className="opacity-50">|</span>
            <span className="font-mono text-[10px] opacity-70">{Math.round(zoom * 100)}%</span>
          </div>
        </div>

        {/* Main Image Display */}
        <div className="flex-1 flex items-center justify-center p-0 w-full h-full relative">
          {loadingState !== 'idle' ? (
            (() => {
              let statusText = 'Processing Image...';
              if (loadingState === 'uploading') {
                statusText = '上传图片中...';
              } else if (loadingState === 'loading') {
                statusText = 'Mask 编辑中，正在处理遮罩区域...';
              } else if (loadingState === 'streaming') {
                statusText = '流式处理中...';
              }

              return (
                <div className="flex flex-col items-center gap-4 pointer-events-none">
                  <div className="relative">
                    <div className="w-20 h-20 border-4 border-purple-500/30 border-t-purple-500 rounded-full animate-spin"></div>
                  </div>
                  <p className="text-slate-400 animate-pulse">{statusText}</p>
                </div>
              );
            })()
          ) : isCompareMode && originalImageUrl && activeImageUrl ? (
            <div
              className="relative shadow-2xl transition-transform duration-75 ease-out"
              style={canvasStyle}
            >
              <ImageCompare
                beforeImage={originalImageUrl}
                afterImage={activeImageUrl}
                beforeLabel="原图"
                afterLabel="Mask 编辑结果"
                accentColor="indigo"
                className="max-w-none rounded-lg border border-slate-800"
                style={{ maxHeight: '80vh', maxWidth: '80vw' }}
              />
            </div>
          ) : activeImageUrl ? (
            <div
              className="relative shadow-2xl group transition-transform duration-75 ease-out"
              style={canvasStyle}
            >
              <CachedImage
                ref={imageRef}
                source={{
                  url: activeImageUrl,
                  mimeType: 'image/png',
                }}
                src={activeImageUrl}
                rawFallbackDelayMs={300}
                className="max-w-none rounded-lg border border-slate-800"
                style={{ maxHeight: '80vh', maxWidth: '80vw' }}
                alt="Main Canvas"
              />
              {/* 自动 Mask 主画布反馈层 */}
              {isAutoMaskMode && maskPreviewUrl && (
                <div className="absolute inset-0 rounded-lg pointer-events-none overflow-hidden">
                  <MaskPreviewImage
                    src={maskPreviewUrl}
                    alt={`${maskModeLabel} Mask 覆盖层`}
                    className="absolute inset-0 w-full h-full object-fill opacity-60"
                    style={{
                      mixBlendMode: 'screen',
                      filter: 'sepia(1) saturate(5) hue-rotate(190deg) contrast(1.2)',
                    }}
                  />
                  <div className="absolute top-3 right-3 rounded-full border border-purple-400/40 bg-purple-950/85 px-2.5 py-1 text-[11px] font-medium text-purple-100 shadow-lg">
                    {maskModeLabel} Mask 已应用
                  </div>
                </div>
              )}
              {isAutoMaskMode && isPreviewingMask && (
                <div className="absolute inset-0 rounded-lg pointer-events-none overflow-hidden">
                  <div className="absolute inset-0 bg-purple-500/10 animate-pulse" />
                  <div className="absolute top-3 right-3 flex items-center gap-1.5 rounded-full border border-purple-400/40 bg-purple-950/85 px-2.5 py-1 text-[11px] font-medium text-purple-100 shadow-lg">
                    <Loader2 size={12} className="animate-spin" />
                    正在提取 {maskModeLabel} Mask
                  </div>
                </div>
              )}
              {isAutoMaskMode && maskPreviewError && !isPreviewingMask && !maskPreviewUrl && (
                <div className="absolute top-3 right-3 max-w-[260px] rounded-lg border border-rose-500/40 bg-rose-950/90 px-3 py-2 text-[11px] text-rose-100 shadow-lg">
                  <div className="flex items-start gap-2">
                    <AlertCircle size={13} className="mt-0.5 flex-shrink-0 text-rose-300" />
                    <span>{maskPreviewError}</span>
                  </div>
                </div>
              )}
              {isAutoMaskMode &&
                maskPreviewNotice &&
                !isPreviewingMask &&
                !maskPreviewUrl &&
                !maskPreviewError && (
                  <div className="absolute top-3 right-3 max-w-[300px] rounded-lg border border-purple-400/40 bg-purple-950/90 px-3 py-2 text-[11px] text-purple-100 shadow-lg">
                    <div className="flex items-start gap-2">
                      <Wand2 size={13} className="mt-0.5 flex-shrink-0 text-purple-300" />
                      <span>{maskPreviewNotice}</span>
                    </div>
                  </div>
                )}
              {/* Mask 可视化层 - 支持矩形选区和画笔绘制 */}
              {(selectionRects.length > 0 || maskCanvasUrl) && (
                <div className="absolute inset-0 rounded-lg pointer-events-none overflow-hidden">
                  {/* 画笔绘制的 mask 层 */}
                  <canvas
                    ref={displayCanvasRef}
                    className="absolute inset-0 w-full h-full"
                    style={{
                      opacity: isMaskInverted ? 0 : 0.3,
                      display: isPainting || maskCanvasUrl ? 'block' : 'none',
                    }}
                  />
                  {isMaskInverted ? (
                    /* 反转模式：外部蓝色，使用 SVG mask 实现 */
                    <svg className="absolute inset-0 w-full h-full">
                      <defs>
                        <mask id="invertMask">
                          {/* 白色背景 = 可见 */}
                          <rect x="0" y="0" width="100%" height="100%" fill="white" />
                          {/* 黑色矩形 = 透明（挖洞） */}
                          {selectionRects.map((rect, index) => (
                            <rect
                              key={index}
                              x={Math.min(rect.startX, rect.endX)}
                              y={Math.min(rect.startY, rect.endY)}
                              width={Math.abs(rect.endX - rect.startX)}
                              height={Math.abs(rect.endY - rect.startY)}
                              fill="black"
                            />
                          ))}
                        </mask>
                      </defs>
                      <rect
                        x="0"
                        y="0"
                        width="100%"
                        height="100%"
                        fill="rgba(59, 130, 246, 0.3)"
                        mask="url(#invertMask)"
                      />
                      {selectionRects.map((rect, index) => (
                        <rect
                          key={`border-${index}`}
                          x={Math.min(rect.startX, rect.endX)}
                          y={Math.min(rect.startY, rect.endY)}
                          width={Math.abs(rect.endX - rect.startX)}
                          height={Math.abs(rect.endY - rect.startY)}
                          fill="none"
                          stroke="#3b82f6"
                          strokeWidth="2"
                        />
                      ))}
                    </svg>
                  ) : (
                    /* 正常模式：内部蓝色 */
                    selectionRects.map((rect, index) => (
                      <div
                        key={index}
                        className="absolute"
                        style={{
                          left: Math.min(rect.startX, rect.endX),
                          top: Math.min(rect.startY, rect.endY),
                          width: Math.abs(rect.endX - rect.startX),
                          height: Math.abs(rect.endY - rect.startY),
                          border: '2px solid #3b82f6',
                          backgroundColor: 'rgba(59, 130, 246, 0.3)',
                        }}
                      />
                    ))
                  )}
                </div>
              )}
              {/* 选区绘制交互层 - 仅在 select 工具激活时启用 */}
              {activeMaskTool === 'select' && (
                <div
                  className="absolute inset-0 rounded-lg"
                  style={{ cursor: 'crosshair' }}
                  onMouseDown={onSelectionStart}
                  onMouseMove={onSelectionMove}
                  onMouseUp={onSelectionEnd}
                  onMouseLeave={onSelectionEnd}
                >
                  {currentSelectionRect && (
                    <div
                      className="absolute"
                      style={{
                        left: Math.min(currentSelectionRect.startX, currentSelectionRect.endX),
                        top: Math.min(currentSelectionRect.startY, currentSelectionRect.endY),
                        width: Math.abs(currentSelectionRect.endX - currentSelectionRect.startX),
                        height: Math.abs(currentSelectionRect.endY - currentSelectionRect.startY),
                        border: '2px dashed #60a5fa',
                        backgroundColor: 'rgba(96, 165, 250, 0.2)',
                      }}
                    />
                  )}
                </div>
              )}
              {/* 画笔/橡皮擦交互层 */}
              {(activeMaskTool === 'brush' || activeMaskTool === 'eraser') && (
                <div
                  className="absolute inset-0 rounded-lg"
                  style={{ cursor: 'none' }}
                  onMouseDown={onBrushStart}
                  onMouseMove={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    onBrushCursorMove({
                      x: (e.clientX - rect.left) / zoom,
                      y: (e.clientY - rect.top) / zoom,
                    });
                    onBrushMove(e);
                  }}
                  onMouseUp={onBrushEnd}
                  onMouseLeave={() => {
                    onBrushCursorMove(null);
                    onBrushEnd();
                  }}
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    onBrushCursorMove({
                      x: (e.clientX - rect.left) / zoom,
                      y: (e.clientY - rect.top) / zoom,
                    });
                  }}
                >
                  {/* 自定义圆形光标 */}
                  <div
                    ref={brushCursorRef}
                    className="pointer-events-none absolute rounded-full border-2"
                    style={{
                      display: 'none',
                      width: brushSize,
                      height: brushSize,
                      borderColor: activeMaskTool === 'eraser' ? '#f87171' : '#3b82f6',
                      backgroundColor:
                        activeMaskTool === 'eraser'
                          ? 'rgba(248, 113, 113, 0.2)'
                          : 'rgba(59, 130, 246, 0.2)',
                    }}
                  />
                </div>
              )}
              {/* 序号圆点/撤销按钮 - 放在所有交互层之后，确保可点击 */}
              {selectionRects.length > 0 &&
                selectionRects.map((rect, index) => (
                  <button
                    key={`btn-${index}`}
                    onMouseDown={(e) => {
                      e.stopPropagation();
                      e.preventDefault();
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSelection(index);
                    }}
                    className="absolute w-5 h-5 bg-blue-500 hover:bg-red-500 rounded-full flex items-center justify-center text-[10px] text-white font-bold cursor-pointer transition-colors z-30"
                    style={{
                      left: Math.min(rect.startX, rect.endX) - 10,
                      top: Math.min(rect.startY, rect.endY) - 10,
                    }}
                    title="点击撤销此选区"
                  >
                    {index + 1}
                  </button>
                ))}
            </div>
          ) : (
            <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
              <Crop size={48} className="opacity-20" />
              <div>
                <h3 className="text-xl font-bold text-slate-500 mb-2">Mask Editor</h3>
                <p className="text-sm opacity-60">上传图片并指定遮罩区域进行编辑</p>
              </div>
            </div>
          )}

          {/* Mask 工具栏 - 底部居中（始终显示，不依赖图片）— P0 #2 Step 4 抽离 */}
          <MaskToolbar
            loadingState={loadingState}
            maskMode={maskMode}
            onMaskModeChange={onMaskModeChange}
            isPreviewingMask={isPreviewingMask}
            onImportMask={onImportMask}
            onClearMask={onClearMask}
            activeMaskTool={activeMaskTool}
            onMaskToolChange={onMaskToolChange}
            isMaskInverted={isMaskInverted}
            onToggleMaskInvert={onToggleMaskInvert}
            brushSize={brushSize}
            onBrushSizeChange={onBrushSizeChange}
          />

          {/* Mask 预览 - 画布右下角浮动显示 */}
          {maskPreviewUrl && (
            <div className="absolute bottom-20 right-4 z-20">
              <div className="bg-slate-800/95 backdrop-blur-md rounded-xl border border-slate-700/50 shadow-xl p-3">
                <div className="text-xs text-slate-400 mb-2 font-medium">
                  {isAutoMaskMode ? `${maskModeLabel} Mask` : 'Mask Preview'}
                </div>
                <div className="relative w-24 h-24 rounded-lg overflow-hidden border border-slate-600 bg-black">
                  <MaskPreviewImage
                    src={maskPreviewUrl}
                    alt="Mask Preview"
                    className="w-full h-full object-contain"
                  />
                </div>
                <div className="text-[10px] text-slate-500 mt-2">
                  {isAutoMaskMode ? '已同步到主画布' : `${selectionRects.length} 个选区`}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Floating Controls */}
        {activeImageUrl && (
          <div className="absolute bottom-6 right-6 z-20">
            <ImageCanvasControls
              zoom={zoom}
              onZoomIn={onZoomIn}
              onZoomOut={onZoomOut}
              onReset={onReset}
              onFullscreen={onFullscreen}
              downloadUrl={activeImageUrl}
              onExpand={onExpand}
              onToggleCompare={onToggleCompare}
              isCompareMode={isCompareMode}
              accentColor="indigo"
            />
          </div>
        )}
      </div>
    );
  }
);

MaskCanvasPainter.displayName = 'MaskCanvasPainter';
