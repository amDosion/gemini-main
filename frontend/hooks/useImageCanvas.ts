/**
 * useImageCanvas Hook
 * 
 * 提供图片画布的交互功能：
 * - 放大 / 缩小 / 重置
 * - 拖拽平移
 * - 滚轮缩放
 * 
 * 可复用于 ImageEditView、ImageExpandView 等组件
 */

import { useState, useRef, useCallback, useEffect } from 'react';

export interface UseImageCanvasOptions {
  /** 最小缩放比例，默认 0.1 */
  minZoom?: number;
  /** 最大缩放比例，默认 5 */
  maxZoom?: number;
  /** 缩放步长，默认 0.2 */
  zoomStep?: number;
  /** 滚轮缩放灵敏度，默认 0.1 */
  wheelSensitivity?: number;
  /** 初始缩放比例，默认 1 */
  initialZoom?: number;
}

export interface UseImageCanvasReturn {
  // 状态
  zoom: number;
  pan: { x: number; y: number };
  isDragging: boolean;
  
  // 操作方法
  handleZoomIn: (e?: React.MouseEvent) => void;
  handleZoomOut: (e?: React.MouseEvent) => void;
  handleReset: (e?: React.MouseEvent) => void;
  setZoom: (zoom: number) => void;
  
  // 事件处理器
  handleWheel: (e: React.WheelEvent) => void;
  handleMouseDown: (e: React.MouseEvent) => void;
  handleMouseMove: (e: React.MouseEvent) => void;
  handleMouseUp: () => void;
  
  // 样式
  canvasStyle: React.CSSProperties;
  containerStyle: React.CSSProperties;
  
  // 工具方法
  resetView: () => void;
}

export function useImageCanvas(options: UseImageCanvasOptions = {}): UseImageCanvasReturn {
  const {
    minZoom = 0.1,
    maxZoom = 5,
    zoomStep = 0.2,
    wheelSensitivity = 0.1,
    initialZoom = 1,
  } = options;

  // 状态
  const [zoom, setZoomState] = useState(initialZoom);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  
  // Ref 用于拖拽计算
  const dragStartRef = useRef({ x: 0, y: 0 });

  // 限制缩放范围
  const clampZoom = useCallback((value: number) => {
    return Math.min(Math.max(value, minZoom), maxZoom);
  }, [minZoom, maxZoom]);

  // 设置缩放（带范围限制）
  const setZoom = useCallback((value: number) => {
    setZoomState(clampZoom(value));
  }, [clampZoom]);

  // 放大
  const handleZoomIn = useCallback((e?: React.MouseEvent) => {
    e?.stopPropagation();
    setZoomState(prev => clampZoom(prev + zoomStep));
  }, [clampZoom, zoomStep]);

  // 缩小
  const handleZoomOut = useCallback((e?: React.MouseEvent) => {
    e?.stopPropagation();
    setZoomState(prev => clampZoom(prev - zoomStep));
  }, [clampZoom, zoomStep]);

  // 重置视图
  const resetView = useCallback(() => {
    setZoomState(initialZoom);
    setPan({ x: 0, y: 0 });
  }, [initialZoom]);

  const handleReset = useCallback((e?: React.MouseEvent) => {
    e?.stopPropagation();
    resetView();
  }, [resetView]);

  // 滚轮缩放
  const handleWheel = useCallback((e: React.WheelEvent) => {
    const scaleAmount = wheelSensitivity;
    const newZoom = e.deltaY > 0 
      ? zoom * (1 - scaleAmount) 
      : zoom * (1 + scaleAmount);
    setZoomState(clampZoom(newZoom));
  }, [zoom, wheelSensitivity, clampZoom]);

  // 拖拽开始
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX - pan.x,
      y: e.clientY - pan.y,
    };
  }, [pan]);

  // 拖拽移动
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;
    e.preventDefault();
    setPan({
      x: e.clientX - dragStartRef.current.x,
      y: e.clientY - dragStartRef.current.y,
    });
  }, [isDragging]);

  // 拖拽结束
  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // 画布样式（应用到图片容器）
  const canvasStyle: React.CSSProperties = {
    transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
    transformOrigin: 'center center',
    transition: isDragging ? 'none' : 'transform 75ms ease-out',
  };

  // 容器样式
  const containerStyle: React.CSSProperties = {
    cursor: isDragging ? 'grabbing' : 'grab',
    userSelect: 'none',
  };

  return {
    // 状态
    zoom,
    pan,
    isDragging,
    
    // 操作方法
    handleZoomIn,
    handleZoomOut,
    handleReset,
    setZoom,
    
    // 事件处理器
    handleWheel,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    
    // 样式
    canvasStyle,
    containerStyle,
    
    // 工具方法
    resetView,
  };
}

export default useImageCanvas;
