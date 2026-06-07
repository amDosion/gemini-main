import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  LogOut,
  User,
  Shield,
} from 'lucide-react';
import { ModelConfig, AppMode } from '../../types/types';
import { ConfigProfile } from '../../services/db';
import type { User as AuthUser, ChangePasswordData } from '../../services/auth';
import { useToastContext } from '../../contexts/ToastContext';
import type { SystemConfigPayload, SystemStatusPayload } from '../../services/systemAdmin';
import { systemAdminService } from '../../services/systemAdmin';
import { useEscapeClose } from '../../hooks/useEscapeClose';
import { ConfirmDialog } from '../common/ConfirmDialog';
import {
  normalizeNumberInput,
  SYSTEM_STATUS_POLL_INTERVAL_MS,
} from './headerHelpers';
import { HeaderUserInfoDialog } from './HeaderUserInfoDialog';
import { HeaderSystemConfigDialog } from './HeaderSystemConfigDialog';
import { HeaderModelSelector } from './HeaderModelSelector';
import { HeaderProfileSelector } from './HeaderProfileSelector';

interface HeaderProps {
  isSidebarOpen: boolean;
  setIsSidebarOpen: (v: boolean) => void;
  isLoadingModels: boolean;
  isModelMenuOpen: boolean;
  setIsModelMenuOpen: (v: boolean) => void;
  activeModelConfig?: ModelConfig;
  configApiKey: string;
  visibleModels: ModelConfig[];
  currentModelId: string;
  onModelSelect: (id: string) => void;
  onOpenSettings: (tab?: 'profiles' | 'editor') => void;
  appMode: AppMode;

  // New Profile-based Props
  profiles: ConfigProfile[];
  activeProfileId: string | null;
  onActivateProfile: (id: string) => void;
  currentUser: AuthUser | null;
  onChangePassword: (data: ChangePasswordData) => Promise<void>;
  onLogout?: () => void;
}

const USER_INFO_FIELD_LABELS: Partial<Record<keyof AuthUser, string>> = {
  id: '用户ID',
  name: '用户名',
  email: '邮箱',
  status: '状态',
  isAdmin: '是否管理员',
  createdAt: '注册时间',
  updatedAt: '最近更新时间',
  lastLoginAt: '最近登录时间',
};

const USER_INFO_FIELD_ORDER: Array<keyof AuthUser> = [
  'id',
  'name',
  'email',
  'status',
  'isAdmin',
  'createdAt',
  'updatedAt',
  'lastLoginAt',
];

const formatDateTime = (value?: string | null) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
};

const formatUserFieldValue = (field: string, value: unknown) => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (field === 'createdAt' || field === 'updatedAt' || field === 'lastLoginAt') {
    return formatDateTime(String(value));
  }
  return String(value);
};

