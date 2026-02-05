
import React, { useState, useEffect } from 'react';
import { PlusCircle, Database, Trash2, Edit3, Check, Layers, List, Copy, Zap, Cpu, Globe, Sparkles, Server, AlertTriangle, ChevronLeft, Loader2, Eye, Box } from 'lucide-react';
import { ConfigProfile } from '../../../services/db';
import { ModelConfig, ApiProtocol } from '../../../types/types';
import { LLMFactory } from '../../../services/LLMFactory';
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
    const [expandedProfileId, setExpandedProfileId] = useState<string | null>(null);

    // --- Local State for Inspection ---
    const [previewProfile, setPreviewProfile] = useState<ConfigProfile | null>(null);
    const [previewModels, setPreviewModels] = useState<ModelConfig[]>([]);
    const [isPreviewLoading, setIsPreviewLoading] = useState(false);
    const [previewError, setPreviewError] = useState<string | null>(null);

    // --- Local State for Deletion ---
    const [deleteConfirmationId, setDeleteConfirmationId] = useState<string | null>(null);

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
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
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

            <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-2 custom-scrollbar p-2 md:p-0.5 pb-4 md:pb-4">
                {safeProfiles.map(p => {
                    const isActive = p.id === activeProfileId;
                    const isDeleting = deleteConfirmationId === p.id;

                    let activeBorder = 'border-indigo-500/50';
                    let activeBg = 'bg-indigo-600';
                    if (p.providerId.includes('deepseek')) { activeBorder = 'border-blue-500/50'; activeBg = 'bg-blue-600'; }
                    else if (p.providerId.includes('tongyi')) { activeBorder = 'border-purple-500/50'; activeBg = 'bg-purple-600'; }
                    else if (p.providerId.includes('openai')) { activeBorder = 'border-emerald-500/50'; activeBg = 'bg-emerald-600'; }
                    else if (p.providerId.includes('google')) { activeBorder = 'border-orange-500/50'; activeBg = 'bg-orange-600'; }

                    return (
                        <div
                            key={p.id}
                            onClick={() => setExpandedProfileId(expandedProfileId === p.id ? null : p.id)}
                            className={`p-3 rounded-xl border flex flex-row items-center justify-between group transition-all shrink-0 h-auto gap-3 ${isActive
                                ? `bg-slate-900 border ${activeBorder} shadow-[0_0_15px_rgba(0,0,0,0.3)]`
                                : `bg-slate-900/40 border-slate-800 hover:border-slate-700`
                                } ${expandedProfileId === p.id ? 'ring-1 ring-indigo-500/50' : ''}`}>
                            <div className="flex items-center gap-3 flex-1 min-w-0">
                                <div className={`p-2 rounded-lg shrink-0 ${isActive ? `${activeBg} text-white` : 'bg-slate-800 text-slate-500'}`}>
                                    {getProviderIcon(p.providerId)}
                                </div>
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-2 mb-0.5">
                                        <h4 className="font-medium text-slate-200 text-sm md:text-base truncate">{p.name}</h4>
                                        {isActive && <span className={`text-[10px] ${isActive ? 'text-white/80' : 'text-slate-500'} px-1.5 py-0.5 rounded border border-white/20 font-bold shrink-0`}>Active</span>}
                                    </div>
                                    <div className="text-xs text-slate-500 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                                        <span className="flex items-center gap-1.5">
                                            <span className={`font-mono px-1.5 py-0 rounded bg-slate-800/50 text-slate-400`}>
                                                {p.providerId}
                                            </span>
                                            <span className="text-slate-600 hidden md:inline">•</span>
                                            <span className="font-mono text-slate-500 hidden md:inline">
                                                {p.apiKey ? `...${p.apiKey.slice(-4)}` : 'No Key'}
                                            </span>
                                        </span>
                                        <span className="flex items-center gap-1 text-slate-400">
                                            <Layers size={10} />
                                            {p.cachedModelCount !== undefined ? (
                                                <span>{p.cachedModelCount} Models</span>
                                            ) : (
                                                <span className="italic opacity-50">Unknown</span>
                                            )}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-center justify-end gap-1.5 shrink-0 ml-2">
                                {isDeleting ? (
                                    <div className="flex items-center bg-red-900/20 border border-red-900/50 rounded-lg p-1 animate-[fadeIn_0.2s_ease-out]">
                                        <span className="text-xs text-red-300 font-medium px-2">Delete?</span>
                                        <button
                                            onClick={() => { onDeleteProfile(p.id); setDeleteConfirmationId(null); }}
                                            className="px-2 py-1 bg-red-600 hover:bg-red-500 text-white rounded text-xs mr-1 transition-colors"
                                        >
                                            Yes
                                        </button>
                                        <button
                                            onClick={() => setDeleteConfirmationId(null)}
                                            className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded text-xs transition-colors"
                                        >
                                            No
                                        </button>
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-1 opacity-100">
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleInspectProfile(p); }}
                                            className="p-1.5 bg-slate-800 hover:bg-slate-700 hover:text-white text-slate-400 rounded-lg transition-colors border border-slate-700"
                                            title="View Available Models"
                                        >
                                            <List size={16} className="md:w-[14px] md:h-[14px]" />
                                        </button>
                                        {!isActive && (
                                            <button
                                                onClick={(e) => { e.stopPropagation(); onActivateProfile(p.id); }}
                                                className="p-1.5 bg-slate-800 hover:bg-green-600 hover:text-white text-slate-400 rounded-lg transition-colors border border-slate-700"
                                                title="Activate"
                                            >
                                                <Check size={16} className="md:w-[14px] md:h-[14px]" />
                                            </button>
                                        )}
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleDuplicate(p); }}
                                            className="p-1.5 bg-slate-800 hover:bg-slate-600 hover:text-white text-slate-400 rounded-lg transition-colors border border-slate-700"
                                            title="Duplicate"
                                        >
                                            <Copy size={16} className="md:w-[14px] md:h-[14px]" />
                                        </button>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); onEditProfile(p); }}
                                            className="p-1.5 bg-slate-800 hover:bg-blue-600 hover:text-white text-slate-400 rounded-lg transition-colors border border-slate-700"
                                            title="Edit"
                                        >
                                            <Edit3 size={16} className="md:w-[14px] md:h-[14px]" />
                                        </button>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); setDeleteConfirmationId(p.id); }}
                                            className="p-1.5 bg-slate-800 hover:bg-red-600 hover:text-white text-slate-400 rounded-lg transition-colors border border-slate-700"
                                            title="Delete"
                                        >
                                            <Trash2 size={16} className="md:w-[14px] md:h-[14px]" />
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
                {safeProfiles.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="text-slate-400 mb-4 text-sm">还没有配置任何提供商</div>
                        <button
                            onClick={onCreateNew}
                            className="flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-medium transition-colors shadow-lg shadow-indigo-500/20"
                        >
                            <PlusCircle size={18} />
                            <span>创建第一个配置</span>
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};
