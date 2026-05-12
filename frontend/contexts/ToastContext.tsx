import React, { createContext, useContext, useMemo, ReactNode } from 'react';
import { useToast } from '../hooks/useToast';
import { ToastContainer } from '../components/common/Toast';

interface ToastContextType {
  showSuccess: (message: string, duration?: number) => string;
  showError: (message: string, duration?: number) => string;
  showInfo: (message: string, duration?: number) => string;
  showWarning: (message: string, duration?: number) => string;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { toasts, showSuccess, showError, showInfo, showWarning, removeToast } = useToast();

  // ✅ Wave 2 perf: useMemo 包裹 context value，避免每次 ToastProvider 渲染
  // 都创建新对象触发 consumer（全应用）不必要的重渲染。
  // 注意：useToast 内部 callbacks 已 useCallback，依赖稳定。
  const value = useMemo<ToastContextType>(
    () => ({ showSuccess, showError, showInfo, showWarning }),
    [showSuccess, showError, showInfo, showWarning]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
};

export const useToastContext = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToastContext must be used within ToastProvider');
  }
  return context;
};
