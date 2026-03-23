
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, Check, Loader2, Settings, Globe, Brain, Image as ImageIcon, Zap, BrainCircuit, Video, Mic, Server, Cpu, Sparkles, PlusCircle, LogOut, Search, X, User, KeyRound, Shield, Activity, HardDrive, Network, RefreshCw, Trash2 } from 'lucide-react';
import { ModelConfig, AppMode } from '../../types/types';
import { ConfigProfile } from '../../services/db';
import type { User as AuthUser, ChangePasswordData } from '../../services/auth';
import { useToastContext } from '../../contexts/ToastContext';
import { isMultimodalUnderstandingModel } from '../../utils/modelSuitability';
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

const getModelIcon = (model: ModelConfig) => {
    const id = model.id.toLowerCase();
    // 视频生成模型
    if (id.includes('veo') || id.includes('sora') || id.includes('luma')) return Video;
    // 音频生成模型
    if (id.includes('tts') || id.includes('audio') || id.includes('speech')) return Mic;
    // 文生图模型：统一使用 Zap 图标
    if (id.includes('-t2i') || id.includes('z-image') || id.includes('wanx') || id.includes('wan2') || id.includes('dall') || id.includes('flux') || id.includes('midjourney') || id.includes('imagen')) return Zap;
    // 代码模型
    if (model.capabilities.coding) return BrainCircuit;
    // 推理模型
    if (model.capabilities.reasoning) return Brain;
    // 搜索模型
    if (model.capabilities.search) return Globe;
    // 视觉理解模型（不是文生图）
    if (model.capabilities.vision) return ImageIcon;
    // Pro 模型
    if (id.includes('pro')) return BrainCircuit;
    // 默认
    return Zap;
};

const getProviderIcon = (pid: string) => {
    if (pid.includes('google')) return <Zap size={14} />;
    if (pid.includes('deepseek')) return <Cpu size={14} />;
    if (pid.includes('tongyi')) return <Globe size={14} />;
    if (pid.includes('openai')) return <Sparkles size={14} />;
    return <Server size={14} />;
};

const formatBytes = (bytes?: number | null): string => {
    if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return '—';
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const base = Math.floor(Math.log(bytes) / Math.log(1024));
    const index = Math.min(base, units.length - 1);
    const value = bytes / Math.pow(1024, index);
    return `${value.toFixed(value >= 100 || index === 0 ? 0 : 1)} ${units[index]}`;
};

const formatPercent = (value?: number | null): string => {
    if (value === null || value === undefined || Number.isNaN(value)) return '—';
    return `${value.toFixed(1)}%`;
};

const normalizeNumberInput = (value: string): number | '' => {
    if (value === '') return '';
    const n = Number(value);
    return Number.isFinite(n) ? n : '';
};