export const Header: React.FC<HeaderProps> = ({
  isSidebarOpen,
  setIsSidebarOpen,
  isLoadingModels,
  isModelMenuOpen,
  setIsModelMenuOpen,
  activeModelConfig,
  configApiKey,
  visibleModels,
  currentModelId,
  onModelSelect,
  onOpenSettings,
  appMode,
  profiles,
  activeProfileId,
  onActivateProfile,
  currentUser,
  onChangePassword,
  onLogout,
}) => {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [isUserInfoDialogOpen, setIsUserInfoDialogOpen] = useState(false);
  const [isSystemConfigDialogOpen, setIsSystemConfigDialogOpen] = useState(false);
  const [isEditingPassword, setIsEditingPassword] = useState(false);
  const [passwordForm, setPasswordForm] = useState<ChangePasswordData>({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [isSubmittingPassword, setIsSubmittingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [systemConfig, setSystemConfig] = useState<SystemConfigPayload | null>(null);
  const [editedSystemConfig, setEditedSystemConfig] = useState<
    Record<string, string | number | boolean | null>
  >({});
  const [isLoadingSystemConfig, setIsLoadingSystemConfig] = useState(false);
  const [isSavingSystemConfig, setIsSavingSystemConfig] = useState(false);
  const [systemConfigError, setSystemConfigError] = useState('');
  const [systemStatus, setSystemStatus] = useState<SystemStatusPayload | null>(null);
  const [isLoadingSystemStatus, setIsLoadingSystemStatus] = useState(false);
  const [systemStatusError, setSystemStatusError] = useState('');
  const isSystemStatusRequestInFlight = useRef(false);
  const [isCleanupConfirmOpen, setIsCleanupConfirmOpen] = useState(false);
  const [isCleaningUp, setIsCleaningUp] = useState(false);
  const { showError, showSuccess } = useToastContext();

  // Get Current Profile
  const activeProfile = profiles.find((p) => p.id === activeProfileId);

  const userInfoEntries = useMemo(() => {
    if (!currentUser) return [] as Array<{ field: keyof AuthUser; label: string; value: string }>;

    return USER_INFO_FIELD_ORDER.filter((field) =>
      Object.prototype.hasOwnProperty.call(currentUser, field)
    ).map((field) => ({
      field,
      label: USER_INFO_FIELD_LABELS[field] || String(field),
      value: formatUserFieldValue(String(field), currentUser[field]),
    }));
  }, [currentUser]);

  const resetPasswordForm = () => {
    setPasswordForm({
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
    });
    setPasswordError('');
  };

  const closeUserInfoDialog = () => {
    if (isSubmittingPassword) return;
    setIsUserInfoDialogOpen(false);
    setIsEditingPassword(false);
    resetPasswordForm();
  };

  const handleChangePassword = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setPasswordError('');

    if (passwordForm.newPassword.length < 8) {
      setPasswordError('新密码至少需要 8 位');
      return;
    }

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordError('两次输入的新密码不一致');
      return;
    }

    try {
      setIsSubmittingPassword(true);
      await onChangePassword(passwordForm);
      showSuccess('密码修改成功');
      setIsEditingPassword(false);
      resetPasswordForm();
    } catch (error) {
      const message = error instanceof Error ? error.message : '修改密码失败，请重试';
      setPasswordError(message);
      showError(message);
    } finally {
      setIsSubmittingPassword(false);
    }
  };

  const loadSystemConfig = useCallback(async () => {
    try {
      setIsLoadingSystemConfig(true);
      setSystemConfigError('');
      const payload = await systemAdminService.getConfig();
      setSystemConfig(payload);
      setEditedSystemConfig(payload.values || {});
    } catch (error) {
      const message = error instanceof Error ? error.message : '获取系统配置失败';
      setSystemConfigError(message);
    } finally {
      setIsLoadingSystemConfig(false);
    }
  }, []);

  const loadSystemStatus = useCallback(async (silent = false) => {
    if (isSystemStatusRequestInFlight.current) return;

    isSystemStatusRequestInFlight.current = true;
    try {
      if (!silent) {
        setIsLoadingSystemStatus(true);
      }
      setSystemStatusError('');
      const payload = await systemAdminService.getStatus();
      setSystemStatus(payload);
    } catch (error) {
      const message = error instanceof Error ? error.message : '获取系统状态失败';
      setSystemStatusError(message);
    } finally {
      isSystemStatusRequestInFlight.current = false;
      if (!silent) {
        setIsLoadingSystemStatus(false);
      }
    }
  }, []);

  useEffect(() => {
    if (!isSystemConfigDialogOpen || !currentUser?.isAdmin) return;
    loadSystemConfig();
    loadSystemStatus();

    const timer = window.setInterval(() => {
      loadSystemStatus(true);
    }, SYSTEM_STATUS_POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [isSystemConfigDialogOpen, currentUser?.isAdmin, loadSystemConfig, loadSystemStatus]);

  const closeSystemConfigDialog = () => {
    if (isSavingSystemConfig) return;
    setIsSystemConfigDialogOpen(false);
    setSystemConfigError('');
    setSystemStatusError('');
  };

  useEscapeClose(isUserInfoDialogOpen, closeUserInfoDialog, !isSubmittingPassword);
  useEscapeClose(isSystemConfigDialogOpen, closeSystemConfigDialog, !isSavingSystemConfig);

  const handleSystemConfigValueChange = (
    key: string,
    type: 'boolean' | 'number' | 'string',
    value: string | number | boolean
  ) => {
    setEditedSystemConfig((prev) => {
      if (type === 'number' && typeof value === 'string') {
        return { ...prev, [key]: normalizeNumberInput(value) };
      }
      return { ...prev, [key]: value };
    });
  };

  const hasSystemConfigChanges = useMemo(() => {
    if (!systemConfig) return false;
    const source = systemConfig.values || {};
    return Object.keys(source).some((key) => source[key] !== editedSystemConfig[key]);
  }, [systemConfig, editedSystemConfig]);

  const handleSaveSystemConfig = async () => {
    if (!systemConfig || !hasSystemConfigChanges) return;

    const changedEntries = Object.entries(editedSystemConfig).filter(([key, value]) => {
      return systemConfig.values[key] !== value;
    });

    if (changedEntries.length === 0) return;

    const payload = changedEntries.reduce<Record<string, string | number | boolean>>(
      (acc, [key, value]) => {
        if (value === null || value === '') return acc;
        acc[key] = value as string | number | boolean;
        return acc;
      },
      {}
    );

    if (Object.keys(payload).length === 0) return;

    try {
      setIsSavingSystemConfig(true);
      setSystemConfigError('');
      const nextConfig = await systemAdminService.updateConfig(payload);
      setSystemConfig(nextConfig);
      setEditedSystemConfig(nextConfig.values || {});
      showSuccess('系统配置已更新');
    } catch (error) {
      const message = error instanceof Error ? error.message : '保存系统配置失败';
      setSystemConfigError(message);
      showError(message);
    } finally {
      setIsSavingSystemConfig(false);
    }
  };

  const handleCleanup = async () => {
    setIsCleanupConfirmOpen(false);
    setIsCleaningUp(true);
    try {
      const result = await systemAdminService.cleanup();
      const entries = Object.entries(result.cleaned)
        .map(([k, v]) => `${k}: ${v < 0 ? '失败' : v}`)
        .join(', ');
      const freedMB = ((result.freedBytes || 0) / 1024 / 1024).toFixed(2);
      showSuccess(`清理完成 (释放 ${freedMB} MB): ${entries}`);
      void loadSystemStatus();
    } catch (error) {
      const message = error instanceof Error ? error.message : '系统清理失败';
      showError(message);
    } finally {
      setIsCleaningUp(false);
    }
  };

  return (
    <header className="h-14 flex items-center justify-between gap-3 px-4 border-b border-slate-800 bg-slate-900/50 backdrop-blur-md z-50 shrink-0 sticky top-0">
      <div
        data-testid="header-primary-controls"
        className="flex w-fit min-w-0 max-w-full items-center gap-3 pr-2"
      >
        <HeaderProfileSelector
          profiles={profiles}
          activeProfileId={activeProfileId}
          onActivateProfile={onActivateProfile}
          onOpenSettings={onOpenSettings}
          onError={showError}
        />
        <HeaderModelSelector
          isLoadingModels={isLoadingModels}
          isModelMenuOpen={isModelMenuOpen}
          setIsModelMenuOpen={setIsModelMenuOpen}
          activeModelConfig={activeModelConfig}
          hasActiveProfile={Boolean(activeProfile)}
          visibleModels={visibleModels}
          currentModelId={currentModelId}
          onModelSelect={onModelSelect}
          onOpenSettings={onOpenSettings}
          appMode={appMode}
        />
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
            className={`p-2 rounded-lg transition-colors ${isUserMenuOpen ? 'bg-indigo-500/20 text-indigo-400' : 'hover:bg-slate-800 text-slate-400 hover:text-white'}`}
            title="User Menu"
          >
            <User size={20} />
          </button>

          {isUserMenuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setIsUserMenuOpen(false)} />
              <div className="absolute top-full right-0 mt-2 w-max bg-slate-900 border border-slate-700 rounded-xl shadow-2xl z-50 overflow-hidden ring-1 ring-black/50">
                <div className="p-2 flex flex-col gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      setIsUserMenuOpen(false);
                      setIsUserInfoDialogOpen(true);
                      setIsEditingPassword(false);
                      resetPasswordForm();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm text-slate-300 hover:bg-slate-800 hover:text-white transition-colors whitespace-nowrap"
                  >
                    <User size={16} />
                    查看用户信息
                  </button>
                  {currentUser?.isAdmin && (
                    <button
                      type="button"
                      onClick={() => {
                        setIsUserMenuOpen(false);
                        setIsUserInfoDialogOpen(false);
                        setIsSystemConfigDialogOpen(true);
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm text-slate-300 hover:bg-slate-800 hover:text-white transition-colors whitespace-nowrap"
                    >
                      <Shield size={16} />
                      系统配置
                    </button>
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        {onLogout && (
          <button
            type="button"
            onClick={onLogout}
            className="p-2 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded-lg transition-colors"
            title="Log Out"
          >
            <LogOut size={20} />
          </button>
        )}
      </div>

      <HeaderUserInfoDialog
        isOpen={isUserInfoDialogOpen}
        userInfoEntries={userInfoEntries}
        isEditingPassword={isEditingPassword}
        passwordForm={passwordForm}
        setPasswordForm={setPasswordForm}
        passwordError={passwordError}
        isSubmittingPassword={isSubmittingPassword}
        closeUserInfoDialog={closeUserInfoDialog}
        setIsEditingPassword={setIsEditingPassword}
        resetPasswordForm={resetPasswordForm}
        handleChangePassword={handleChangePassword}
      />

      <HeaderSystemConfigDialog
        isOpen={!!isSystemConfigDialogOpen && !!currentUser?.isAdmin}
        systemConfig={systemConfig}
        editedSystemConfig={editedSystemConfig}
        isLoadingSystemConfig={isLoadingSystemConfig}
        isSavingSystemConfig={isSavingSystemConfig}
        systemConfigError={systemConfigError}
        systemStatus={systemStatus}
        isLoadingSystemStatus={isLoadingSystemStatus}
        systemStatusError={systemStatusError}
        isCleaningUp={isCleaningUp}
        hasSystemConfigChanges={hasSystemConfigChanges}
        closeSystemConfigDialog={closeSystemConfigDialog}
        handleSystemConfigValueChange={handleSystemConfigValueChange}
        loadSystemStatus={loadSystemStatus}
        setIsCleanupConfirmOpen={setIsCleanupConfirmOpen}
        handleSaveSystemConfig={handleSaveSystemConfig}
      />
      {isCleanupConfirmOpen &&
        typeof document !== 'undefined' &&
        createPortal(
          <ConfirmDialog
            isOpen={isCleanupConfirmOpen}
            title="清理系统垃圾"
            message="将清理 __pycache__、临时上传文件、存储下载缓存、测试临时文件、过期上传任务、过期刷新令牌和 Redis 过期键。不会删除用户数据。确认继续？"
            confirmLabel="确认清理"
            cancelLabel="取消"
            onConfirm={handleCleanup}
            onCancel={() => setIsCleanupConfirmOpen(false)}
          />,
          document.body
        )}
    </header>
  );
};
