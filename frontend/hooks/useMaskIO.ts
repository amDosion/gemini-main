/**
 * Mask 编辑器 I/O & 模式切换 hook。
 *
 * 抽离自 `components/views/ImageMaskEditView.tsx` L1262-1394
 * （JIRA-frontend-view-decomposition.md P0 #2 Step 3）。
 *
 * 提供 3 个回调：
 * 1. `handleMaskModeChange`：切换 mask mode（manual ↔ auto-bg/fg/semantic），自动模式下调用
 *    分割 API 获取预览；切回手动模式时清理预览
 * 2. `handleImportMask`：本地文件选择 → 标准化（resize 到原图尺寸）→ 应用为手动 mask
 * 3. `handleClearMask`：清除所有 mask 状态（选区/画笔/预览/blob URL）
 *
 * 设计：依赖通过 grouped object（setters / refs / external）传入，避免 16+ 平铺参数。
 * React useState setters 引用稳定（不需进 useCallback deps）；refs 同理非反应式。
 * 因此 useCallback deps 与原 inline 实现一致（仅外部 props/controls）。
 */

import { useCallback, type RefObject, type MutableRefObject } from 'react';
import { fileToBase64 } from './handlers/attachmentUtils';
import { revokeManagedMediaObjectUrl } from '../services/mediaCache';
import { type MaskMode, type SelectionRect } from '../utils/maskHelpers';
import { fetchAutoMaskPreview } from '../utils/maskSegmentation';

type Setter<T> = (value: T | ((prev: T) => T)) => void;

interface MaskControls {
  setMaskMode: (mode: MaskMode) => void;
}

interface UseMaskIOSetters {
  setMaskRequestDataUrl: Setter<string | null>;
  setMaskPreviewNotice: Setter<string | null>;
  setMaskPreviewError: Setter<string | null>;
  setSelectionRects: Setter<SelectionRect[]>;
  setCurrentSelectionRect: Setter<SelectionRect | null>;
  setIsPreviewingMask: Setter<boolean>;
  setMaskPreviewUrl: Setter<string | null>;
  setMaskCanvasUrl: Setter<string | null>;
}

interface UseMaskIORefs {
  imageRef: RefObject<HTMLImageElement | null>;
  maskCanvasRef: RefObject<HTMLCanvasElement | null>;
  displayCanvasRef: RefObject<HTMLCanvasElement | null>;
  hasBrushContentRef: MutableRefObject<boolean>;
  maskPreviewBlobUrlRef: MutableRefObject<string | null>;
  maskPreviewUrlRef: MutableRefObject<string | null>;
}

export interface UseMaskIOParams {
  controls: MaskControls;
  activeImageUrl: string | null;
  providerId: string | undefined;
  showError: (msg: string) => void;
  setters: UseMaskIOSetters;
  refs: UseMaskIORefs;
}

export interface UseMaskIOResult {
  handleMaskModeChange: (mode: MaskMode) => Promise<void>;
  handleImportMask: () => void;
  handleClearMask: () => void;
}

