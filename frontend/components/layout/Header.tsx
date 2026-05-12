import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  ChevronDown,
  Check,
  Loader2,
  Settings,
  Globe,
  Brain,
  Image as ImageIcon,
  Zap,
  BrainCircuit,
  Video,
  Mic,
  Server,
  Sparkles,
  PlusCircle,
  LogOut,
  Search,
  X,
  User,
  Shield,
  Flame,
} from 'lucide-react';
import { ModelConfig, AppMode } from '../../types/types';
import { ConfigProfile } from '../../services/db';
import type { User as AuthUser, ChangePasswordData } from '../../services/auth';
import { useToastContext } from '../../contexts/ToastContext';
import { isMultimodalUnderstandingModel } from '../../utils/modelSuitability';
import { getModelUsage } from '../../utils/modelUsage';
import type { SystemConfigPayload, SystemStatusPayload } from '../../services/systemAdmin';
import { systemAdminService } from '../../services/systemAdmin';
import { useEscapeClose } from '../../hooks/useEscapeClose';
import { ConfirmDialog } from '../common/ConfirmDialog';

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

import {
  getModelIcon,
  getProviderIcon,
  normalizeNumberInput,
  SYSTEM_STATUS_POLL_INTERVAL_MS,
} from './headerHelpers';
import { HeaderUserInfoDialog } from './HeaderUserInfoDialog';
import { HeaderSystemConfigDialog } from './HeaderSystemConfigDialog';

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
  const ActiveIcon = activeModelConfig ? getModelIcon(activeModelConfig) : Loader2;
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const [isActivating, setIsActivating] = useState(false);
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
  const [modelSearchQuery, setModelSearchQuery] = useState('');
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

  // Filter models based on search query
  // ✅ visibleModels 已经从 useModels hook 返回，已经根据 appMode 过滤过了
  // 这里只需要根据搜索查询进一步过滤
  const filteredModels = useMemo(() => {
    if (!modelSearchQuery.trim()) return visibleModels;

    const query = modelSearchQuery.toLowerCase();
    return visibleModels.filter(
      (m) => m.name.toLowerCase().includes(query) || m.id.toLowerCase().includes(query)
    );
  }, [visibleModels, modelSearchQuery]);

  const renderCapabilities = (model: ModelConfig) => {
    return (
      <div className="flex items-center gap-1 ml-2">
        {model.capabilities.search && <Globe size={12} className="text-blue-400" />}
        {model.capabilities.reasoning && <Brain size={12} className="text-purple-400" />}
        {model.capabilities.vision && isMultimodalUnderstandingModel(model) && (
          <ImageIcon size={12} className="text-emerald-400" />
        )}
        {model.capabilities.coding && <BrainCircuit size={12} className="text-amber-400" />}
      </div>
    );
  };

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
      loadSystemStatus();
    } catch (error) {
      const message = error instanceof Error ? error.message : '系统清理失败';
      showError(message);
    } finally {
      setIsCleaningUp(false);
    }
  };

  return (
    <header className="h-14 flex items-center justify-between px-4 border-b border-slate-800 bg-slate-900/50 backdrop-blur-md z-50 shrink-0 sticky top-0">
      <div className="flex items-center gap-2">
        {/* --- Profile / Provider Selector --- */}
        <div className="relative hidden md:block border-r border-slate-700/50 pr-2 mr-2">
          <button
            type="button"
            onClick={() => setIsProfileMenuOpen(!isProfileMenuOpen)}
            className={`flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors ${
              !activeProfile
                ? 'text-orange-400 bg-orange-900/20'
                : 'hover:bg-slate-800 text-slate-300'
            }`}
          >
            {activeProfile ? (
              <div className="p-1 rounded bg-slate-800 text-slate-400">
                {getProviderIcon(activeProfile.providerId)}
              </div>
            ) : (
              <div className="p-1 rounded bg-orange-900/50 text-orange-400">
                <Settings size={14} />
              </div>
            )}
            <span className="text-sm font-medium max-w-[150px] truncate">
              {activeProfile ? activeProfile.name : 'Setup Required'}
            </span>
            <ChevronDown size={12} className="text-slate-500" />
          </button>

          {isProfileMenuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setIsProfileMenuOpen(false)} />
              <div className="absolute top-full left-0 mt-2 w-64 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl z-50 overflow-hidden max-h-[70vh] flex flex-col ring-1 ring-black/50">
                <div className="px-3 py-2 bg-slate-950/50 border-b border-slate-800 text-xs font-bold text-slate-500 uppercase tracking-wider flex justify-between items-center">
                  <span>Saved Configurations</span>
                  <button
                    onClick={() => {
                      setIsProfileMenuOpen(false);
                      onOpenSettings('editor');
                    }}
                    className="text-indigo-400 hover:text-indigo-300"
                  >
                    <PlusCircle size={14} />
                  </button>
                </div>

                <div className="p-1 overflow-y-auto custom-scrollbar">
                  {profiles.length === 0 && (
                    <div className="p-4 text-center text-xs text-slate-500 italic">
                      No profiles found.
                      <br />
                      Click below to add one.
                    </div>
                  )}
                  {profiles.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={async (e) => {
                        e.preventDefault();
                        e.stopPropagation();

                        setIsActivating(true);
                        try {
                          await onActivateProfile(p.id);
                          setIsProfileMenuOpen(false);
                        } catch (error) {
                          showError('切换提供商失败，请重试');
                        } finally {
                          setIsActivating(false);
                        }
                      }}
                      disabled={isActivating}
                      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm group transition-all ${
                        activeProfileId === p.id
                          ? 'bg-indigo-600 text-white'
                          : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                      } ${isActivating ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      <div className="flex items-center gap-3 overflow-hidden">
                        <div
                          className={`p-1 rounded shrink-0 ${activeProfileId === p.id ? 'bg-white/20' : 'bg-slate-800 group-hover:bg-slate-700'}`}
                        >
                          {getProviderIcon(p.providerId)}
                        </div>
                        <div className="flex flex-col items-start min-w-0">
                          <span className="truncate w-full font-medium">{p.name}</span>
                          <span className="text-[10px] opacity-60 truncate w-full text-left font-mono">
                            {p.providerId} • {p.cachedModelCount ?? '?'} models
                          </span>
                        </div>
                      </div>
                      {activeProfileId === p.id && <Check size={14} className="shrink-0" />}
                    </button>
                  ))}
                </div>
                <div className="border-t border-slate-800 p-2 shrink-0 bg-slate-900">
                  <button
                    type="button"
                    onClick={() => {
                      setIsProfileMenuOpen(false);
                      onOpenSettings('profiles');
                    }}
                    className="w-full flex items-center justify-center gap-2 p-2 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                  >
                    <Settings size={14} /> Manage Configurations
                  </button>
                </div>
              </div>
            </>
          )}
        </div>

        {/* --- Model Selector --- */}
        <div className="relative">
          <button
            type="button"
            onClick={() => !isLoadingModels && setIsModelMenuOpen(!isModelMenuOpen)}
            disabled={isLoadingModels || !activeProfile}
            className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-800 transition-colors group disabled:opacity-50 min-w-[160px]"
          >
            {isLoadingModels ? (
              <Loader2 size={16} className="animate-spin text-slate-400" />
            ) : (
              <div className="p-1 rounded bg-indigo-500/10 text-indigo-400">
                <ActiveIcon size={16} />
              </div>
            )}

            <div className="flex items-center flex-1">
              <span className="font-semibold text-slate-200 text-sm leading-none truncate max-w-[150px]">
                {activeModelConfig?.name ||
                  activeModelConfig?.id ||
                  (activeProfile ? 'Select Model' : 'No Config')}
              </span>
              {!isLoadingModels && activeModelConfig && renderCapabilities(activeModelConfig)}
            </div>

            <ChevronDown
              size={14}
              className={`text-slate-400 transition-transform duration-200 ml-1 ${isModelMenuOpen ? 'rotate-180' : ''}`}
            />
          </button>

          {isModelMenuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setIsModelMenuOpen(false)} />
              <div className="absolute top-full left-0 mt-2 w-96 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl z-50 overflow-hidden ring-1 ring-black/50">
                {/* Search Input */}
                <div className="p-2 border-b border-slate-800">
                  <div className="relative">
                    <input
                      type="text"
                      value={modelSearchQuery}
                      onChange={(e) => setModelSearchQuery(e.target.value)}
                      placeholder="Search models..."
                      className="w-full pl-3 pr-20 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                      onClick={(e) => e.stopPropagation()}
                    />
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                      {modelSearchQuery && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setModelSearchQuery('');
                          }}
                          className="p-1 text-slate-500 hover:text-white transition-colors rounded hover:bg-slate-700"
                          title="Clear search"
                        >
                          <X size={14} />
                        </button>
                      )}
                      <Search size={16} className="text-slate-500" />
                    </div>
                  </div>
                </div>
                <div className="p-2 flex flex-col gap-1 max-h-[60vh] overflow-y-auto custom-scrollbar">
                  {filteredModels.length === 0 && (
                    <div className="p-4 text-sm text-slate-500 text-center flex flex-col gap-2 items-center">
                      <Server size={24} className="opacity-50" />
                      <p>
                        No compatible models found for this profile in <b>{appMode}</b> mode.
                      </p>
                      <button
                        type="button"
                        onClick={() => onOpenSettings('editor')}
                        className="text-indigo-400 hover:underline text-xs"
                      >
                        Verify Config
                      </button>
                    </div>
                  )}

                  {filteredModels.map((model) => {
                    const Icon = getModelIcon(model);
                    const isSelected = currentModelId === model.id;
                    const usage = getModelUsage(model);
                    return (
                      <button
                        key={model.id}
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onModelSelect(model.id);
                        }}
                        className={`flex items-start gap-3 p-3 rounded-lg transition-colors text-left ${
                          isSelected
                            ? 'bg-slate-800 border border-slate-700'
                            : 'hover:bg-slate-800/50 border border-transparent'
                        }`}
                      >
                        <div
                          className={`mt-0.5 p-2 rounded-lg ${isSelected ? 'bg-indigo-500 text-white' : 'bg-slate-800 text-slate-400'}`}
                        >
                          <Icon size={18} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-0.5">
                            <div className="flex items-center gap-2 overflow-hidden w-full">
                              <span
                                className={`text-sm font-medium truncate ${isSelected ? 'text-white' : 'text-slate-300'}`}
                                title={model.id}
                              >
                                {model.name || model.id}
                              </span>
                              {renderCapabilities(model)}
                            </div>
                            {isSelected && (
                              <Check size={14} className="text-indigo-400 shrink-0 ml-2" />
                            )}
                          </div>
                          <div
                            className="text-xs text-slate-500 leading-tight truncate"
                            title={usage}
                          >
                            {usage}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
                <div className="p-2 border-t border-slate-800 bg-slate-900">
                  <button
                    type="button"
                    onClick={() => {
                      setIsModelMenuOpen(false);
                      onOpenSettings('profiles');
                    }}
                    className="w-full flex items-center justify-center gap-2 p-2 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                  >
                    <Settings size={14} />
                    <span>Manage Active Models</span>
                    <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">
                      {filteredModels.length}
                    </span>
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
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
