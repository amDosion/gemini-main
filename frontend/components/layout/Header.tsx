
import React, { useMemo, useState } from 'react';
import { Menu, MonitorUp, ChevronDown, Check, Loader2, Settings, Globe, Brain, Image as ImageIcon, Zap, BrainCircuit, Video, Mic, Server, Cpu, Sparkles, PlusCircle, FileText } from 'lucide-react';
import { ModelConfig, AppMode } from '../../types/types';
import { ConfigProfile } from '../../services/db';

interface HeaderProps {
    isSidebarOpen: boolean;
    setIsSidebarOpen: (v: boolean) => void;
    isRightSidebarOpen: boolean;
    setIsRightSidebarOpen: (v: boolean) => void;
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
}

const getModelIcon = (model: ModelConfig) => {
    const id = model.id.toLowerCase();
    // 视频生成模型
    if (id.includes('veo') || id.includes('sora') || id.includes('luma')) return Video;
    // 音频生成模型
    if (id.includes('tts') || id.includes('audio') || id.includes('speech')) return Mic;
    // 文生图模型：统一使用 Zap 图标
    if (id.includes('-t2i') || id.includes('z-image') || id.includes('wanx') || id.includes('dall') || id.includes('flux') || id.includes('midjourney') || id.includes('imagen')) return Zap;
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

export const Header: React.FC<HeaderProps> = ({
    isSidebarOpen,
    setIsSidebarOpen,
    isRightSidebarOpen,
    setIsRightSidebarOpen,
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
    onActivateProfile
}) => {
    const ActiveIcon = activeModelConfig ? getModelIcon(activeModelConfig) : Loader2;
    const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
    const [isActivating, setIsActivating] = useState(false);

    // Get Current Profile
    const activeProfile = profiles.find(p => p.id === activeProfileId);

    // Filter models based on the current App Mode
    const filteredModels = useMemo(() => {
        return visibleModels.filter(m => {
            const id = m.id.toLowerCase();
            const caps = m.capabilities;

            switch (appMode) {
                case 'video-gen':
                    return id.includes('veo') || id.includes('sora') || id.includes('video') || id.includes('luma');
                case 'audio-gen':
                    return id.includes('tts') || id.includes('audio') || id.includes('speech');
                case 'image-gen':
                    // 文生图模式：排除 edit 模型（如 qwen-image-edit-plus），它们需要输入图片
                    // 只包含纯文生图模型：-t2i 系列、z-image 系列、dall-e、flux、midjourney、wanx、imagen
                    // 注意：wan2.6-image 不在此列表中，因为它的纯文生图模式需要流式输出，应放在 image-edit 模式
                    if (id.includes('edit')) return false; // 排除所有编辑模型
                    return (id.includes('dall') || id.includes('wanx') || id.includes('flux') || id.includes('midjourney') || id.includes('-t2i') || id.includes('z-image') || id.includes('imagen'));
                case 'image-edit':
                case 'image-outpainting':
                    return caps.vision && !id.includes('veo');
                case 'virtual-try-on':
                    // 虚拟试衣需要视觉能力的模型,排除视频生成专用模型
                    return caps.vision && !id.includes('veo');
                case 'deep-research':
                    // 深度研究需要搜索或推理能力
                    return caps.search || caps.reasoning;
                case 'pdf-extract':
                    // PDF extraction can use any model that supports function calling / text generation
                    // We exclude specialized media generation models
                    return !id.includes('veo') && !id.includes('tts') && !id.includes('wanx') && !id.includes('imagen') && !id.includes('-t2i') && !id.includes('z-image');
                case 'chat':
                default:
                    // Standard chat: Exclude specialized video/audio generators unless they are multimodal
                    return !id.includes('veo') && !id.includes('tts') && !id.includes('wanx') && !id.includes('-t2i') && !id.includes('z-image');
            }
        });
    }, [visibleModels, appMode]);

    const renderCapabilities = (model: ModelConfig) => {
        const id = model.id.toLowerCase();
        // 文生图模型不显示 vision 能力图标（它们是生成图片，不是理解图片）
        const isImageGenModel = id.includes('-t2i') || id.includes('z-image') || id.includes('wanx') || id.includes('dall') || id.includes('flux') || id.includes('midjourney') || id.includes('imagen');
        
        return (
            <div className="flex items-center gap-1 ml-2">
                {model.capabilities.search && <Globe size={12} className="text-blue-400" />}
                {model.capabilities.reasoning && <Brain size={12} className="text-purple-400" />}
                {model.capabilities.vision && !isImageGenModel && <ImageIcon size={12} className="text-emerald-400" />}
            </div>
        );
    };

    return (
        <header className="h-14 flex items-center justify-between px-4 border-b border-slate-800 bg-slate-900/50 backdrop-blur-md z-50 shrink-0 sticky top-0">
            <div className="flex items-center gap-2">
                <button
                    type="button"
                    onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                    className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
                >
                    <Menu size={20} />
                </button>

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
                                                    console.error('Failed to activate profile:', error);
                                                    alert('切换提供商失败，请重试');
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
                                {activeModelConfig?.name || (activeProfile ? 'Select Model' : 'No Config')}
                            </span>
                            {!isLoadingModels && activeModelConfig && renderCapabilities(activeModelConfig)}
                        </div>

                        <ChevronDown size={14} className={`text-slate-400 transition-transform duration-200 ml-1 ${isModelMenuOpen ? 'rotate-180' : ''}`} />
                    </button>

                    {isModelMenuOpen && (
                        <>
                            <div className="fixed inset-0 z-40" onClick={() => setIsModelMenuOpen(false)} />
                            <div className="absolute top-full left-0 mt-2 w-96 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl z-50 overflow-hidden ring-1 ring-black/50">
                                <div className="p-2 flex flex-col gap-1 max-h-[60vh] overflow-y-auto custom-scrollbar">

                                    <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider flex justify-between bg-slate-950/50 sticky top-0 z-10 backdrop-blur-sm">
                                        <span>{appMode.replace('-', ' ')} Models</span>
                                        <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">{filteredModels.length}</span>
                                    </div>

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
                                                            <span className={`text-sm font-medium truncate ${isSelected ? 'text-white' : 'text-slate-300'}`} title={model.name}>
                                                                {model.name}
                                                            </span>
                                                            {renderCapabilities(model)}
                                                        </div>
                                                        {isSelected && <Check size={14} className="text-indigo-400 shrink-0 ml-2" />}
                                                    </div>
                                                    <div className="text-xs text-slate-500 leading-tight truncate" title={model.id}>
                                                        {model.id}
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
                                        Manage Active Models
                                    </button>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>
            <div className="flex items-center gap-2">
                <button
                    type="button"
                    onClick={() => window.open(window.location.href, '_blank')}
                    className="hidden sm:block p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
                    title="Open in new tab"
                >
                    <MonitorUp size={20} />
                </button>
            </div>
        </header>
    );
};
