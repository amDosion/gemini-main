/**
 * 通用 hover prompt 预览 Portal（Expand / Recontext / Edit / Video 等视图共用）。
 *
 * 与原 `VideoHoverPreviewPortal` 合并：
 *  - `extraContent` 插槽：渲染优化提示词区块下方的额外信息（如视频元数据）
 *  - `zClass` 控制层级（默认无；Video 视图传 `z-[140]`）
 */

import React from 'react';
import { createPortal } from 'react-dom';
import { Check, Copy } from 'lucide-react';
import type {
  HoverPromptPreviewBase,
  HoverPromptPreviewPosition,
  HoverPromptPreviewSize,
} from '../../hooks/useHoverPromptPreview';

export interface HoverPromptPreviewPortalProps {
  preview: HoverPromptPreviewBase | null;
  position: HoverPromptPreviewPosition | null;
  size: HoverPromptPreviewSize | null;
  panelRef: React.RefObject<HTMLDivElement | null>;
  clearHidePreviewTimer: () => void;
  scheduleHideHoverPreview: () => void;
  handleCopyOptimizedPrompt: () => Promise<void> | void;
  copiedPreviewMessageId: string | null;
  handlePreviewResizeMouseDown: (event: React.MouseEvent) => void;
  isResizingPreview: boolean;
  optimizedLabel?: string;
  optimizedLabelClass?: string;
  optimizedTextClass?: string;
  copyButtonClass?: string;
  missingOptimizedText?: string;
  maxWidthClass?: string;
  maxHeightClass?: string;
  /** 渲染在优化提示词下方的额外内容（如 Video 视图的"视频信息"区块）。 */
  extraContent?: React.ReactNode;
  /** Portal 层级 class。默认无（Image 视图）；Video 视图传 `z-[140]`。 */
  zClass?: string;
}

export const HoverPromptPreviewPortal: React.FC<HoverPromptPreviewPortalProps> = ({
  preview,
  position,
  size,
  panelRef,
  clearHidePreviewTimer,
  scheduleHideHoverPreview,
  handleCopyOptimizedPrompt,
  copiedPreviewMessageId,
  handlePreviewResizeMouseDown,
  isResizingPreview,
  optimizedLabel = '优化后提示词',
  optimizedLabelClass = 'text-orange-400',
  optimizedTextClass = 'text-orange-100',
  copyButtonClass = 'border-orange-500/30 bg-orange-500/10 text-orange-200 hover:bg-orange-500/20',
  missingOptimizedText = '未返回优化后的提示词',
  maxWidthClass = 'inline-block w-fit max-w-[min(70vw,560px)]',
  maxHeightClass = 'max-h-[70vh] overflow-y-auto',
  extraContent,
  zClass,
}) => {
  if (!preview || typeof document === 'undefined') return null;
  return createPortal(
    <div
      ref={panelRef}
      className={`fixed hidden md:block${zClass ? ` ${zClass}` : ''}`}
      style={{
        top: position?.top ?? preview.anchorY,
        left: position?.left ?? preview.anchorX,
        ...(size ? { width: size.width, height: size.height } : {}),
      }}
      onMouseEnter={clearHidePreviewTimer}
      onMouseLeave={scheduleHideHoverPreview}
    >
      <div
        className={`group relative rounded-xl border border-slate-700/80 bg-slate-950/95 backdrop-blur-lg p-3 shadow-2xl ${
          size ? 'h-full' : maxWidthClass
        }`}
      >
        <div
          className="absolute right-full -translate-y-1/2 h-2.5 w-2.5 rotate-45 border-b border-l border-slate-700/80 bg-slate-950/95"
          style={{ top: position?.arrowOffsetY ?? '50%' }}
        />

        <div
          className={`pr-2 pb-5 custom-scrollbar ${size ? 'h-full overflow-y-auto' : maxHeightClass}`}
        >
          <div className="mb-3">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">原始提示词</p>
            <p className="mt-1 text-xs text-slate-200 whitespace-pre-wrap break-words">
              {preview.originalPrompt}
            </p>
          </div>

          <div>
            <div className="flex items-center justify-between gap-2">
              <p className={`text-[10px] uppercase tracking-wider ${optimizedLabelClass}`}>
                {optimizedLabel}
              </p>
              {preview.optimizedPrompt && (
                <button
                  type="button"
                  onClick={handleCopyOptimizedPrompt}
                  className={`pointer-events-auto inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] transition-colors ${copyButtonClass}`}
                  title={`复制${optimizedLabel}`}
                >
                  {copiedPreviewMessageId === preview.messageId ? (
                    <Check size={11} />
                  ) : (
                    <Copy size={11} />
                  )}
                  {copiedPreviewMessageId === preview.messageId ? '已复制' : '复制'}
                </button>
              )}
            </div>
            {preview.optimizedPrompt ? (
              <p className={`mt-1 text-xs ${optimizedTextClass} whitespace-pre-wrap break-words`}>
                {preview.optimizedPrompt}
              </p>
            ) : (
              <p className="mt-1 text-xs text-slate-500 italic">{missingOptimizedText}</p>
            )}
          </div>

          {extraContent}
        </div>

        <button
          type="button"
          aria-label="拖动调整提示词预览大小"
          className="absolute bottom-0 right-0 h-5 w-5 cursor-se-resize bg-transparent"
          onMouseDown={handlePreviewResizeMouseDown}
        />
        {isResizingPreview && (
          <div className="pointer-events-none absolute bottom-1 left-3 text-[10px] text-slate-500">
            {Math.round(size?.width || 0)} x {Math.round(size?.height || 0)}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
};
