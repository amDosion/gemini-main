/**
 * 主视图右侧参数面板的通用外壳（标题栏 + 重置按钮 + 滚动区 + 底部输入区）。
 *
 * 由 `ExpandMainCanvas` / `VideoMainCanvas` / `MaskEditMain` 共用。
 * 三处原本各自重复同一段 wrapper（w-72 + 标题 + RotateCcw 按钮 + 滚动 controls + 底部 input）。
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { RotateCcw, SlidersHorizontal } from 'lucide-react';
import { safeLocalGet, safeLocalSet } from '../../utils/safeOps';

export interface ViewSideParamsPanelProps {
  title: string;
  /** 标题图标 className（如 `'text-orange-400'`）。 */
  iconClass?: string;
  resetParams: () => void;
  resetDisabled?: boolean;
  resetTitle?: string;
  /** ModeControlsCoordinator 等参数主体（嵌入到中间滚动区）。 */
  controlsContent: React.ReactNode;
  /** ChatEditInputArea 等底部输入区（嵌入到面板底部）。 */
  editAreaContent: React.ReactNode;
}

const PARAMS_PANEL_WIDTH_STORAGE_KEY = 'view-side-params-panel:width';
const DEFAULT_PARAMS_PANEL_WIDTH = 288;
const MIN_PARAMS_PANEL_WIDTH = 280;
const MAX_PARAMS_PANEL_WIDTH = 520;

const clampParamsPanelWidth = (value: number): number =>
  Math.max(MIN_PARAMS_PANEL_WIDTH, Math.min(MAX_PARAMS_PANEL_WIDTH, Math.round(value)));

const getInitialParamsPanelWidth = (): number => {
  const storedWidth = Number(safeLocalGet(PARAMS_PANEL_WIDTH_STORAGE_KEY));
  return Number.isFinite(storedWidth) && storedWidth > 0
    ? clampParamsPanelWidth(storedWidth)
    : DEFAULT_PARAMS_PANEL_WIDTH;
};

export const ViewSideParamsPanel: React.FC<ViewSideParamsPanelProps> = ({
  title,
  iconClass = 'text-slate-400',
  resetParams,
  resetDisabled = false,
  resetTitle = '重置为默认值',
  controlsContent,
  editAreaContent,
}) => {
  const [panelWidth, setPanelWidth] = useState(getInitialParamsPanelWidth);
  // 进行中拖拽的清理函数；组件在拖拽途中卸载时由 useEffect cleanup 调用。
  const dragCleanupRef = useRef<(() => void) | null>(null);

  useEffect(
    () => () => {
      dragCleanupRef.current?.();
    },
    []
  );

  const handleResizeStart = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = panelWidth;
      let nextWidth = panelWidth;
      let animationFrame: number | null = null;

      const handleMouseMove = (moveEvent: MouseEvent) => {
        nextWidth = clampParamsPanelWidth(startWidth + startX - moveEvent.clientX);
        if (animationFrame !== null) {
          window.cancelAnimationFrame(animationFrame);
        }
        animationFrame = window.requestAnimationFrame(() => {
          setPanelWidth(nextWidth);
          animationFrame = null;
        });
      };

      const stopDrag = () => {
        if (animationFrame !== null) {
          window.cancelAnimationFrame(animationFrame);
          animationFrame = null;
        }
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        dragCleanupRef.current = null;
      };

      const handleMouseUp = () => {
        safeLocalSet(PARAMS_PANEL_WIDTH_STORAGE_KEY, String(nextWidth));
        stopDrag();
      };

      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      dragCleanupRef.current = stopDrag;
    },
    [panelWidth]
  );

  return (
    <div
      data-testid="view-side-params-panel"
      className="relative flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden"
      style={{ width: panelWidth }}
    >
      <div
        role="separator"
        aria-label="拖动调整参数面板宽度"
        aria-orientation="vertical"
        onMouseDown={handleResizeStart}
        className="hidden md:block absolute left-0 top-0 z-20 h-full w-2 -translate-x-1/2 cursor-col-resize"
      />
      <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={14} className={iconClass} />
          <span className="text-xs font-bold text-white">{title}</span>
        </div>
        <button
          onClick={resetParams}
          disabled={resetDisabled}
          className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title={resetTitle}
        >
          <RotateCcw size={12} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-4">{controlsContent}</div>

      {editAreaContent}
    </div>
  );
};
