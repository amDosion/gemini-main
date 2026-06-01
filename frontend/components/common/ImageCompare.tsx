/**
 * ImageCompare 组件
 * 
 * 图片对比组件，支持滑块对比模式
 * 用于对比原图和编辑/扩图后的图片
 * 
 * 注意：为确保对比效果正确，两张图片会被统一缩放到相同的显示区域
 */

import React, { useState, useRef, useCallback } from 'react';
import { CachedImage } from './CachedImage';

export interface ImageCompareProps {
  /** 原图 URL */
  beforeImage: string;
  /** 结果图 URL */
  afterImage: string;
  /** 原图标签，默认 "原图" */
  beforeLabel?: string;
  /** 结果图标签，默认 "结果" */
  afterLabel?: string;
  /** 初始滑块位置（0-100），默认 50 */
  initialPosition?: number;
  /** 自定义类名 */
  className?: string;
  /** 自定义样式 */
  style?: React.CSSProperties;
  /** 主题色 */
  accentColor?: 'pink' | 'orange' | 'emerald' | 'indigo';
}

export const ImageCompare: React.FC<ImageCompareProps> = ({
  beforeImage,
  afterImage,
  beforeLabel = '原图',
  afterLabel = '结果',
  initialPosition = 50,
  className = '',
  style,
  accentColor = 'pink',
}) => {
  const [sliderPosition, setSliderPosition] = useState(initialPosition);
  const [beforeOpacity, setBeforeOpacity] = useState(100);
  const [isDragging, setIsDragging] = useState(false);
  const [imageDimensions, setImageDimensions] = useState<{
    before: { width: number; height: number } | null;
    after: { width: number; height: number } | null;
  }>({ before: null, after: null });
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  const accentColors = {
    pink: 'bg-pink-500',
    orange: 'bg-orange-500',
    emerald: 'bg-emerald-500',
    indigo: 'bg-indigo-500',
  };
  const accentHexColors = {
    pink: '#ec4899',
    orange: '#f97316',
    emerald: '#10b981',
    indigo: '#6366f1',
  };

  // 计算统一的显示比例（以结果图为基准）
  const getUnifiedAspectRatio = useCallback(() => {
    if (!imageDimensions.after) return 1;
    return imageDimensions.after.width / imageDimensions.after.height;
  }, [imageDimensions.after]);

  // 计算滑块位置
  const updateSliderPosition = useCallback((clientX: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = clientX - rect.left;
    const percentage = Math.min(Math.max((x / rect.width) * 100, 0), 100);
    setSliderPosition(percentage);
  }, []);

  const setDraggingState = useCallback((nextDragging: boolean) => {
    draggingRef.current = nextDragging;
    setIsDragging(nextDragging);
  }, []);

  const releasePointerCapture = useCallback((target: HTMLDivElement, pointerId: number) => {
    if (typeof target.releasePointerCapture !== 'function') return;
    try {
      target.releasePointerCapture(pointerId);
    } catch {
      // Pointer capture may already be released by the browser.
    }
  }, []);

  // 指针事件：统一支持鼠标、触摸、触控笔，并在拖动时捕获指针。
  const handlePointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (typeof e.currentTarget.setPointerCapture === 'function') {
      e.currentTarget.setPointerCapture(e.pointerId);
    }
    setDraggingState(true);
    updateSliderPosition(e.clientX);
  }, [setDraggingState, updateSliderPosition]);

  const handlePointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return;
    e.preventDefault();
    e.stopPropagation();
    updateSliderPosition(e.clientX);
  }, [updateSliderPosition]);

  const handlePointerUp = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    releasePointerCapture(e.currentTarget, e.pointerId);
    setDraggingState(false);
  }, [releasePointerCapture, setDraggingState]);

  const handlePointerCancel = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    releasePointerCapture(e.currentTarget, e.pointerId);
    setDraggingState(false);
  }, [releasePointerCapture, setDraggingState]);

  const handleOpacityChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setBeforeOpacity(Number(e.target.value));
  }, []);

  const stopControlPropagation = useCallback((e: React.SyntheticEvent) => {
    e.stopPropagation();
  }, []);

  const updateImageDimension = useCallback(
    (kind: 'before' | 'after', element: HTMLImageElement) => {
      setImageDimensions((current) => ({
        ...current,
        [kind]: {
          width: element.naturalWidth || 1,
          height: element.naturalHeight || 1,
        },
      }));
    },
    []
  );

  const handleBeforeImageLoad = useCallback(
    (e: React.SyntheticEvent<HTMLImageElement, Event>) =>
      updateImageDimension('before', e.currentTarget),
    [updateImageDimension]
  );

  const handleAfterImageLoad = useCallback(
    (e: React.SyntheticEvent<HTMLImageElement, Event>) =>
      updateImageDimension('after', e.currentTarget),
    [updateImageDimension]
  );

  // 检查比例是否一致（允许 5% 误差）
  const aspectRatioMismatch = useCallback(() => {
    if (!imageDimensions.before || !imageDimensions.after) return false;
    const beforeRatio = imageDimensions.before.width / imageDimensions.before.height;
    const afterRatio = imageDimensions.after.width / imageDimensions.after.height;
    const diff = Math.abs(beforeRatio - afterRatio) / afterRatio;
    return diff > 0.05; // 超过 5% 视为不一致
  }, [imageDimensions]);

  const aspectRatio = getUnifiedAspectRatio();

  return (
    <div
      ref={containerRef}
      className={`relative inline-block overflow-hidden select-none ${className}`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
      onLostPointerCapture={() => setDraggingState(false)}
      style={{ 
        cursor: isDragging ? 'ew-resize' : 'col-resize',
        touchAction: 'none',
        lineHeight: 0,
        aspectRatio: aspectRatio > 0 ? `${aspectRatio}` : undefined,
        ...style 
      }}
    >
      {afterImage && (
        <CachedImage
          source={{ url: afterImage, mimeType: 'image/png' }}
          src={afterImage}
          alt=""
          aria-hidden="true"
          data-testid="image-compare-sizer"
          className="block opacity-0 pointer-events-none select-none"
          onLoad={handleAfterImageLoad}
          rawFallbackDelayMs={0}
          style={{
            maxWidth: 'inherit',
            maxHeight: 'inherit',
            width: 'auto',
            height: 'auto',
          }}
          draggable={false}
        />
      )}

      {/* 比例不一致提示 */}
      {aspectRatioMismatch() && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-30 bg-yellow-500/90 backdrop-blur-sm px-4 py-2 rounded-lg text-xs text-black font-medium shadow-lg">
          ⚠️ 图片比例不一致，对比可能有偏差
        </div>
      )}

      {/* 结果图（底层，完整显示） */}
      {afterImage && (
        <CachedImage
          source={{ url: afterImage, mimeType: 'image/png' }}
          src={afterImage}
          alt={afterLabel}
          className="absolute inset-0 w-full h-full object-cover pointer-events-none"
          rawFallbackDelayMs={0}
          draggable={false}
        />
      )}

      {/* 原图（上层，裁剪显示） */}
      <div
        data-testid="image-compare-before-layer"
        className="absolute inset-0 overflow-hidden pointer-events-none"
        style={{ width: `${sliderPosition}%`, opacity: beforeOpacity / 100 }}
      >
        {beforeImage && (
          <CachedImage
            source={{ url: beforeImage, mimeType: 'image/png' }}
            src={beforeImage}
            alt={beforeLabel}
            className="absolute inset-0 h-full object-cover"
            onLoad={handleBeforeImageLoad}
            rawFallbackDelayMs={0}
            style={{
              width: `${sliderPosition > 0 ? 100 / (sliderPosition / 100) : 10000}%`,
              maxWidth: 'none',
              objectPosition: 'left center',
            }}
            draggable={false}
          />
        )}
      </div>

      {/* 分割线 */}
      <div
        className="absolute top-0 bottom-0 w-1 -translate-x-1/2 pointer-events-none"
        style={{ left: `${sliderPosition}%` }}
      >
        <div className={`w-full h-full ${accentColors[accentColor]} shadow-lg`} />
        
        {/* 滑块手柄 */}
        <div 
          className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-10 h-10 rounded-full ${accentColors[accentColor]} shadow-xl flex items-center justify-center`}
        >
          <div className="flex gap-0.5">
            <div className="w-0.5 h-4 bg-white/80 rounded-full" />
            <div className="w-0.5 h-4 bg-white/80 rounded-full" />
          </div>
        </div>
      </div>

      {/* 标签 */}
      <div className="absolute top-4 left-4 bg-black/60 backdrop-blur-sm px-3 py-1 rounded-full text-xs text-white font-medium border border-white/10">
        {beforeLabel}
      </div>
      <div className="absolute top-4 right-4 bg-black/60 backdrop-blur-sm px-3 py-1 rounded-full text-xs text-white font-medium border border-white/10">
        {afterLabel}
      </div>

      <div
        className="absolute bottom-4 left-1/2 z-40 flex -translate-x-1/2 items-center gap-2 rounded-full border border-white/10 bg-black/65 px-3 py-2 text-white shadow-lg backdrop-blur-md"
        onPointerDown={stopControlPropagation}
        onPointerMove={stopControlPropagation}
        onPointerUp={stopControlPropagation}
        onClick={stopControlPropagation}
      >
        <span className="text-[10px] font-medium text-slate-200 whitespace-nowrap">原图</span>
        <input
          aria-label="原图透明度"
          type="range"
          min="0"
          max="100"
          step="1"
          value={beforeOpacity}
          onChange={handleOpacityChange}
          className="h-1.5 w-28 cursor-pointer"
          style={{ accentColor: accentHexColors[accentColor] }}
        />
        <span className="w-8 text-right font-mono text-[10px] text-slate-300">{beforeOpacity}%</span>
      </div>
    </div>
  );
};

export default ImageCompare;
