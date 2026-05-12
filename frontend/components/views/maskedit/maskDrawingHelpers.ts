/**
 * Mask 编辑画布的纯绘制辅助函数。
 *
 * 1:1 抽离自 `ImageMaskEditView.tsx`:
 *  - `drawOnMaskCanvas` (L290-392)
 *  - `generateMaskFromSelections` (L490-612)
 */

import type React from 'react';
import { fileToBase64 } from '../../../hooks/handlers/attachmentUtils';
import type { SelectionRect } from '../../../utils/maskHelpers';

export const getOrCreateMaskCanvas = (
  imageRef: React.RefObject<HTMLImageElement | null>,
  maskCanvasRef: React.MutableRefObject<HTMLCanvasElement | null>
): HTMLCanvasElement | null => {
  const img = imageRef.current;
  if (!img) return null;

  if (
    !maskCanvasRef.current ||
    maskCanvasRef.current.width !== img.naturalWidth ||
    maskCanvasRef.current.height !== img.naturalHeight
  ) {
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    maskCanvasRef.current = canvas;
  }
  return maskCanvasRef.current;
};

export const drawDisplayCanvas = (
  maskCanvasRef: React.RefObject<HTMLCanvasElement | null>,
  displayCanvasRef: React.RefObject<HTMLCanvasElement | null>
): void => {
  const srcCanvas = maskCanvasRef.current;
  const dstCanvas = displayCanvasRef.current;
  if (!srcCanvas || !dstCanvas) return;

  const ctx = dstCanvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) return;

  if (dstCanvas.width !== srcCanvas.width || dstCanvas.height !== srcCanvas.height) {
    dstCanvas.width = srcCanvas.width;
    dstCanvas.height = srcCanvas.height;
  }
  ctx.clearRect(0, 0, dstCanvas.width, dstCanvas.height);
  ctx.drawImage(srcCanvas, 0, 0);
};

export interface UpdateMaskCanvasUrlArgs {
  maskCanvasRef: React.RefObject<HTMLCanvasElement | null>;
  hasBrushContentRef: React.MutableRefObject<boolean>;
  maskPreviewBlobUrlRef: React.MutableRefObject<string | null>;
  setMaskCanvasUrl: (url: string | null) => void;
  onAfterUpdate: () => void;
}

export const updateMaskCanvasUrl = ({
  maskCanvasRef,
  hasBrushContentRef,
  maskPreviewBlobUrlRef,
  setMaskCanvasUrl,
  onAfterUpdate,
}: UpdateMaskCanvasUrlArgs): void => {
  const canvas = maskCanvasRef.current;
  if (!canvas) return;

  if (hasBrushContentRef.current) {
    if (maskPreviewBlobUrlRef.current) {
      URL.revokeObjectURL(maskPreviewBlobUrlRef.current);
      maskPreviewBlobUrlRef.current = null;
    }
    canvas.toBlob((blob) => {
      if (blob) {
        const url = URL.createObjectURL(blob);
        maskPreviewBlobUrlRef.current = url;
        setMaskCanvasUrl(url);
      }
    }, 'image/png');
  } else {
    if (maskPreviewBlobUrlRef.current) {
      URL.revokeObjectURL(maskPreviewBlobUrlRef.current);
      maskPreviewBlobUrlRef.current = null;
    }
    setMaskCanvasUrl(null);
  }
  onAfterUpdate();
};

export interface DrawOnMaskCanvasArgs {
  x: number;
  y: number;
  isEraser?: boolean;
  isStart?: boolean;
  getMaskCanvas: () => HTMLCanvasElement | null;
  imageRef: React.RefObject<HTMLImageElement | null>;
  brushSize: number;
  brushPointsRef: React.MutableRefObject<Array<{ x: number; y: number }>>;
  hasBrushContentRef: React.MutableRefObject<boolean>;
  lastBrushPosRef: React.MutableRefObject<{ x: number; y: number } | null>;
}