const SYSTEM_STATUS_POLL_INTERVAL_MS = 2000;

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
    onLogout
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
        confirmPassword: ''
    });
    const [isSubmittingPassword, setIsSubmittingPassword] = useState(false);
    const [passwordError, setPasswordError] = useState('');
    const [modelSearchQuery, setModelSearchQuery] = useState('');
    const [systemConfig, setSystemConfig] = useState<SystemConfigPayload | null>(null);
    const [editedSystemConfig, setEditedSystemConfig] = useState<Record<string, string | number | boolean | null>>({});
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
    const activeProfile = profiles.find(p => p.id === activeProfileId);

    // Filter models based on search query
    // ✅ visibleModels 已经从 useModels hook 返回，已经根据 appMode 过滤过了
    // 这里只需要根据搜索查询进一步过滤
    const filteredModels = useMemo(() => {
        if (!modelSearchQuery.trim()) return visibleModels;
        
        const query = modelSearchQuery.toLowerCase();
        return visibleModels.filter(m => 
            m.name.toLowerCase().includes(query) || m.id.toLowerCase().includes(query)
        );
    }, [visibleModels, modelSearchQuery]);

    const renderCapabilities = (model: ModelConfig) => {
        return (
            <div className="flex items-center gap-1 ml-2">
                {model.capabilities.search && <Globe size={12} className="text-blue-400" />}
                {model.capabilities.reasoning && <Brain size={12} className="text-purple-400" />}
                {model.capabilities.vision && isMultimodalUnderstandingModel(model) && <ImageIcon size={12} className="text-emerald-400" />}
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
        lastLoginAt: '最近登录时间'
    };

    const USER_INFO_FIELD_ORDER: Array<keyof AuthUser> = [
        'id',
        'name',
        'email',
        'status',
        'isAdmin',
        'createdAt',
        'updatedAt',
        'lastLoginAt'
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

        return USER_INFO_FIELD_ORDER
            .filter((field) => Object.prototype.hasOwnProperty.call(currentUser, field))
            .map((field) => ({
                field,
                label: USER_INFO_FIELD_LABELS[field] || String(field),
                value: formatUserFieldValue(String(field), currentUser[field])
            }));
    }, [currentUser]);

    const resetPasswordForm = () => {
        setPasswordForm({
            currentPassword: '',
            newPassword: '',
            confirmPassword: ''
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

    useEscapeClose(
        isUserInfoDialogOpen,
        closeUserInfoDialog,
        !isSubmittingPassword
    );
    useEscapeClose(
        isSystemConfigDialogOpen,
        closeSystemConfigDialog,
        !isSavingSystemConfig
    );

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

        const payload = changedEntries.reduce<Record<string, string | number | boolean>>((acc, [key, value]) => {
            if (value === null || value === '') return acc;
            acc[key] = value as string | number | boolean;
            return acc;
        }, {});

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

    const configFields = systemConfig?.fields || [];

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
                        className={`flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors ${!activeProfile ? 'text-orange-400 bg-orange-900/20' : 'hover:bg-slate-800 text-slate-300'
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
                                    <button onClick={() => { setIsProfileMenuOpen(false); onOpenSettings('editor'); }} className="text-indigo-400 hover:text-indigo-300">
                                        <PlusCircle size={14} />
                                    </button>
                                </div>

                                <div className="p-1 overflow-y-auto custom-scrollbar">
                                    {profiles.length === 0 && (
                                        <div className="p-4 text-center text-xs text-slate-500 italic">
                                            No profiles found.<br />Click below to add one.
                                        </div>
                                    )}
                                    {profiles.map(p => (
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
                                            className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm group transition-all ${activeProfileId === p.id
                                                ? 'bg-indigo-600 text-white'
                                                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                                                } ${isActivating ? 'opacity-50 cursor-not-allowed' : ''}`}
                                        >
                                            <div className="flex items-center gap-3 overflow-hidden">
                                                <div className={`p-1 rounded shrink-0 ${activeProfileId === p.id ? 'bg-white/20' : 'bg-slate-800 group-hover:bg-slate-700'}`}>
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
                                        onClick={() => { setIsProfileMenuOpen(false); onOpenSettings('profiles'); }}
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
                                {activeModelConfig?.name || activeModelConfig?.id || (activeProfile ? 'Select Model' : 'No Config')}
                            </span>
                            {!isLoadingModels && activeModelConfig && renderCapabilities(activeModelConfig)}
                        </div>

                        <ChevronDown size={14} className={`text-slate-400 transition-transform duration-200 ml-1 ${isModelMenuOpen ? 'rotate-180' : ''}`} />
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
                                            <p>No compatible models found for this profile in <b>{appMode}</b> mode.</p>
                                            <button type="button" onClick={() => onOpenSettings('editor')} className="text-indigo-400 hover:underline text-xs">Verify Config</button>
                                        </div>
                                    )}

                                    {filteredModels.map((model) => {
                                        const Icon = getModelIcon(model);
                                        const isSelected = currentModelId === model.id;
                                        return (
                                            <button
                                                key={model.id}
                                                type="button"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    onModelSelect(model.id);
                                                }}
                                                className={`flex items-start gap-3 p-3 rounded-lg transition-colors text-left ${isSelected
                                                    ? 'bg-slate-800 border border-slate-700'
                                                    : 'hover:bg-slate-800/50 border border-transparent'
                                                    }`}
                                            >
                                                <div className={`mt-0.5 p-2 rounded-lg ${isSelected ? 'bg-indigo-500 text-white' : 'bg-slate-800 text-slate-400'}`}>
                                                    <Icon size={18} />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center justify-between mb-0.5">
                                                        <div className="flex items-center gap-2 overflow-hidden w-full">
                                                            <span className={`text-sm font-medium truncate ${isSelected ? 'text-white' : 'text-slate-300'}`} title={model.id}>
                                                                {model.name || model.id}
                                                            </span>
                                                            {renderCapabilities(model)}
                                                        </div>
                                                        {isSelected && <Check size={14} className="text-indigo-400 shrink-0 ml-2" />}
                                                    </div>
                                                    {/* ✅ 显示描述（如果存在且与ID不同，且不包含ID的主要部分） */}
                                                    {(() => {
                                                        if (!model.description || model.description === model.id) {
                                                            return null;
                                                        }
                                                        // 检查描述是否包含ID的主要关键词（避免重复显示）
                                                        const idWords = model.id.toLowerCase().split(/[-_\s]+/).filter(w => w.length > 2);
                                                        const descLower = model.description.toLowerCase();
                                                        const hasMajorOverlap = idWords.some(word => descLower.includes(word));
                                                        // 如果描述包含ID的主要部分，则不显示描述
                                                        if (hasMajorOverlap && idWords.length > 2) {
                                                            return null;
                                                        }
                                                        return (
                                                            <div className="text-xs text-slate-500 leading-tight truncate" title={model.description}>
                                                                {model.description}
                                                            </div>
                                                        );
                                                    })()}
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
                                        <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">{filteredModels.length}</span>
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

            {isUserInfoDialogOpen && typeof document !== 'undefined' && createPortal(
                <>
                    <div
                        className="fixed inset-0 z-[160] bg-black/60"
                        onClick={closeUserInfoDialog}
                    />
                    <div className="fixed inset-0 z-[161] flex items-center justify-center p-4">
                        <div className="w-full max-w-lg bg-slate-900 border border-slate-700 rounded-xl shadow-2xl ring-1 ring-black/50">
                            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
                                <h3 className="text-base font-semibold text-white">{isEditingPassword ? '修改密码' : '用户信息'}</h3>
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
                                                <span className={`text-slate-200 ${item.field === 'id' || item.field === 'email' ? 'break-all' : ''}`}>
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
                                        <label htmlFor="currentPassword" className="text-sm text-slate-300">当前密码</label>
                                        <input
                                            id="currentPassword"
                                            type="password"
                                            value={passwordForm.currentPassword}
                                            onChange={(e) => setPasswordForm(prev => ({ ...prev, currentPassword: e.target.value }))}
                                            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                                            required
                                            autoComplete="current-password"
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label htmlFor="newPassword" className="text-sm text-slate-300">新密码</label>
                                        <input
                                            id="newPassword"
                                            type="password"
                                            value={passwordForm.newPassword}
                                            onChange={(e) => setPasswordForm(prev => ({ ...prev, newPassword: e.target.value }))}
                                            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                                            required
                                            minLength={8}
                                            autoComplete="new-password"
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label htmlFor="confirmPassword" className="text-sm text-slate-300">确认新密码</label>
                                        <input
                                            id="confirmPassword"
                                            type="password"
                                            value={passwordForm.confirmPassword}
                                            onChange={(e) => setPasswordForm(prev => ({ ...prev, confirmPassword: e.target.value }))}
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
            )}

            {isSystemConfigDialogOpen && currentUser?.isAdmin && typeof document !== 'undefined' && createPortal(
                <>
                    <div
                        className="fixed inset-0 z-[170] bg-black/60"
                        onClick={closeSystemConfigDialog}
                    />
                    <div className="fixed inset-0 z-[171] flex items-center justify-center p-4">
                        <div className="w-full max-w-5xl max-h-[90vh] bg-slate-900 border border-slate-700 rounded-xl shadow-2xl ring-1 ring-black/50 flex flex-col overflow-hidden">
                            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
                                <div>
                                    <h3 className="text-base font-semibold text-white">系统配置</h3>
                                    <p className="text-xs text-slate-400 mt-0.5">仅管理员可见，保存后立即生效</p>
                                </div>
                                <button
                                    type="button"
                                    onClick={closeSystemConfigDialog}
                                    className="p-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
                                    disabled={isSavingSystemConfig}
                                >
                                    <X size={16} />
                                </button>
                            </div>

                            <div className="flex-1 overflow-y-auto p-5 grid grid-cols-1 lg:grid-cols-2 gap-5">
                                <section className="space-y-4">
                                    <h4 className="text-sm font-semibold text-white">常用配置</h4>

                                    {isLoadingSystemConfig ? (
                                        <div className="h-36 flex items-center justify-center text-slate-400 text-sm">
                                            <Loader2 size={16} className="animate-spin mr-2" />
                                            加载系统配置...
                                        </div>
                                    ) : (
                                        <div className="space-y-3">
                                            {configFields.map((field) => {
                                                const value = editedSystemConfig[field.key];
                                                if (field.type === 'boolean') {
                                                    return (
                                                        <label
                                                            key={field.key}
                                                            className="flex items-center justify-between p-3 rounded-lg border border-slate-800 bg-slate-950/50"
                                                        >
                                                            <div className="pr-4">
                                                                <div className="text-sm text-slate-200">{field.label}</div>
                                                                {field.description && (
                                                                    <div className="text-xs text-slate-500 mt-1">{field.description}</div>
                                                                )}
                                                            </div>
                                                            <button
                                                                type="button"
                                                                onClick={() => handleSystemConfigValueChange(field.key, 'boolean', !(value === true))}
                                                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                                                                    value ? 'bg-indigo-500' : 'bg-slate-700'
                                                                }`}
                                                                aria-pressed={value === true}
                                                                disabled={field.editable === false}
                                                            >
                                                                <span
                                                                    className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${
                                                                        value ? 'translate-x-5' : 'translate-x-1'
                                                                    }`}
                                                                />
                                                            </button>
                                                        </label>
                                                    );
                                                }

                                                return (
                                                    <div key={field.key} className="p-3 rounded-lg border border-slate-800 bg-slate-950/50 space-y-2">
                                                        <div>
                                                            <div className="text-sm text-slate-200">{field.label}</div>
                                                            {field.description && (
                                                                <div className="text-xs text-slate-500 mt-1">{field.description}</div>
                                                            )}
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <input
                                                                type={field.type === 'number' ? 'number' : 'text'}
                                                                value={value === null || value === undefined ? '' : String(value)}
                                                                min={field.min}
                                                                max={field.max}
                                                                step={field.step || 1}
                                                                onChange={(e) => handleSystemConfigValueChange(field.key, field.type, e.target.value)}
                                                                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                                                                disabled={field.editable === false}
                                                            />
                                                            {field.unit && (
                                                                <span className="text-xs text-slate-500 whitespace-nowrap">{field.unit}</span>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })}

                                            {configFields.length === 0 && (
                                                <div className="text-sm text-slate-500">暂无可配置字段</div>
                                            )}
                                        </div>
                                    )}

                                    {systemConfigError && (
                                        <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                                            {systemConfigError}
                                        </div>
                                    )}
                                </section>

                                <section className="space-y-4">
                                    <div className="flex items-center justify-between">
                                        <h4 className="text-sm font-semibold text-white">系统运行状态</h4>
                                        <button
                                            type="button"
                                            onClick={() => loadSystemStatus()}
                                            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                                        >
                                            <RefreshCw size={13} />
                                            刷新
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => setIsCleanupConfirmOpen(true)}
                                            disabled={isCleaningUp}
                                            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg text-red-400 hover:text-red-300 hover:bg-red-500/10 border border-red-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {isCleaningUp ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                                            {isCleaningUp ? '清理中...' : '清理垃圾'}
                                        </button>
                                    </div>

                                    {isLoadingSystemStatus ? (
                                        <div className="h-36 flex items-center justify-center text-slate-400 text-sm">
                                            <Loader2 size={16} className="animate-spin mr-2" />
                                            加载系统状态...
                                        </div>
                                    ) : (
                                        <div className="space-y-3">
                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                                <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50">
                                                    <div className="flex items-center justify-between mb-1">
                                                        <span className="text-xs text-slate-400 inline-flex items-center gap-1.5"><Activity size={13} /> CPU</span>
                                                        <span className="text-sm text-white">{formatPercent(systemStatus?.metrics.cpu.usagePercent)}</span>
                                                    </div>
                                                    <div className="h-1.5 rounded bg-slate-800 overflow-hidden">
                                                        <div
                                                            className="h-full bg-indigo-500 transition-all"
                                                            style={{ width: `${Math.max(0, Math.min(100, systemStatus?.metrics.cpu.usagePercent || 0))}%` }}
                                                        />
                                                    </div>
                                                </div>

                                                <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50">
                                                    <div className="flex items-center justify-between mb-1">
                                                        <span className="text-xs text-slate-400 inline-flex items-center gap-1.5"><Cpu size={13} /> 内存</span>
                                                        <span className="text-sm text-white">{formatPercent(systemStatus?.metrics.memory.usagePercent)}</span>
                                                    </div>
                                                    <div className="text-xs text-slate-500">
                                                        {formatBytes(systemStatus?.metrics.memory.usedBytes)} / {formatBytes(systemStatus?.metrics.memory.totalBytes)}
                                                    </div>
                                                </div>

                                                <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50">
                                                    <div className="flex items-center justify-between mb-1">
                                                        <span className="text-xs text-slate-400 inline-flex items-center gap-1.5"><HardDrive size={13} /> 磁盘</span>
                                                        <span className="text-sm text-white">{formatPercent(systemStatus?.metrics.disk.usagePercent)}</span>
                                                    </div>
                                                    <div className="text-xs text-slate-500">
                                                        {formatBytes(systemStatus?.metrics.disk.usedBytes)} / {formatBytes(systemStatus?.metrics.disk.totalBytes)}
                                                    </div>
                                                    <div className="text-xs text-slate-500 mt-1">
                                                        R {formatBytes(systemStatus?.metrics.disk.readRateBps ?? undefined)}/s · W {formatBytes(systemStatus?.metrics.disk.writeRateBps ?? undefined)}/s
                                                    </div>
                                                </div>

                                                <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50">
                                                    <div className="flex items-center justify-between mb-1">
                                                        <span className="text-xs text-slate-400 inline-flex items-center gap-1.5"><Network size={13} /> 网络</span>
                                                        <span className="text-sm text-white">{formatPercent(systemStatus?.metrics.network.usagePercent)}</span>
                                                    </div>
                                                    <div className="text-xs text-slate-500">
                                                        ↑ {formatBytes(systemStatus?.metrics.network.txRateBps ?? undefined)}/s · ↓ {formatBytes(systemStatus?.metrics.network.rxRateBps ?? undefined)}/s
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50 text-xs text-slate-500 space-y-1">
                                                <div>主机: {systemStatus?.host.hostname || '—'}</div>
                                                <div>平台: {systemStatus?.host.platform || '—'}</div>
                                                <div>CPU 核数: {systemStatus?.host.cpuCount ?? '—'}</div>
                                                <div>服务运行时长: {systemStatus?.host.processUptimeSeconds ?? 0}s</div>
                                                <div>指标采集器: {systemStatus?.collector || '—'}</div>
                                                {systemStatus?.collector === 'fallback' && (
                                                    <div className="text-amber-400">当前为降级采集，内存/网络/磁盘速率需要安装 psutil</div>
                                                )}
                                            </div>
                                        </div>
                                    )}

                                    {systemStatusError && (
                                        <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                                            {systemStatusError}
                                        </div>
                                    )}
                                </section>
                            </div>

                            <div className="px-5 py-4 border-t border-slate-800 flex items-center justify-end gap-2">
                                <button
                                    type="button"
                                    onClick={closeSystemConfigDialog}
                                    className="px-4 py-2 text-sm rounded-lg text-slate-300 hover:bg-slate-800 transition-colors"
                                    disabled={isSavingSystemConfig}
                                >
                                    关闭
                                </button>
                                <button
                                    type="button"
                                    onClick={handleSaveSystemConfig}
                                    className="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-60 disabled:cursor-not-allowed inline-flex items-center gap-2"
                                    disabled={!hasSystemConfigChanges || isSavingSystemConfig || isLoadingSystemConfig}
                                >
                                    {isSavingSystemConfig && <Loader2 size={14} className="animate-spin" />}
                                    保存配置
                                </button>
                            </div>
                        </div>
                    </div>
                </>,
                document.body
            )}
            {isCleanupConfirmOpen && typeof document !== 'undefined' && createPortal(
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
