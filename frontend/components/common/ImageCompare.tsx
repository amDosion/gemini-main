/**
 * ImageCompare 组件
 * 
 * 图片对比组件，支持滑块对比模式
 * 用于对比原图和编辑/扩图后的图片
 */

import React, { useState, useRef, useCallback } from 'react';

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
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const accentColors = {
    pink: 'bg-pink-500',
    orange: 'bg-orange-500',
    emerald: 'bg-emerald-500',
    indigo: 'bg-indigo-500',
  };

  // 计算滑块位置
  const updateSliderPosition = useCallback((clientX: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = clientX - rect.left;
    const percentage = Math.min(Math.max((x / rect.width) * 100, 0), 100);
    setSliderPosition(percentage);
  }, []);

  // 鼠标事件
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    updateSliderPosition(e.clientX);
  }, [updateSliderPosition]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;
    updateSliderPosition(e.clientX);
  }, [isDragging, updateSliderPosition]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // 触摸事件
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    setIsDragging(true);
    updateSliderPosition(e.touches[0].clientX);
  }, [updateSliderPosition]);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (!isDragging) return;
    updateSliderPosition(e.touches[0].clientX);
  }, [isDragging, updateSliderPosition]);

  return (
    <div
      ref={containerRef}
      className={`relative overflow-hidden select-none ${className}`}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleMouseUp}
      style={{ cursor: isDragging ? 'ew-resize' : 'col-resize', ...style }}
    >

      {/* 结果图（底层，完整显示） */}
      <img
        src={afterImage}
        alt={afterLabel}
        className="w-full h-full object-contain pointer-events-none"
        draggable={false}
      />

      {/* 原图（上层，裁剪显示） */}
      <div
        className="absolute inset-0 overflow-hidden pointer-events-none"
        style={{ width: `${sliderPosition}%` }}
      >
        <img
          src={beforeImage}
          alt={beforeLabel}
          className="h-full object-contain"
          style={{ width: `${100 / (sliderPosition / 100)}%`, maxWidth: 'none' }}
          draggable={false}
        />
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
    </div>
  );
};

export default ImageCompare;
