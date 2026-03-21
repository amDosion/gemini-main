
import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Save, Key, Shield, RefreshCw, CheckCircle2, AlertTriangle, Check, Loader2, X } from 'lucide-react';
import { ConfigProfile, db } from '../../../services/db';
import { ModelConfig, ApiProtocol } from '../../../types/types';
import { getProviderTemplates, AIProviderConfig } from '../../../services/providers';
import { LLMFactory } from '../../../services/LLMFactory';
import { v4 as uuidv4 } from 'uuid';
import { OllamaModelManager } from './OllamaModelManager';
import { useToastContext } from '../../../contexts/ToastContext';

interface EditorTabProps {
    initialData?: ConfigProfile | null;
    existingProfiles?: ConfigProfile[]; // 用于智能切换 Provider 时查找已有配置
    onSave: (profile: ConfigProfile) => Promise<void>;
    onClose: () => void;
    footerNode?: HTMLDivElement | null;
}

export const EditorTab: React.FC<EditorTabProps> = ({
    initialData,
    existingProfiles,
    onSave,
    onClose,
    footerNode
}) => {
    const { showWarning } = useToastContext();
    const [formData, setFormData] = useState<ConfigProfile | null>(null);

    // Verification State
    const [verifiedModels, setVerifiedModels] = useState<ModelConfig[]>([]);
    const [isVerifying, setIsVerifying] = useState(false);
    const [verifyError, setVerifyError] = useState<string | null>(null);

    // ✅ Provider Templates State (从后端 API 加载)
    const [providerTemplates, setProviderTemplates] = useState<AIProviderConfig[]>([]);
    const [isLoadingTemplates, setIsLoadingTemplates] = useState(true);
    const [templatesError, setTemplatesError] = useState<string | null>(null);

    /**
     * 根据 providerId 查找已有配置
     * 如果存在多个，返回最近更新的
     * @param providerId Provider ID
     * @param profiles 配置列表
     * @param excludeId 排除的配置 ID（通常是当前编辑的配置）
     * @returns 找到的配置或 null
     */
    const findProviderConfig = (
        providerId: string,
        profiles: ConfigProfile[],
        excludeId?: string
    ): ConfigProfile | null => {
        try {
            const matchingProfiles = profiles.filter(
                p => p.providerId === providerId && p.id !== excludeId
            );
            
            if (matchingProfiles.length === 0) {
                return null;
            }
            
            // 返回最近更新的配置
            return matchingProfiles.reduce((latest, current) => 
                current.updatedAt > latest.updatedAt ? current : latest
            );
        } catch (error) {
            return null;
        }
    };

    /**
     * 确保编辑器中使用的是可验证的明文 API Key。
     * existingProfiles 来自 /settings/full（默认非 edit_mode），其中 key 可能是加密值。
     */
    const resolveDecryptedProfile = async (profile: ConfigProfile): Promise<ConfigProfile> => {
        const apiKey = profile.apiKey || '';
        if (!apiKey.startsWith('gAAAAA')) {
            return profile;
        }

        const decryptedProfiles = await db.getProfiles(true);
        const decrypted = decryptedProfiles.find(p => p.id === profile.id);
        if (decrypted) {
            return decrypted;
        }

        return profile;
    };

    // ✅ 加载 Provider Templates
    useEffect(() => {
        const loadTemplates = async () => {
            try {
                setIsLoadingTemplates(true);
                const templates = await getProviderTemplates();
                setProviderTemplates(templates);
                setTemplatesError(null);
                
            } catch (error) {
                setTemplatesError((error instanceof Error ? error.message : String(error)) || 'Failed to load provider templates');
                // 不使用降级配置，显示错误状态
                setProviderTemplates([]);
            } finally {
                setIsLoadingTemplates(false);
            }
        };
        
        loadTemplates();
    }, []);

    // Initialize Form
    useEffect(() => {
        if (initialData) {
            // ✅ 编辑现有配置：需要获取解密后的 API Key 以便验证连接
            // 如果 initialData 中的 apiKey 是加密的（以 gAAAAA 开头），需要重新获取解密版本
            const loadDecryptedProfile = async () => {
                try {
                    // ✅ 使用 edit_mode=true 获取解密后的配置
                    const decryptedProfiles = await db.getProfiles(true);
                    const decryptedProfile = decryptedProfiles.find(p => p.id === initialData.id);
                    
                    if (decryptedProfile) {
                        // ✅ 使用解密后的配置（包含解密的 API Key）
                        setFormData({ ...decryptedProfile });
                        setVerifiedModels(decryptedProfile.savedModels || []);
                        
                    } else {
                        // 如果找不到，使用原始数据（可能是新创建的配置）
                        setFormData({ ...initialData });
                        setVerifiedModels(initialData.savedModels || []);
                    }
                } catch (error) {
                    // 降级：使用原始数据
                    setFormData({ ...initialData });
                    setVerifiedModels(initialData.savedModels || []);
                }
            };
            
            loadDecryptedProfile();
        } else if (!initialData && providerTemplates.length > 0) {
            // 创建新配置：初始化空白表单
            // ✅ 使用第一个 Provider Template 作为默认配置
            const firstTemplate = providerTemplates[0];
            const googleTemplate = providerTemplates.find(p => p.id === 'google') || firstTemplate;
            
            
            setFormData({
                id: uuidv4(),
                name: `${googleTemplate.name} Config`,  // ✅ 使用 Provider Template 名称作为默认配置名称
                providerId: googleTemplate.id,
                apiKey: '',
                baseUrl: googleTemplate?.baseUrl || '',  // ✅ 使用 Template 的 baseUrl
                protocol: googleTemplate.protocol,
                isProxy: !!googleTemplate.isCustom,
                hiddenModels: [],
                cachedModelCount: 0,
                savedModels: [],
                createdAt: Date.now(),
                updatedAt: Date.now()
            });
            setVerifiedModels([]);
        }
        setVerifyError(null);
    }, [initialData, providerTemplates]);  // ✅ 添加 providerTemplates 依赖

    const handleVerify = async () => {
        if (!formData) return;
        
        // ✅ 验证连接时，必须使用明文 API Key
        // formData.apiKey 在 EditorTab 中应该是解密的（通过 edit_mode=true 加载）
        // 如果仍然是加密的（以 gAAAAA 开头），验证会失败
        const apiKeyToVerify = formData.apiKey;
        if (apiKeyToVerify && apiKeyToVerify.startsWith('gAAAAA')) {
            setVerifyError('API Key is encrypted. Please reload the configuration.');
            setIsVerifying(false);
            return;
        }
        
        
        setIsVerifying(true);
        setVerifiedModels([]);
        setVerifyError(null);

        try {
            // ✅ 统一通过后端 API 验证
            // 前端只负责传递 URL 和 Key（明文），后端负责调用 Provider API
            const providerInstance = LLMFactory.getProvider(formData.protocol as ApiProtocol, formData.providerId);
            
            // ✅ 验证连接时强制不使用缓存，确保获取最新数据
            const models = await providerInstance.getAvailableModels(
                apiKeyToVerify,  // ✅ 使用明文 API Key 验证
                formData.baseUrl,
                false  // useCache = false，强制刷新
            );
            

            if (models.length > 0) {
                setVerifiedModels(models);

                setFormData(prev => {
                    if (!prev) return null;

                    // Smart Selection for Fresh Setup
                    let nextHidden = prev.hiddenModels;
                    if (prev.cachedModelCount === 0) {
                        // ✅ 使用动态加载的 providerTemplates
                        const templateConfig = providerTemplates.find(p => p.id === prev.providerId);
                        const defaultModelId = templateConfig?.defaultModel;

                        const visibleModel = (defaultModelId && models.find(m => m.id === defaultModelId))
                            || models.find(m => m.id.toLowerCase().includes('chat'))
                            || models[0];

                        nextHidden = models.filter(m => m.id !== visibleModel.id).map(m => m.id);
                    }

                    return {
                        ...prev,
                        cachedModelCount: models.length,
                        savedModels: models,
                        hiddenModels: nextHidden
                    };
                });
            } else {
                setVerifyError("Connection established, but no models were returned.");
            }
        } catch (e) {
            setVerifyError((e instanceof Error ? e.message : String(e)) || "Connection failed.");
        } finally {
            setIsVerifying(false);
        }
    };

    const handleSaveInternal = async () => {
        if (!formData) return;
        if (!formData.name.trim()) {
            showWarning('Please enter a configuration name.');
            return;
        }

        // ✅ 保存完整的 ModelConfig 对象数组到数据库
        // 后端会直接存储完整对象，前端加载时可以直接使用，无需再次调用 API
        // ✅ 重要：formData.apiKey 此时应该是明文（因为 EditorTab 中加载时已解密）
        // 后端会检查：如果是明文则加密保存，如果已经是加密的则直接保存
        const profileToSave: ConfigProfile = {
            ...formData,
            updatedAt: Date.now(),
            ...(verifiedModels.length > 0 && {
                savedModels: verifiedModels,  // ✅ 保存完整的 ModelConfig 对象，不是 ID 数组
                cachedModelCount: verifiedModels.length
            })
        };

        await onSave(profileToSave);
    };

    const toggleEditorModelVisibility = (id: string) => {
        if (!formData) return;
        const currentHidden = new Set(formData.hiddenModels);
        if (currentHidden.has(id)) currentHidden.delete(id);
        else currentHidden.add(id);

        setFormData({
            ...formData,
            hiddenModels: Array.from(currentHidden)
        });
    };

    if (!formData) {
        return (
            <div className="flex flex-col items-center justify-center h-48 text-slate-500">
                <Loader2 size={24} className="animate-spin text-indigo-500 mb-2" />
                <p>Initializing Editor...</p>
            </div>
        );
    }

    return (
        <>
            <div className="absolute inset-0 flex flex-col p-3 md:p-4 space-y-2 md:space-y-3 animate-[fadeIn_0.3s_ease-out]">

                <div className="border-b border-slate-800 flex justify-between items-center pb-2 shrink-0">
                    <div>
                        <h3 className="text-base md:text-lg font-medium text-white mb-0.5">
                            {initialData ? 'Edit Configuration' : 'New Configuration'}
                        </h3>
                        <p className="text-xs text-slate-500">Configure connection details.</p>
                    </div>
                    <div className="text-xs font-mono text-slate-600 bg-slate-900 px-2 py-1 rounded">
                        ID: {formData.id.slice(0, 8)}...
                    </div>
                </div>

                <div className="flex-1 flex flex-col min-h-0 space-y-2 md:space-y-3 overflow-y-auto custom-scrollbar pr-1 pb-24 md:pb-24">

                    {/* Name Input */}
                    <div className="space-y-1.5 shrink-0">
                                <label className="text-xs font-bold uppercase tracking-wider text-slate-500">Configuration Name</label>
                                <input
                                    type="text"
                                    value={formData.name}
                                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                                    placeholder="e.g. Work OpenAI"
                                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none text-slate-200 transition-colors"
                                />
                            </div>

                    {/* Template Selection */}
                    <div className="space-y-1.5 shrink-0">
                        <div className="flex justify-between items-center">
                            <label className="text-xs font-bold uppercase tracking-wider text-slate-500">Provider Template</label>
                            <span className="text-xs text-slate-600">Clicking applies default settings</span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2">
                            {isLoadingTemplates ? (
                                <div className="col-span-full text-center text-slate-500 text-xs py-4">
                                    <Loader2 size={14} className="inline animate-spin mr-2" />
                                    Loading providers...
                                </div>
                            ) : templatesError && providerTemplates.length === 0 ? (
                                <div className="col-span-full text-center text-red-400 text-xs py-4">
                                    {templatesError}
                                </div>
                            ) : (
                                providerTemplates.map(p => (
                                    <button
                                        key={p.id}
                                        onClick={async () => {
                                            // 查找该 Provider 的已有配置
                                            const existingConfig = existingProfiles 
                                                ? findProviderConfig(p.id, existingProfiles, formData?.id)
                                                : null;
                                            
                                            if (initialData) {
                                                // ========== 编辑模式：智能切换到已有配置 ==========
                                                if (existingConfig) {
                                                    const configToUse = await resolveDecryptedProfile(existingConfig);
                                                    // 找到已有配置：完全切换到该配置
                                                    setFormData({ ...configToUse });
                                                    setVerifiedModels(configToUse.savedModels || []);
                                                    
                                                } else {
                                                    // 未找到配置：应用模板默认值并清空用户数据
                                                    setFormData(prev => {
                                                        if (!prev) return null;
                                                        return {
                                                            ...prev,
                                                            providerId: p.id,
                                                            protocol: p.protocol,
                                                            baseUrl: p.baseUrl,
                                                            isProxy: !!p.isCustom,
                                                            name: `${p.name} Config`,
                                                            apiKey: '',
                                                            savedModels: [],
                                                            hiddenModels: [],
                                                            cachedModelCount: 0
                                                        };
                                                    });
                                                    setVerifiedModels([]);
                                                    
                                                }
                                            } else {
                                                // ========== 创建模式：应用模板默认值 ==========
                                                // 在创建模式下，始终应用模板默认值，不自动加载已有配置
                                                // 如果用户想基于已有配置创建，应该使用 Duplicate 功能
                                                setFormData(prev => {
                                                    if (!prev) return null;
                                                    return {
                                                        ...prev,
                                                        providerId: p.id,
                                                        protocol: p.protocol,
                                                        baseUrl: p.baseUrl,
                                                        isProxy: !!p.isCustom,
                                                        name: `${p.name} Config`
                                                    };
                                                });
                                                setVerifiedModels([]);
                                                
                                            }
                                        }}
                                        className={`flex items-center gap-2 p-3 md:p-2 rounded-lg border text-left transition-all ${formData.providerId === p.id
                                            ? 'bg-indigo-600/10 border-indigo-500 ring-1 ring-indigo-500/50 text-indigo-200'
                                            : 'bg-slate-900 border-slate-800 hover:bg-slate-800 text-slate-400'
                                            }`}
                                    >
                                        <div className={`w-2 h-2 md:w-1.5 md:h-1.5 rounded-full ${formData.providerId === p.id ? 'bg-indigo-500' : 'bg-slate-600'}`} />
                                        <span className="text-sm md:text-xs font-medium">{p.name}</span>
                                    </button>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Connection Details Box */}
                    <div className="bg-slate-900/30 p-4 rounded-xl border border-slate-800/50 space-y-4 shrink-0">
                        <div className="flex items-center justify-between">
                            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                                <Key size={12} className="text-indigo-400" /> Connection Details
                            </h4>
                            <div className="flex bg-slate-800/80 p-1 md:p-0.5 rounded-lg border border-slate-700/50">
                                <button
                                    onClick={() => setFormData({ ...formData, isProxy: false })}
                                    className={`px-4 py-2 md:px-3 md:py-1 text-xs md:text-[10px] font-bold rounded-md transition-all ${!formData.isProxy ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-300'}`}
                                >Standard</button>
                                <button
                                    onClick={() => setFormData({ ...formData, isProxy: true })}
                                    className={`px-4 py-2 md:px-3 md:py-1 text-xs md:text-[10px] font-bold rounded-md transition-all ${formData.isProxy ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-300'}`}
                                >Custom / Proxy</button>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium text-slate-500">API Endpoint</label>
                                {formData.isProxy ? (
                                    <input
                                        type="text"
                                        value={formData.baseUrl}
                                        onChange={e => setFormData({ ...formData, baseUrl: e.target.value })}
                                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs focus:border-indigo-500 outline-none text-slate-200 font-mono"
                                        placeholder="https://api.custom.com/v1"
                                    />
                                ) : (
                                    <div className="w-full bg-slate-900/50 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-500 font-mono select-none cursor-not-allowed truncate">
                                        {formData.baseUrl || 'Default'}
                                    </div>
                                )}
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-xs font-medium text-slate-500">API Key</label>
                                <div className="relative">
                                    <input
                                        type="password"
                                        value={formData.apiKey}
                                        onChange={e => setFormData({ ...formData, apiKey: e.target.value })}
                                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs focus:border-indigo-500 outline-none text-slate-200 pr-8 font-mono"
                                        placeholder="sk-..."
                                        autoComplete="off"
                                    />
                                    <Shield size={12} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600" />
                                </div>
                            </div>
                        </div>

                        <div className="flex justify-end">
                            <button
                                type="button"
                                onClick={handleVerify}
                                disabled={isVerifying || !formData.apiKey}
                                className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-colors border border-slate-700 shadow-sm"
                            >
                                <RefreshCw size={12} className={isVerifying ? 'animate-spin' : ''} />
                                {isVerifying ? 'Verifying...' : 'Verify Connection'}
                            </button>
                        </div>
                    </div>

                    {/* Models List (Verification Result) */}
                    {(verifiedModels.length > 0 || verifyError) && (
                        <div className="animate-[fadeIn_0.3s_ease-out] flex flex-col">
                            {verifyError ? (
                                <div className="p-3 bg-red-900/20 border border-red-900/50 rounded-xl text-red-300 text-xs flex items-start gap-3 shrink-0">
                                    <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                                    <div>
                                        <div className="font-bold mb-0.5">Verification Failed</div>
                                        <div className="opacity-80">{verifyError}</div>
                                    </div>
                                </div>
                            ) : (
                                <div className="bg-slate-900/30 rounded-xl border border-slate-800 flex flex-col mt-2">
                                    <div className="p-2 bg-slate-900/50 border-b border-slate-800 flex items-center justify-between shrink-0">
                                        <div className="flex items-center gap-2 text-green-400 px-1">
                                            <CheckCircle2 size={14} />
                                            <span className="text-xs font-medium">Verified</span>
                                        </div>
                                        <div className="flex items-center gap-2 md:gap-1.5 flex-wrap">
                                            <button
                                                onClick={() => setFormData(prev => prev ? ({ ...prev, hiddenModels: [] }) : null)}
                                                className="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 md:px-2 md:py-0.5 rounded text-slate-300 transition-colors border border-slate-700"
                                            >
                                                Select All
                                            </button>
                                            <button
                                                onClick={() => setFormData(prev => prev ? ({ ...prev, hiddenModels: verifiedModels.map(m => m.id) }) : null)}
                                                className="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 md:px-2 md:py-0.5 rounded text-slate-300 transition-colors border border-slate-700"
                                            >
                                                Select None
                                            </button>
                                            <span className="text-xs text-slate-500 ml-1 border-l border-slate-700 pl-2">{verifiedModels.length} Models</span>
                                        </div>
                                    </div>

                                    <div className="bg-slate-950/30 p-2 text-xs text-slate-500 border-b border-slate-800/50 shrink-0">
                                        Check models to include in the dropdown.
                                    </div>

                                    <div className="w-full p-3 md:p-2">
                                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 md:gap-1 w-full">
                                            {verifiedModels.map(model => {
                                                const isHidden = formData.hiddenModels.includes(model.id);
                                                return (
                                                    <div
                                                        key={model.id}
                                                        onClick={() => toggleEditorModelVisibility(model.id)}
                                                        className={`flex items-center gap-2 p-2 md:p-1.5 rounded-md cursor-pointer transition-colors border ${!isHidden ? 'bg-slate-800/60 border-slate-700/50 hover:bg-slate-800' : 'opacity-60 border-transparent hover:bg-slate-800/20'}`}
                                                    >
                                                        <div
                                                            className={`w-3.5 h-3.5 rounded-[3px] border flex items-center justify-center transition-colors shrink-0 ${!isHidden ? 'bg-indigo-600 border-indigo-600 text-white' : 'border-slate-600 bg-transparent'}`}
                                                        >
                                                            {!isHidden && <Check size={10} />}
                                                        </div>
                                                        <div className="min-w-0 flex-1 overflow-hidden">
                                                            <div className={`text-xs md:text-[11px] font-medium truncate leading-tight ${!isHidden ? 'text-slate-200' : 'text-slate-500'}`}>
                                                                {model.id}
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
                                                                    <div className="text-[10px] text-slate-500 truncate leading-tight mt-0.5 opacity-80">
                                                                        {model.description}
                                                                    </div>
                                                                );
                                                            })()}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Ollama Model Manager - 仅当 providerId 为 ollama 时显示 */}
                    {formData.providerId === 'ollama' && (
                        <div className="animate-[fadeIn_0.3s_ease-out] mt-2">
                            <OllamaModelManager
                                baseUrl={formData.baseUrl || 'http://localhost:11434'}
                                apiKey={formData.apiKey}
                                onModelSelect={(modelId) => {
                                    // 可选：选择模型时的回调
                                }}
                                onModelsChanged={() => {
                                    // 模型下载/删除后刷新验证列表
                                    handleVerify();
                                }}
                            />
                        </div>
                    )}

                </div>
            </div>

            {/* Footer Portal */}
            {footerNode && createPortal(
                <>
                    <button
                        onClick={onClose}
                        className="px-4 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors text-xs font-medium flex items-center gap-1"
                    >
                        <X size={16} /> Close
                    </button>
                    <button
                        onClick={handleSaveInternal}
                        className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20 transition-all text-sm font-medium flex items-center gap-2"
                    >
                        <Save size={14} /> Save
                    </button>
                </>,
                footerNode
            )}
        </>
    );
};
