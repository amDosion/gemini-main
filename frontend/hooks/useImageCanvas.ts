import { useState, useRef, useCallback, useMemo } from 'react';

const DEFAULT_PAN = { x: 0, y: 0 };

export interface UseImageCanvasOptions {
  minZoom?: number;
  maxZoom?: number;
  zoomStep?: number;
  wheelSensitivity?: number;
  initialZoom?: number;
}

export interface UseImageCanvasReturn {
  zoom: number;
  pan: { x: number; y: number };
  isDragging: boolean;
  handleZoomIn: (e?: React.MouseEvent) => void;
  handleZoomOut: (e?: React.MouseEvent) => void;
  handleReset: (e?: React.MouseEvent) => void;
  setZoom: (zoom: number) => void;
  handleWheel: (e: React.WheelEvent) => void;
  handleMouseDown: (e: React.MouseEvent) => void;
  handleMouseMove: (e: React.MouseEvent) => void;
  handleMouseUp: () => void;
  canvasStyle: React.CSSProperties;
  containerStyle: React.CSSProperties;
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

  const [zoom, _setZoom] = useState(initialZoom);
  const [pan, setPan] = useState(DEFAULT_PAN);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const panRef = useRef(pan);
  const isDraggingRef = useRef(isDragging);

  const setPanBoth = useCallback(
    (
      next:
        | { x: number; y: number }
        | ((prev: { x: number; y: number }) => { x: number; y: number })
    ) => {
      setPan((prev) => {
        const resolved = typeof next === 'function' ? next(prev) : next;
        panRef.current = resolved;
        return resolved;
      });
    },
    []
  );

  const setDraggingBoth = useCallback((next: boolean | ((prev: boolean) => boolean)) => {
    setIsDragging((prev) => {
      const resolved = typeof next === 'function' ? next(prev) : next;
      isDraggingRef.current = resolved;
      return resolved;
    });
  }, []);

  const clampZoom = useCallback(
    (value: number) => {
      return Math.min(Math.max(value, minZoom), maxZoom);
    },
    [minZoom, maxZoom]
  );

  const setZoom = useCallback(
    (newZoom: number) => {
      _setZoom((prevZoom) => {
        const nextZoom = clampZoom(newZoom);
        return prevZoom === nextZoom ? prevZoom : nextZoom;
      });
    },
    [clampZoom]
  );

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      const scaleAmount = wheelSensitivity;
      _setZoom((prevZoom) => {
        const newZoom = e.deltaY > 0 ? prevZoom * (1 - scaleAmount) : prevZoom * (1 + scaleAmount);
        return clampZoom(newZoom);
      });
    },
    [wheelSensitivity, clampZoom]
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setDraggingBoth(true);
      dragStartRef.current = {
        x: e.clientX - panRef.current.x,
        y: e.clientY - panRef.current.y,
      };
    },
    [setDraggingBoth]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDraggingRef.current) return;
      e.preventDefault();
      setPanBoth((prevPan) => {
        const nextPan = {
          x: e.clientX - dragStartRef.current.x,
          y: e.clientY - dragStartRef.current.y,
        };
        if (prevPan.x === nextPan.x && prevPan.y === nextPan.y) {
          return prevPan;
        }
        return nextPan;
      });
    },
    [setPanBoth]
  );

  const handleMouseUp = useCallback(() => {
    setDraggingBoth(false);
  }, [setDraggingBoth]);

  const handleZoomIn = useCallback(
    (e?: React.MouseEvent) => {
      e?.stopPropagation();
      setZoom(zoom + zoomStep);
    },
    [zoom, zoomStep, setZoom]
  );

  const handleZoomOut = useCallback(
    (e?: React.MouseEvent) => {
      e?.stopPropagation();
      setZoom(zoom - zoomStep);
    },
    [zoom, zoomStep, setZoom]
  );

  const resetView = useCallback(() => {
    setZoom(initialZoom);
    setPanBoth((prevPan) => {
      if (prevPan.x === DEFAULT_PAN.x && prevPan.y === DEFAULT_PAN.y) {
        return prevPan;
      }
      return DEFAULT_PAN;
    });
    setDraggingBoth((prevDragging) => (prevDragging ? false : prevDragging));
  }, [initialZoom, setZoom, setPanBoth, setDraggingBoth]);

  const handleReset = useCallback(
    (e?: React.MouseEvent) => {
      e?.stopPropagation();
      resetView();
    },
    [resetView]
  );

  const canvasStyle = useMemo<React.CSSProperties>(
    () => ({
      transform: `translate3d(${pan.x}px, ${pan.y}px, 0) scale(${zoom})`,
      transformOrigin: 'center center',
      transition: isDragging ? 'none' : 'transform 75ms ease-out',
      willChange: 'transform',
    }),
    [zoom, pan, isDragging]
  );

  const containerStyle = useMemo<React.CSSProperties>(
    () => ({
      cursor: isDragging ? 'grabbing' : 'grab',
      userSelect: 'none',
    }),
    [isDragging]
  );

  return {
    zoom,
    pan,
    isDragging,
    handleZoomIn,
    handleZoomOut,
    handleReset,
    setZoom,
    handleWheel,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    canvasStyle,
    containerStyle,
    resetView,
  };
}

export default useImageCanvas;
