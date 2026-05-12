/**
 * VideoGenView 历史侧边栏 hover prompt 预览 Portal。
 *
 * 1:1 抽离自 `VideoGenView.tsx` L957-1074 hover preview portal。
 * 注意：相比通用 HoverPromptPreviewPortal，此版本：
 *  - 使用 z-[140]（高于 action menu 的 z-[130]）
 *  - 额外渲染 "视频信息" 区块（extensionCount / totalDurationSeconds / strategyLabel / subtitleLabel）
 */

import React from 'react';
import { createPortal } from 'react-dom';
import { Check, Copy } from 'lucide-react';
import type {
  HoverPromptPreviewPosition,
  HoverPromptPreviewSize,
} from '../../../hooks/useHoverPromptPreview';
import type { HoverPromptPreview } from './types';

export interface VideoHoverPreviewPortalProps {
  hoverPreview: HoverPromptPreview;
  hoverPreviewPosition: HoverPromptPreviewPosition | null;
  hoverPreviewSize: HoverPromptPreviewSize | null;
  hoverPreviewPanelRef: React.RefObject<HTMLDivElement | null>;
  clearHidePreviewTimer: () => void;
  scheduleHideHoverPreview: () => void;
  handleCopyOptimizedPrompt: () => Promise<void> | void;
  copiedPreviewMessageId: string | null;
  handlePreviewResizeMouseDown: (event: React.MouseEvent) => void;
  isResizingPreview: boolean;
}

export const VideoHoverPreviewPortal: React.FC<VideoHoverPreviewPortalProps> = ({
  hoverPreview,
  hoverPreviewPosition,
  hoverPreviewSize,
  hoverPreviewPanelRef,
  clearHidePreviewTimer,
  scheduleHideHoverPreview,
  handleCopyOptimizedPrompt,
  copiedPreviewMessageId,
  handlePreviewResizeMouseDown,
  isResizingPreview,
}) => {
  if (typeof document === 'undefined') return null;
  return createPortal(
    <div
      ref={hoverPreviewPanelRef}
      className="fixed z-[140] hidden md:block"
      style={{
        top: hoverPreviewPosition?.top ?? hoverPreview.anchorY,
        left: hoverPreviewPosition?.left ?? hoverPreview.anchorX,
        ...(hoverPreviewSize
          ? { width: hoverPreviewSize.width, height: hoverPreviewSize.height }
          : {}),
      }}
      onMouseEnter={() => clearHidePreviewTimer()}
      onMouseLeave={() => scheduleHideHoverPreview()}
    >
      <div
        className={`group relative rounded-xl border border-slate-700/80 bg-slate-950/95 backdrop-blur-lg p-3 shadow-2xl ${
          hoverPreviewSize ? 'h-full' : 'inline-block w-fit max-w-[min(70vw,560px)]'
        }`}
      >
        <div
          className="absolute right-full -translate-y-1/2 h-2.5 w-2.5 rotate-45 border-b border-l border-slate-700/80 bg-slate-950/95"
          style={{ top: hoverPreviewPosition?.arrowOffsetY ?? '50%' }}
        />

        <div
          className={`pr-2 pb-5 custom-scrollbar ${
            hoverPreviewSize ? 'h-full overflow-y-auto' : 'max-h-[70vh] overflow-y-auto'
          }`}
        >
          <div className="mb-3">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">
              原始提示词
            </p>
            <p className="mt-1 text-xs text-slate-200 whitespace-pre-wrap break-words">
              {hoverPreview.originalPrompt}
            </p>
          </div>

          <div>
            <div className="flex items-center justify-between gap-2">
              <p className="text-[10px] uppercase tracking-wider text-indigo-400">
                优化后提示词
              </p>
              {hoverPreview.optimizedPrompt && (
                <button
                  type="button"
                  onClick={handleCopyOptimizedPrompt}
                  className="pointer-events-auto inline-flex items-center gap-1 rounded-md border border-indigo-500/30 bg-indigo-500/10 px-1.5 py-0.5 text-[10px] text-indigo-200 hover:bg-indigo-500/20 transition-colors"
                  title="复制优化后提示词"
                >
                  {copiedPreviewMessageId === hoverPreview.messageId ? (
                    <Check size={11} />
                  ) : (
                    <Copy size={11} />
                  )}
                  {copiedPreviewMessageId === hoverPreview.messageId ? '已复制' : '复制'}
                </button>
              )}
            </div>
            {hoverPreview.optimizedPrompt ? (
              <p className="mt-1 text-xs text-indigo-100 whitespace-pre-wrap break-words">
                {hoverPreview.optimizedPrompt}
              </p>
            ) : (
              <p className="mt-1 text-xs text-slate-500 italic">未返回优化后的提示词</p>
            )}
          </div>

          {(hoverPreview.extensionCount > 0 ||
            hoverPreview.totalDurationSeconds ||
            hoverPreview.strategyLabel ||
            hoverPreview.subtitleLabel) && (
            <div className="mt-3 border-t border-slate-800 pt-3">
              <p className="text-[10px] uppercase tracking-wider text-cyan-400">视频信息</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px]">
                {hoverPreview.extensionCount > 0 && (
                  <span className="inline-flex items-center rounded-full border border-cyan-500/30 bg-cyan-500/10 px-1.5 py-0.5 text-cyan-200">
                    延长 {hoverPreview.extensionCount} 次
                  </span>
                )}
                {hoverPreview.totalDurationSeconds && (
                  <span className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-emerald-200">
                    总时长 {hoverPreview.totalDurationSeconds}s
                  </span>
                )}
                {hoverPreview.strategyLabel && (
                  <span className="inline-flex items-center rounded-full border border-slate-600 bg-slate-800/80 px-1.5 py-0.5 text-slate-300">
                    {hoverPreview.strategyLabel}
                  </span>
                )}
                {hoverPreview.subtitleLabel && (
                  <span className="inline-flex items-center rounded-full border border-fuchsia-500/30 bg-fuchsia-500/10 px-1.5 py-0.5 text-fuchsia-200">
                    {hoverPreview.subtitleLabel}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        <button
          type="button"
          aria-label="拖动调整提示词预览大小"
          className="absolute bottom-0 right-0 h-5 w-5 cursor-se-resize bg-transparent"
          onMouseDown={handlePreviewResizeMouseDown}
        />
        {isResizingPreview && (
          <div className="pointer-events-none absolute bottom-1 left-3 text-[10px] text-slate-500">
            {Math.round(hoverPreviewSize?.width || 0)} ×{' '}
            {Math.round(hoverPreviewSize?.height || 0)}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
};