export const drawOnMaskCanvas = ({
  x,
  y,
  isEraser = false,
  isStart = false,
  getMaskCanvas,
  imageRef,
  brushSize,
  brushPointsRef,
  hasBrushContentRef,
  lastBrushPosRef,
}: DrawOnMaskCanvasArgs): void => {
  const canvas = getMaskCanvas();
  if (!canvas) return;

  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) return;

  const img = imageRef.current;
  if (!img) return;

  const scaleX = img.naturalWidth / img.clientWidth;
  const scaleY = img.naturalHeight / img.clientHeight;
  const actualX = x * scaleX;
  const actualY = y * scaleY;
  const actualBrushSize = brushSize * Math.max(scaleX, scaleY);

  if (isEraser) {
    ctx.globalCompositeOperation = 'destination-out';
    ctx.fillStyle = 'rgba(255, 255, 255, 1)';
    ctx.strokeStyle = 'rgba(255, 255, 255, 1)';
  } else {
    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = 'rgba(59, 130, 246, 1)';
    ctx.strokeStyle = 'rgba(59, 130, 246, 1)';
  }

  if (isStart) {
    brushPointsRef.current = [{ x: actualX, y: actualY }];
    ctx.beginPath();
    ctx.arc(actualX, actualY, actualBrushSize / 2, 0, Math.PI * 2);
    ctx.fill();
  } else {
    brushPointsRef.current.push({ x: actualX, y: actualY });
    const points = brushPointsRef.current;

    ctx.lineWidth = actualBrushSize;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    if (points.length >= 3) {
      const p0 = points[points.length - 3];
      const p1 = points[points.length - 2];
      const p2 = points[points.length - 1];
      const startX = (p0.x + p1.x) / 2;
      const startY = (p0.y + p1.y) / 2;
      const endX = (p1.x + p2.x) / 2;
      const endY = (p1.y + p2.y) / 2;

      ctx.beginPath();
      ctx.moveTo(startX, startY);
      ctx.quadraticCurveTo(p1.x, p1.y, endX, endY);
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(endX, endY, actualBrushSize / 2, 0, Math.PI * 2);
      ctx.fill();

      if (points.length > 4) {
        brushPointsRef.current = points.slice(-3);
      }
    } else if (points.length === 2) {
      const p0 = points[0];
      const p1 = points[1];
      ctx.beginPath();
      ctx.moveTo(p0.x, p0.y);
      ctx.lineTo(p1.x, p1.y);
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(p1.x, p1.y, actualBrushSize / 2, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  ctx.globalCompositeOperation = 'source-over';

  if (!isEraser) {
    hasBrushContentRef.current = true;
  }

  lastBrushPosRef.current = { x, y };
};

export interface GenerateMaskFromSelectionsArgs {
  rects: SelectionRect[];
  inverted: boolean;
  imageRef: React.RefObject<HTMLImageElement | null>;
  maskCanvasRef: React.RefObject<HTMLCanvasElement | null>;
  hasBrushContentRef: React.MutableRefObject<boolean>;
  maskCompositeCanvasRef: React.MutableRefObject<HTMLCanvasElement | null>;
  maskPreviewUrlRef: React.MutableRefObject<string | null>;
  isMountedRef: React.MutableRefObject<boolean>;
  setMaskPreviewUrl: (url: string | null) => void;
  setMaskRequestDataUrl: (url: string | null) => void;
  setMaskPreviewError: (error: string | null) => void;
  showError: (message: string) => void;
}

export const generateMaskFromSelections = ({
  rects,
  inverted,
  imageRef,
  maskCanvasRef,
  hasBrushContentRef,
  maskCompositeCanvasRef,
  maskPreviewUrlRef,
  isMountedRef,
  setMaskPreviewUrl,
  setMaskRequestDataUrl,
  setMaskPreviewError,
  showError,
}: GenerateMaskFromSelectionsArgs): void => {
  const img = imageRef.current;
  const hasBrushMask = hasBrushContentRef.current;

  if ((!img || rects.length === 0) && !hasBrushMask) {
    setMaskPreviewUrl(null);
    setMaskRequestDataUrl(null);
    return;
  }

  if (!img) return;

  const imgWidth = img.naturalWidth;
  const imgHeight = img.naturalHeight;
  const displayWidth = img.clientWidth;
  const displayHeight = img.clientHeight;
  const scaleX = imgWidth / displayWidth;
  const scaleY = imgHeight / displayHeight;

  if (
    !maskCompositeCanvasRef.current ||
    maskCompositeCanvasRef.current.width !== imgWidth ||
    maskCompositeCanvasRef.current.height !== imgHeight
  ) {
    maskCompositeCanvasRef.current = document.createElement('canvas');
    maskCompositeCanvasRef.current.width = imgWidth;
    maskCompositeCanvasRef.current.height = imgHeight;
  }
  const canvas = maskCompositeCanvasRef.current;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) return;

  ctx.clearRect(0, 0, imgWidth, imgHeight);

  if (inverted) {
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, imgWidth, imgHeight);
    ctx.fillStyle = 'black';
  } else {
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, imgWidth, imgHeight);
    ctx.fillStyle = 'white';
  }

  rects.forEach((rect) => {
    const x = Math.min(rect.startX, rect.endX) * scaleX;
    const y = Math.min(rect.startY, rect.endY) * scaleY;
    const width = Math.abs(rect.endX - rect.startX) * scaleX;
    const height = Math.abs(rect.endY - rect.startY) * scaleY;
    ctx.fillRect(x, y, width, height);
  });

  if (maskCanvasRef.current && hasBrushMask) {
    const brushCanvas = maskCanvasRef.current;
    ctx.save();
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = brushCanvas.width;
    tempCanvas.height = brushCanvas.height;
    const tempCtx = tempCanvas.getContext('2d', { willReadFrequently: true });
    if (tempCtx) {
      tempCtx.fillStyle = inverted ? 'black' : 'white';
      tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
      tempCtx.globalCompositeOperation = 'destination-in';
      tempCtx.drawImage(brushCanvas, 0, 0);
      ctx.globalCompositeOperation = 'source-over';
      ctx.drawImage(tempCanvas, 0, 0);
    }
    ctx.restore();
  }

  canvas.toBlob((blob) => {
    if (!blob) return;
    // 卸载后 callback 仍可能到达：直接丢弃 blob，不创建 URL，避免泄漏。
    if (!isMountedRef.current) {
      return;
    }
    if (maskPreviewUrlRef.current) {
      URL.revokeObjectURL(maskPreviewUrlRef.current);
    }
    const url = URL.createObjectURL(blob);
    maskPreviewUrlRef.current = url;
    setMaskPreviewUrl(url);

    fileToBase64(blob)
      .then((dataUrl) => {
        if (!isMountedRef.current) return;
        setMaskRequestDataUrl(dataUrl);
      })
      .catch(() => {
        if (!isMountedRef.current) return;
        setMaskRequestDataUrl(null);
        setMaskPreviewError('Mask 转换失败，请重试');
        showError('Mask 数据转换失败，请重试');
      });
  }, 'image/png');
};