export const useMaskIO = ({
  controls,
  activeImageUrl,
  providerId,
  showError,
  setters,
  refs,
}: UseMaskIOParams): UseMaskIOResult => {
  const {
    setMaskRequestDataUrl,
    setMaskPreviewNotice,
    setMaskPreviewError,
    setSelectionRects,
    setCurrentSelectionRect,
    setIsPreviewingMask,
    setMaskPreviewUrl,
    setMaskCanvasUrl,
  } = setters;
  const {
    imageRef,
    maskCanvasRef,
    displayCanvasRef,
    hasBrushContentRef,
    maskPreviewBlobUrlRef,
    maskPreviewUrlRef,
  } = refs;

  const handleMaskModeChange = useCallback(
    async (mode: MaskMode) => {
      controls.setMaskMode(mode);
      setMaskRequestDataUrl(null);
      setMaskPreviewNotice(null);
      setMaskPreviewError(null);

      // 切到自动模式：清除手动选区 + 拉取自动 mask 预览
      if (mode !== 'MASK_MODE_USER_PROVIDED') {
        setSelectionRects([]);
        setCurrentSelectionRect(null);

        if (activeImageUrl) {
          setIsPreviewingMask(true);
          try {
            const result = await fetchAutoMaskPreview(activeImageUrl, providerId, mode);
            if (result.maskUrl) {
              setMaskPreviewUrl(result.maskUrl);
              setMaskPreviewNotice(null);
              setMaskPreviewError(null);
            } else if (result.notice) {
              setMaskPreviewUrl(null);
              setMaskPreviewNotice(result.notice);
              setMaskPreviewError(null);
            } else if (result.error) {
              setMaskPreviewUrl(null);
              setMaskPreviewError(result.error);
              showError(result.error);
            }
          } finally {
            setIsPreviewingMask(false);
          }
        } else {
          setMaskPreviewUrl(null);
          setMaskPreviewNotice(null);
          setMaskPreviewError('请先上传或选择一张图片');
        }
      } else {
        // 切回手动模式：清除自动 mask 预览
        setMaskPreviewUrl(null);
        setMaskRequestDataUrl(null);
        setMaskPreviewNotice(null);
        setMaskPreviewError(null);
      }
    },
    // 仅列入外部反应式依赖（setters 引用稳定 → 与原 inline 实现一致）
    [controls, activeImageUrl, providerId, showError]
  );

  const handleImportMask = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/png,image/jpeg,image/webp,image/*';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;

      let dataUrl: string;
      try {
        dataUrl = await fileToBase64(file);
      } catch {
        showError('Mask 导入失败，请重新选择图片');
        return;
      }

      const applyImportedMask = (normalizedMaskUrl: string) => {
        controls.setMaskMode('MASK_MODE_USER_PROVIDED');
        setSelectionRects([]);
        setCurrentSelectionRect(null);
        setMaskPreviewUrl(normalizedMaskUrl);
        setMaskPreviewNotice(null);
        setMaskPreviewError(null);
        setMaskRequestDataUrl(normalizedMaskUrl);
      };

      const rawImage = imageRef.current;
      if (!rawImage?.naturalWidth || !rawImage?.naturalHeight) {
        applyImportedMask(dataUrl);
        return;
      }

      // 将导入的 mask 缩放到原图分辨率（保证 mask 与原图像素 1:1 对齐）
      const importedMask = new Image();
      importedMask.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = rawImage.naturalWidth;
        canvas.height = rawImage.naturalHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          applyImportedMask(dataUrl);
          return;
        }
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(importedMask, 0, 0, canvas.width, canvas.height);
        applyImportedMask(canvas.toDataURL('image/png'));
      };
      importedMask.onerror = () => showError('Mask 导入失败，请重新选择图片');
      importedMask.src = dataUrl;
    };
    input.click();
  }, [controls, showError]);

  const handleClearMask = useCallback(() => {
    setSelectionRects([]);
    setCurrentSelectionRect(null);
    setMaskPreviewUrl(null);
    setMaskPreviewNotice(null);
    setMaskPreviewError(null);
    setMaskRequestDataUrl(null);
    // 清除画笔绘制的 mask canvas
    if (maskCanvasRef.current) {
      const ctx = maskCanvasRef.current.getContext('2d', { willReadFrequently: true });
      if (ctx) {
        ctx.clearRect(0, 0, maskCanvasRef.current.width, maskCanvasRef.current.height);
      }
    }
    // 清除显示 canvas
    if (displayCanvasRef.current) {
      const ctx = displayCanvasRef.current.getContext('2d', { willReadFrequently: true });
      if (ctx) {
        ctx.clearRect(0, 0, displayCanvasRef.current.width, displayCanvasRef.current.height);
      }
    }
    hasBrushContentRef.current = false;
    // 清理 blob URL（防内存泄漏）
    if (maskPreviewBlobUrlRef.current) {
      revokeManagedMediaObjectUrl(maskPreviewBlobUrlRef.current);
      maskPreviewBlobUrlRef.current = null;
    }
    if (maskPreviewUrlRef.current) {
      revokeManagedMediaObjectUrl(maskPreviewUrlRef.current);
      maskPreviewUrlRef.current = null;
    }
    setMaskCanvasUrl(null);
  }, []);

  return { handleMaskModeChange, handleImportMask, handleClearMask };
};
