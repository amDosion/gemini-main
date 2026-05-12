/**
 * Header 用户信息 / 修改密码 Dialog 组件。
 *
 * 1:1 抽离自 `Header.tsx` L708-847 isUserInfoDialogOpen portal block。
 */

import React from 'react';
import { createPortal } from 'react-dom';
import { KeyRound, Loader2, X } from 'lucide-react';
import type { User as AuthUser, ChangePasswordData } from '../../services/auth';

export interface HeaderUserInfoDialogProps {
  isOpen: boolean;
  userInfoEntries: Array<{ field: keyof AuthUser; label: string; value: string }>;
  isEditingPassword: boolean;
  passwordForm: ChangePasswordData;
  setPasswordForm: React.Dispatch<React.SetStateAction<ChangePasswordData>>;
  passwordError: string;
  isSubmittingPassword: boolean;
  closeUserInfoDialog: () => void;
  setIsEditingPassword: React.Dispatch<React.SetStateAction<boolean>>;
  resetPasswordForm: () => void;
  handleChangePassword: (event: React.FormEvent<HTMLFormElement>) => void | Promise<void>;
}

export const HeaderUserInfoDialog: React.FC<HeaderUserInfoDialogProps> = ({
  isOpen,
  userInfoEntries,
  isEditingPassword,
  passwordForm,
  setPasswordForm,
  passwordError,
  isSubmittingPassword,
  closeUserInfoDialog,
  setIsEditingPassword,
  resetPasswordForm,
  handleChangePassword,
}) => {
  if (!isOpen || typeof document === 'undefined') return null;
  return createPortal(
    <>
      <div className="fixed inset-0 z-[160] bg-black/60" onClick={closeUserInfoDialog} />
      <div className="fixed inset-0 z-[161] flex items-center justify-center p-4">
        <div className="w-full max-w-lg bg-slate-900 border border-slate-700 rounded-xl shadow-2xl ring-1 ring-black/50">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
            <h3 className="text-base font-semibold text-white">
              {isEditingPassword ? '修改密码' : '用户信息'}
            </h3>
            <button
              type="button"
              onClick={closeUserInfoDialog}
              className="p-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
              disabled={isSubmittingPassword}
            >
              <X size={16} />
            </button>
          </div>
          {!isEditingPassword ? (
            <div className="p-5 space-y-3">
              <div className="grid grid-cols-[120px_1fr] gap-2 text-sm">
                {userInfoEntries.map((item) => (
                  <React.Fragment key={item.field}>
                    <span className="text-slate-400">{item.label}</span>
                    <span
                      className={`text-slate-200 ${item.field === 'id' || item.field === 'email' ? 'break-all' : ''}`}
                    >
                      {item.value}
                    </span>
                  </React.Fragment>
                ))}
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={closeUserInfoDialog}
                  className="px-4 py-2 text-sm rounded-lg text-slate-300 hover:bg-slate-800 transition-colors"
                >
                  关闭
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIsEditingPassword(true);
                    resetPasswordForm();
                  }}
                  className="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors inline-flex items-center gap-2"
                >
                  <KeyRound size={14} />
                  修改密码
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleChangePassword} className="p-5 space-y-4">
              <div className="space-y-1">
                <label htmlFor="currentPassword" className="text-sm text-slate-300">
                  当前密码
                </label>
                <input
                  id="currentPassword"
                  type="password"
                  value={passwordForm.currentPassword}
                  onChange={(e) =>
                    setPasswordForm((prev) => ({ ...prev, currentPassword: e.target.value }))
                  }
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  required
                  autoComplete="current-password"
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="newPassword" className="text-sm text-slate-300">
                  新密码
                </label>
                <input
                  id="newPassword"
                  type="password"
                  value={passwordForm.newPassword}
                  onChange={(e) =>
                    setPasswordForm((prev) => ({ ...prev, newPassword: e.target.value }))
                  }
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="confirmPassword" className="text-sm text-slate-300">
                  确认新密码
                </label>
                <input
                  id="confirmPassword"
                  type="password"
                  value={passwordForm.confirmPassword}
                  onChange={(e) =>
                    setPasswordForm((prev) => ({ ...prev, confirmPassword: e.target.value }))
                  }
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
              </div>
              {passwordError && (
                <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                  {passwordError}
                </div>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsEditingPassword(false);
                    resetPasswordForm();
                  }}
                  className="px-4 py-2 text-sm rounded-lg text-slate-300 hover:bg-slate-800 transition-colors"
                  disabled={isSubmittingPassword}
                >
                  返回
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-60 disabled:cursor-not-allowed inline-flex items-center gap-2"
                  disabled={isSubmittingPassword}
                >
                  {isSubmittingPassword && <Loader2 size={14} className="animate-spin" />}
                  提交修改
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </>,
    document.body
  );
};
