
import React, { useState, useEffect } from 'react';
import { PlusCircle, Database, Trash2, Edit3, Check, Layers, List, Copy, Zap, Cpu, Globe, Sparkles, Server, AlertTriangle, ChevronLeft, Loader2, Eye, Box, MoreHorizontal } from 'lucide-react';
import { ConfigProfile } from '../../../services/db';
import { ModelConfig, ApiProtocol } from '../../../types/types';
import { LLMFactory } from '../../../services/LLMFactory';
import { getAuthHeaders } from '../../../services/apiClient';
import { v4 as uuidv4 } from 'uuid';

interface ProfilesTabProps {
    profiles: ConfigProfile[];
    activeProfileId: string | null;
    onActivateProfile: (id: string) => Promise<void>;
    onDeleteProfile: (id: string) => Promise<void>;
    onSaveProfile: (profile: ConfigProfile) => Promise<void>; // Needed for duplicate/update
    onEditProfile: (profile: ConfigProfile) => void;
    onCreateNew: () => void;
}

export const ProfilesTab: React.FC<ProfilesTabProps> = ({
    profiles,
    activeProfileId,
    onActivateProfile,
    onDeleteProfile,
    onSaveProfile,
    onEditProfile,
    onCreateNew
}) => {
    // --- Local State for Inspection ---
    const [previewProfile, setPreviewProfile] = useState<ConfigProfile | null>(null);
    const [previewModels, setPreviewModels] = useState<ModelConfig[]>([]);
    const [isPreviewLoading, setIsPreviewLoading] = useState(false);
    const [previewError, setPreviewError] = useState<string | null>(null);

    // --- Local State for Deletion ---
    const [deleteConfirmationId, setDeleteConfirmationId] = useState<string | null>(null);
    const [openMenuId, setOpenMenuId] = useState<string | null>(null);

    const handleDeleteRequest = (id: string) => {
        if (deleteConfirmationId === id) {
            void onDeleteProfile(id);
            setDeleteConfirmationId(null);
            setOpenMenuId(null);
            return;
        }
        setDeleteConfirmationId(id);
        setOpenMenuId(id);
        window.setTimeout(() => {
            setDeleteConfirmationId((prev) => (prev === id ? null : prev));
        }, 3000);
    };

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            const target = event.target as HTMLElement | null;
            if (target?.closest('[data-profile-card-actions]')) {
                return;
            }
            setOpenMenuId(null);
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, []);

    // --- 日志：记录 profiles 数据（仅在开发模式下且数据变化时） ---
    useEffect(() => {
        // 始终输出日志以便调试
        const profileCount = profiles?.length || 0;
        console.log('[ProfilesTab] Profiles data:', {
            count: profileCount,
            activeProfileId,
            isArray: Array.isArray(profiles),
            profiles: profiles?.map(p => ({
                id: p.id?.substring(0, 8) + '...' || 'no-id',
                name: p.name || 'no-name',
                providerId: p.providerId || 'no-provider',
                isActive: p.id === activeProfileId
            })) || [],
            timestamp: new Date().toISOString()
        });
        
        if (profileCount === 0 && profiles) {
            console.warn('[ProfilesTab] Profiles array is empty but exists');
        }
    }, [profiles, activeProfileId]);

    const getProviderIcon = (pid: string) => {
        if (pid.includes('google')) return <Zap size={20} />;
        if (pid.includes('deepseek')) return <Cpu size={20} />;
        if (pid.includes('tongyi')) return <Globe size={20} />;
        if (pid.includes('openai')) return <Sparkles size={20} />;
        return <Server size={20} />;
    };

    const handleDuplicate = (profile: ConfigProfile) => {
        const copy: ConfigProfile = {
            ...profile,
            id: uuidv4(),
            name: `${profile.name} (Copy)`,
            createdAt: Date.now(),
            updatedAt: Date.now()
        };
        onSaveProfile(copy);
    };

    const handleInspectProfile = async (profile: ConfigProfile) => {
        setPreviewProfile(profile);
        setPreviewError(null);
        setPreviewModels([]);

        // Fetch live models
        setIsPreviewLoading(true);
        try {
            // ✅ 使用后端 API 获取模型列表
            // 后端会自动从数据库读取并解密 API key
            // 这样前端不需要处理加密的 API key
            const response = await fetch(`/api/models/${profile.providerId}?use_cache=false`, {
                headers: getAuthHeaders(),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Failed to get models: ${response.statusText}`);
            }

            const data = await response.json();
            const models = data.models || [];

            if (models.length > 0) {
                setPreviewModels(models);
                // Update cache count in background if it changed
                if (profile.cachedModelCount !== models.length) {
                    onSaveProfile({ ...profile, cachedModelCount: models.length, savedModels: models });
                }
            } else {
                setPreviewError("No models found. Check API Key or connectivity.");
            }
        } catch (e: any) {
            setPreviewError(e.message || "Failed to fetch models.");
        } finally {
            setIsPreviewLoading(false);
        }
    };

    // If inspecting, show the overlay
    if (previewProfile) {
        return (
            <div className="absolute inset-0 bg-slate-950 z-10 flex flex-col animate-[fadeIn_0.2s_ease-out]">
                <div className="flex items-center gap-3 p-4 border-b border-slate-800 bg-slate-900/50">
                    <button
                        onClick={() => setPreviewProfile(null)}
                        className="p-2 hover:bg-slate-800 rounded-full text-slate-400 hover:text-white"
                    >
                        <ChevronLeft size={20} />
                    </button>
                    <div>
                        <h3 className="font-bold text-slate-200">Models for: {previewProfile.name}</h3>
                        <p className="text-xs text-slate-500">Live fetch using stored credentials</p>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                    {isPreviewLoading ? (
                        <div className="flex flex-col items-center justify-center h-48 text-slate-500 gap-3">
                            <Loader2 size={24} className="animate-spin text-indigo-500" />
                            <span>Fetching models...</span>
                        </div>
                    ) : previewError ? (
                        <div className="p-4 bg-red-900/20 border border-red-900/50 rounded-xl text-red-300 flex items-start gap-3">
                            <AlertTriangle size={18} className="mt-0.5" />
                            <div>
                                <div className="font-bold mb-1">Fetch Failed</div>
                                <div className="text-sm opacity-90">{previewError}</div>
                            </div>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {previewModels.map(m => {
                                const isHidden = previewProfile.hiddenModels.includes(m.id);
                                return (
                                    <div key={m.id} className={`p-3 rounded-xl border flex flex-col ${isHidden
                                        ? 'bg-slate-900/30 border-slate-800 opacity-60'
                                        : 'bg-slate-900 border-slate-700'
                                        }`}>
                                        <div className="flex items-start gap-3 mb-2">
                                            <div className={`p-2 rounded-lg shrink-0 ${isHidden ? 'bg-slate-800 text-slate-600' : 'bg-indigo-500/10 text-indigo-400'}`}>
                                                {m.capabilities.vision ? <Eye size={16} /> : <Box size={16} />}
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <div className="text-sm font-medium text-slate-200 break-words">{m.name}</div>
                                                <div className="text-xs text-slate-500 font-mono break-all">{m.id}</div>
                                            </div>
                                        </div>
                                        {isHidden && (
                                            <div className="mt-auto pt-2 border-t border-slate-800">
                                                <span className="text-[10px] bg-slate-800 px-2 py-1 rounded text-slate-500 font-medium">Hidden</span>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                            {previewModels.length === 0 && !isPreviewLoading && (
                                <div className="col-span-full text-center py-8 text-slate-500">No models returned by the API.</div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // Main List View
    // ✅ 防御性检查：确保 profiles 总是有效数组
    const safeProfiles = profiles || [];
    
    return (
        <div className="absolute inset-0 flex flex-col p-3 md:p-3 space-y-3">
            <div className="shrink-0 flex items-center justify-between pb-3 border-b border-slate-800">
                <div>
                    <h3 className="text-base md:text-lg font-medium text-white mb-0.5">Configuration Profiles ({safeProfiles.length})</h3>
                    <p className="text-xs text-slate-500">Manage API setups. Active profile is used for chat.</p>
                </div>
                <button
                    onClick={onCreateNew}
                    className="flex items-center gap-2 px-3 py-1.5 md:px-4 md:py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs md:text-sm font-medium transition-colors shadow-lg shadow-indigo-500/20"
                >
                    <PlusCircle size={14} className="md:w-4 md:h-4" /> <span className="hidden md:inline">New Config</span><span className="md:hidden">New</span>
                </button>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar pr-1 pb-4">
                {safeProfiles.length === 0 ? (
                    <div className="text-center py-16 bg-slate-900/30 rounded-xl border border-slate-800 h-full flex flex-col items-center justify-center">
                        <Database className="mx-auto mb-4 text-slate-600" size={40} />
                        <p className="text-slate-400 mb-2 text-sm">No configuration profile</p>
                        <p className="text-slate-500 text-xs mb-4">Click the button above to add one.</p>
                        <button
                            onClick={onCreateNew}
                            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-medium transition-colors shadow-lg shadow-indigo-500/20"
                        >
                            <PlusCircle size={16} />
                            <span>Create First Config</span>
                        </button>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                        {safeProfiles.map((p) => {
                            const isActive = p.id === activeProfileId;
                            const isDeleting = deleteConfirmationId === p.id;
                            const isMenuOpen = openMenuId === p.id;

                            let activeBorder = 'border-indigo-500/50';
                            let activeBg = 'bg-indigo-600';
                            if (p.providerId.includes('deepseek')) { activeBorder = 'border-blue-500/50'; activeBg = 'bg-blue-600'; }
                            else if (p.providerId.includes('tongyi')) { activeBorder = 'border-purple-500/50'; activeBg = 'bg-purple-600'; }
                            else if (p.providerId.includes('openai')) { activeBorder = 'border-emerald-500/50'; activeBg = 'bg-emerald-600'; }
                            else if (p.providerId.includes('google')) { activeBorder = 'border-orange-500/50'; activeBg = 'bg-orange-600'; }

                            return (
                                <div
                                    key={p.id}
                                    className={`group rounded-xl border p-4 md:p-5 h-full flex flex-col transition-all ${isActive
                                        ? `bg-slate-900 border ${activeBorder} shadow-[0_0_15px_rgba(0,0,0,0.3)]`
                                        : 'bg-slate-900/50 border-slate-800 hover:border-slate-700'
                                        }`}
                                >
                                    <div className="flex items-start justify-between gap-2 mb-2">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <div className={`p-2 rounded-lg shrink-0 ${isActive ? `${activeBg} text-white` : 'bg-slate-800 text-slate-500'}`}>
                                                {getProviderIcon(p.providerId)}
                                            </div>
                                            <h4 className="text-sm md:text-base font-medium text-slate-200 truncate">
                                                {p.name}
                                            </h4>
                                            <div className="relative shrink-0" data-profile-card-actions>
                                                <button
                                                    type="button"
                                                    onClick={() => setOpenMenuId((prev) => (prev === p.id ? null : p.id))}
                                                    className={`p-1.5 rounded-lg border border-slate-700 bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 transition-all ${isMenuOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 group-focus-within:opacity-100'
                                                        }`}
                                                    title="Actions"
                                                >
                                                    <MoreHorizontal size={14} />
                                                </button>

                                                {isMenuOpen && (
                                                    <div className="absolute left-0 top-9 z-20 w-40 rounded-lg border border-slate-700 bg-slate-900 shadow-xl p-1">
                                                        <button
                                                            type="button"
                                                            onClick={() => {
                                                                handleInspectProfile(p);
                                                                setOpenMenuId(null);
                                                            }}
                                                            className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
                                                        >
                                                            <List size={13} />
                                                            <span>View Models</span>
                                                        </button>

                                                        {!isActive && (
                                                            <button
                                                                type="button"
                                                                onClick={() => {
                                                                    void onActivateProfile(p.id);
                                                                    setOpenMenuId(null);
                                                                }}
                                                                className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
                                                            >
                                                                <Check size={13} />
                                                                <span>Activate</span>
                                                            </button>
                                                        )}

                                                        <button
                                                            type="button"
                                                            onClick={() => {
                                                                handleDuplicate(p);
                                                                setOpenMenuId(null);
                                                            }}
                                                            className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
                                                        >
                                                            <Copy size={13} />
                                                            <span>Duplicate</span>
                                                        </button>

                                                        <button
                                                            type="button"
                                                            onClick={() => {
                                                                onEditProfile(p);
                                                                setOpenMenuId(null);
                                                            }}
                                                            className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
                                                        >
                                                            <Edit3 size={13} />
                                                            <span>Edit</span>
                                                        </button>

                                                        <button
                                                            type="button"
                                                            onClick={() => handleDeleteRequest(p.id)}
                                                            className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-red-300 hover:bg-red-900/30 rounded"
                                                        >
                                                            <Trash2 size={13} />
                                                            <span>{isDeleting ? 'Confirm Delete' : 'Delete'}</span>
                                                        </button>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-1 shrink-0">
                                            <span className="px-1.5 py-0.5 bg-slate-800/80 text-slate-300 text-[10px] font-mono rounded border border-slate-700 uppercase">
                                                {p.providerId}
                                            </span>
                                            {isActive && (
                                                <span className="px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] font-medium rounded border border-emerald-500/30">
                                                    Active
                                                </span>
                                            )}
                                        </div>
                                    </div>

                                    <div className="text-xs text-slate-500 font-mono break-all">
                                        {p.apiKey ? `Key: ...${p.apiKey.slice(-4)}` : 'No API key configured'}
                                    </div>

                                    <div className="mt-2 text-xs text-slate-400 inline-flex items-center gap-1.5">
                                        <Layers size={12} />
                                        {p.cachedModelCount !== undefined ? (
                                            <span>{p.cachedModelCount} Models</span>
                                        ) : (
                                            <span className="italic opacity-60">Model count unknown</span>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};
