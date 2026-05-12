/**
 * 主视图右侧参数面板的通用外壳（标题栏 + 重置按钮 + 滚动区 + 底部输入区）。
 *
 * 由 `ExpandMainCanvas` / `VideoMainCanvas` / `MaskEditMain` 共用。
 * 三处原本各自重复同一段 wrapper（w-72 + 标题 + RotateCcw 按钮 + 滚动 controls + 底部 input）。
 */

import React from 'react';
import { RotateCcw, SlidersHorizontal } from 'lucide-react';

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

export const ViewSideParamsPanel: React.FC<ViewSideParamsPanelProps> = ({
  title,
  iconClass = 'text-slate-400',
  resetParams,
  resetDisabled = false,
  resetTitle = '重置为默认值',
  controlsContent,
  editAreaContent,
}) => {
  return (
    <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
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
