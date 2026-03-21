import React from 'react';
import { useEscapeClose } from '../../hooks/useEscapeClose';

type ConfirmTone = 'danger' | 'primary' | 'neutral';

interface ActionDialogProps {
  isOpen: boolean;
  title: string;
  description?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmTone?: ConfirmTone;
  confirmDisabled?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: React.ReactNode;
  icon?: React.ReactNode;
  maxWidthClassName?: string;
}

const confirmToneClass = (tone: ConfirmTone): string => {
  if (tone === 'danger') {
    return 'bg-red-600 hover:bg-red-500 text-white';
  }
  if (tone === 'primary') {
    return 'bg-indigo-600 hover:bg-indigo-500 text-white';
  }
  return 'bg-slate-700 hover:bg-slate-600 text-white';
};

export const ActionDialog: React.FC<ActionDialogProps> = ({
  isOpen,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  confirmTone = 'primary',
  confirmDisabled = false,
  onConfirm,
  onCancel,
  children,
  icon,
  maxWidthClassName = 'max-w-md',
}) => {
  useEscapeClose(isOpen, onCancel);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[180] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]"
      onClick={onCancel}
      role="presentation"
    >
      <div
        className={`w-full ${maxWidthClassName} rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl overflow-hidden`}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="p-5 border-b border-slate-800">
          <div className="flex items-start gap-3">
            {icon ? (
              <div className="p-2 rounded-lg bg-slate-800/80 border border-slate-700/80 text-slate-300 shrink-0">
                {icon}
              </div>
            ) : null}
            <div className="min-w-0">
              <h3 className="text-base font-semibold text-white">{title}</h3>
              {description ? (
                <p className="text-sm text-slate-300 mt-1 leading-relaxed">{description}</p>
              ) : null}
            </div>
          </div>
        </div>

        {children ? (
          <div className="p-4 border-b border-slate-800">
            {children}
          </div>
        ) : null}

        <div className="p-4 flex justify-end gap-2.5">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-lg text-sm text-slate-300 hover:text-white hover:bg-slate-900 transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={confirmDisabled}
            className={`px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${confirmToneClass(confirmTone)}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ActionDialog;
