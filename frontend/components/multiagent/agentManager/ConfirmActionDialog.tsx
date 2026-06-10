/**
 * ConfirmActionDialog - Agent 管理面板的确认弹窗(停用 / 永久删除 / 恢复共用)。
 *
 * 抽离自 AgentManagerPanel 中两处近乎重复的确认遮罩,统一遮罩、面板、标题、
 * 取消/确认按钮布局与加载态,差异部分(标题、正文、确认文案/配色/图标、忙碌态、
 * 回调)通过 props 注入,行为与原内联实现保持一致。
 */

import React from 'react';
import { Loader2 } from 'lucide-react';

interface ConfirmActionDialogProps {
  title: string;
  /** 对话框正文,会被包裹在 <p> 内。 */
  children: React.ReactNode;
  confirmLabel: string;
  /** 确认按钮的配色变体类;基础布局类已内置。 */
  confirmVariantClassName: string;
  /** 非加载态时确认按钮内显示的图标。 */
  confirmIcon: React.ReactNode;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export const ConfirmActionDialog: React.FC<ConfirmActionDialogProps> = ({
  title,
  children,
  confirmLabel,
  confirmVariantClassName,
  confirmIcon,
  busy,
  onCancel,
  onConfirm,
}) => (
  <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/65 backdrop-blur-sm">
    <div className="w-[430px] max-w-[92vw] rounded-xl border border-slate-700 bg-slate-900 shadow-2xl p-5">
      <h3 className="text-base font-semibold text-slate-100 mb-2">{title}</h3>
      <p className="text-sm text-slate-300">{children}</p>
      <div className="mt-5 flex items-center justify-end gap-2">
        <button
          onClick={onCancel}
          disabled={busy}
          className="px-3 py-1.5 text-sm bg-slate-800 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          取消
        </button>
        <button
          onClick={onConfirm}
          disabled={busy}
          className={`px-3 py-1.5 text-sm rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 ${confirmVariantClassName}`}
        >
          {busy ? <Loader2 size={13} className="animate-spin" /> : confirmIcon}
          {confirmLabel}
        </button>
      </div>
    </div>
  </div>
);

export default ConfirmActionDialog;
