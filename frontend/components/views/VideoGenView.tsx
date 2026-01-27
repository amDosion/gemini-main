
import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Video as VideoIcon, Clock, AlertCircle, User, Bot, Download, Maximize2, Film, SlidersHorizontal, RotateCcw, Paperclip, X, Image as ImageIcon, Send } from 'lucide-react';
import { GenViewLayout } from '../common/GenViewLayout';
import { useControlsState } from '../../hooks/useControlsState';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';

interface VideoGenViewProps {
    messages: Message[];
    setAppMode: (mode: AppMode) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    visibleModels?: ModelConfig[];
    allVisibleModels?: ModelConfig[];
    initialPrompt?: string;
    providerId?: string;
}

export const VideoGenView: React.FC<VideoGenViewProps> = ({
    messages,
    setAppMode,
    loadingState,
    onSend,
    onStop,
    activeModelConfig,
    visibleModels = [],
    allVisibleModels = [],  // 新增
    initialPrompt,
    providerId
}) => {
    const scrollRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // State for the currently displayed video in the main stage
    const [activeVideoUrl, setActiveVideoUrl] = useState<string | null>(null);

    // ✅ 参数面板状态
    const videoMode: AppMode = 'video-gen';
    const controls = useControlsState(videoMode, activeModelConfig);
    const [prompt, setPrompt] = useState(initialPrompt || '');
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);

    // 重置参数
    const resetParams = useCallback(() => {
        controls.setAspectRatio('16:9');
        controls.setNegativePrompt('');
        controls.setSeed(-1);
    }, [controls]);

    // Auto-scroll history to bottom when messages change
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    // Auto-select the latest generated video when loading finishes
    useEffect(() => {
        if (loadingState === 'idle') {
            // Find the latest successful model message with a video attachment
            const lastModelMsg = [...messages].reverse().find(m =>
                m.role === Role.MODEL &&
                m.attachments?.some(a => a.mimeType.startsWith('video/')) &&
                !m.isError
            );

            if (lastModelMsg) {
                const videoAtt = lastModelMsg.attachments?.find(a => a.mimeType.startsWith('video/'));
                if (videoAtt?.url) {
                    setActiveVideoUrl(videoAtt.url);
                }
            }
        }
    }, [loadingState, messages]);

    const handleDownload = useCallback((url: string) => {
        const link = document.createElement('a');
        link.href = url;
        link.download = `gemini-video-${Date.now()}.mp4`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }, []);

    // ✅ 使用参数面板发送生成请求
    const handleGenerate = useCallback(() => {
        if (!prompt.trim() || loadingState !== 'idle') return;
        
        const options: ChatOptions = {
            enableSearch: false,
            enableThinking: false,
            enableCodeExecution: false,
            imageAspectRatio: controls.aspectRatio,
            imageResolution: controls.resolution,
            negativePrompt: controls.negativePrompt || undefined,
            seed: controls.seed !== -1 ? controls.seed : undefined,
        };
        
        onSend(prompt, options, activeAttachments, videoMode);
        setPrompt('');
        setActiveAttachments([]);
    }, [prompt, loadingState, controls, onSend, activeAttachments, videoMode]);

    // ✅ 键盘快捷键
    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleGenerate();
        }
    }, [handleGenerate]);

    // Mobile History Toggle
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

    // ✅ 使用 useMemo 缓存 sidebarContent，防止不必要的重新渲染
    const sidebarContent = useMemo(() => (
        <div className="flex-1 p-4 space-y-6">
            {messages.map((msg) => (
                <div key={msg.id} className={`flex flex-col gap-2 ${msg.role === Role.USER ? 'items-end' : 'items-start'}`}>

                    {/* Role Label */}
                    <div className="flex items-center gap-2 text-xs text-slate-500 px-1">
                        {msg.role === Role.USER ? <User size={12} /> : <Bot size={12} />}
                        <span>{msg.role === Role.USER ? 'You' : (activeModelConfig?.name || 'AI')}</span>
                    </div>

                    {/* Message Bubble */}
                    <div className={`p-3 rounded-2xl max-w-full text-sm shadow-sm border ${msg.role === Role.USER
                        ? 'bg-slate-800 text-slate-200 border-slate-700/50 rounded-tr-sm'
                        : 'bg-slate-800/50 text-slate-300 border-slate-700/50 rounded-tl-sm'
                        }`}>
                        {msg.content && <p className="mb-2 whitespace-pre-wrap">{msg.content}</p>}

                        {/* Attachments (Images/Videos) */}
                        {msg.attachments?.map((att, idx) => {
                            const isVideo = att.mimeType.startsWith('video/');
                            const isImage = att.mimeType.startsWith('image/');
                            const isActive = activeVideoUrl === att.url;

                            return (
                                <div
                                    key={idx}
                                    onClick={() => att.url && isVideo && setActiveVideoUrl(att.url)}
                                    className={`relative group mt-2 rounded-lg overflow-hidden border transition-all ${isVideo ? 'cursor-pointer' : ''
                                        } ${isActive ? 'ring-2 ring-indigo-500 border-transparent' : 'border-slate-700 hover:border-slate-500'
                                        }`}
                                >
                                    {isImage ? (
                                        <img src={att.url} className="w-full max-h-48 object-contain bg-black/50" alt="input reference" />
                                    ) : isVideo ? (
                                        <div className="relative">
                                            <video
                                                src={att.url}
                                                className="w-full max-h-32 object-cover bg-black"
                                                muted
                                                onMouseOver={e => (e.target as HTMLVideoElement).play()}
                                                onMouseOut={e => (e.target as HTMLVideoElement).pause()}
                                            />
                                            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                                                <div className="bg-black/50 p-1.5 rounded-full backdrop-blur-sm">
                                                    <VideoIcon size={16} className="text-white" />
                                                </div>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="p-2 bg-slate-900 flex items-center gap-2 text-xs">
                                            <Film size={14} /> {att.name}
                                        </div>
                                    )}
                                </div>
                            );
                        })}

                        {/* Error State */}
                        {msg.isError && (
                            <div className="flex items-center gap-2 text-red-400 text-xs mt-2 p-2 bg-red-900/10 rounded">
                                <AlertCircle size={12} />
                                <span>Generation failed</span>
                            </div>
                        )}
                    </div>
                </div>
            ))}

            {/* Loading Indicator */}
            {loadingState !== 'idle' && (
                <div className="flex items-start gap-2 animate-pulse">
                    <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center">
                        <Bot size={16} className="text-slate-500" />
                    </div>
                    <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400 border border-slate-700/50">
                        Generating video frames... This may take a minute.
                    </div>
                </div>
            )}

            {messages.length === 0 && (
                <div className="text-center py-10 text-slate-600 text-xs italic">
                    No history yet. Start by describing a video!
                </div>
            )}
            {/* Dummy div for scroll ref */}
            <div ref={scrollRef} />
        </div>
    ), [messages, loadingState, activeModelConfig?.name, activeVideoUrl]);

    // ✅ 主区域：两栏布局（画布 + 参数面板）
    const mainContent = useMemo(() => (
        <div className="flex-1 flex flex-row h-full">
            {/* ========== 左侧：画布区域 ========== */}
            <div className="flex-1 flex flex-col items-center justify-center p-8 overflow-hidden bg-slate-950 relative">
                {/* 棋盘格背景 */}
                <div
                    className="absolute inset-0 opacity-20 pointer-events-none"
                    style={{
                        backgroundImage: `
                            linear-gradient(45deg, #334155 25%, transparent 25%), 
                            linear-gradient(-45deg, #334155 25%, transparent 25%), 
                            linear-gradient(45deg, transparent 75%, #334155 75%), 
                            linear-gradient(-45deg, transparent 75%, #334155 75%)
                        `,
                        backgroundSize: '20px 20px',
                        backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
                    }}
                />
                {/* Canvas Header */}
                <div className="absolute top-4 left-4 z-10 pointer-events-none">
                    <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-lg">
                        <Film size={12} className="text-indigo-400" />
                        Video Workspace
                    </div>
                </div>

                {loadingState !== 'idle' ? (
                    <div className="flex flex-col items-center gap-6 p-8 rounded-3xl bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 shadow-2xl relative z-10">
                        <div className="relative">
                            <div className="w-24 h-24 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"></div>
                            <div className="absolute inset-0 flex items-center justify-center text-sm font-mono text-indigo-400 font-bold tracking-widest">VEO</div>
                        </div>
                        <div className="text-center">
                            <p className="text-slate-200 font-medium text-lg">Creating your video...</p>
                            <p className="text-slate-500 text-xs mt-1">AI models take time to render frames.</p>
                        </div>
                    </div>
                ) : activeVideoUrl ? (
                    <div className="relative max-w-full max-h-full shadow-2xl group rounded-xl overflow-hidden bg-black ring-1 ring-white/10 flex items-center justify-center z-10">
                        <video
                            src={activeVideoUrl}
                            controls
                            autoPlay
                            loop
                            className="max-w-full max-h-[80vh] object-contain shadow-2xl"
                        />

                        {/* Overlay Actions */}
                        <div className="absolute bottom-0 inset-x-0 p-4 bg-gradient-to-t from-black/90 via-black/50 to-transparent translate-y-full group-hover:translate-y-0 transition-transform flex justify-end gap-2">
                            <button
                                onClick={() => window.open(activeVideoUrl, '_blank')}
                                className="p-2.5 bg-white/10 hover:bg-white/20 text-white rounded-xl backdrop-blur border border-white/10 transition-colors"
                                title="Open in new tab"
                            >
                                <Maximize2 size={20} />
                            </button>
                            <button
                                onClick={() => handleDownload(activeVideoUrl)}
                                className="p-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl shadow-lg transition-colors flex items-center gap-2"
                                title="Download"
                            >
                                <Download size={20} />
                                <span className="text-xs font-bold pr-1">Download</span>
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="text-center text-slate-600 flex flex-col items-center gap-6 relative z-10">
                        <div className="w-32 h-32 rounded-3xl bg-slate-900 border border-slate-800 flex items-center justify-center shadow-inner relative overflow-hidden group">
                            <div className="absolute inset-0 bg-gradient-to-tr from-indigo-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                            <VideoIcon size={64} className="opacity-20 group-hover:scale-110 transition-transform duration-500" />
                        </div>
                        <div>
                            <h3 className="text-2xl font-bold text-slate-500 mb-2">Video Generator</h3>
                            <p className="max-w-xs mx-auto text-sm opacity-60">
                                Describe a scene, or upload an image to animate using Google Veo.
                            </p>
                        </div>
                    </div>
                )}
            </div>

            {/* ========== 右侧：参数面板 ========== */}
            <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
                {/* 头部 */}
                <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal size={14} className="text-indigo-400" />
                        <span className="text-xs font-bold text-white">视频参数</span>
                    </div>
                    <button
                        onClick={resetParams}
                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                        title="重置为默认值"
                    >
                        <RotateCcw size={12} />
                    </button>
                </div>

                {/* 参数滚动区 */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
                    <ModeControlsCoordinator
                        mode={videoMode}
                        providerId={providerId || 'google'}
                        controls={controls}
                    />
                </div>

                {/* 底部固定区：附件预览 + 提示词 + 生成按钮 */}
                <div className="border-t border-slate-800 p-3 space-y-2 bg-slate-900/80">
                    {/* 附件预览区 */}
                    {activeAttachments.length > 0 && (
                        <div className="flex gap-2 flex-wrap">
                            {activeAttachments.map((att, idx) => (
                                <div key={idx} className="relative group">
                                    <img 
                                        src={att.url || att.tempUrl || ''} 
                                        className="w-12 h-12 rounded-lg object-cover border border-slate-700" 
                                        alt="参考图"
                                    />
                                    <button
                                        onClick={() => {
                                            setActiveAttachments(activeAttachments.filter((_, i) => i !== idx));
                                        }}
                                        className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                                    >
                                        <X size={12} className="text-white" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* 提示词输入 */}
                    <textarea
                        ref={textareaRef}
                        value={prompt}
                        onChange={(e) => {
                            setPrompt(e.target.value);
                            e.target.style.height = 'auto';
                            e.target.style.height = Math.min(e.target.scrollHeight, 150) + 'px';
                        }}
                        onKeyDown={handleKeyDown}
                        placeholder="描述你想生成的视频..."
                        className="w-full min-h-[40px] max-h-[150px] bg-slate-800/80 border border-slate-700 rounded-lg p-2.5 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 overflow-y-auto"
                    />

                    {/* 上传按钮 + 生成按钮 */}
                    <div className="flex gap-2 items-center">
                        {/* 上传按钮 */}
                        <label className="p-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 cursor-pointer transition-colors border border-indigo-500/50 flex-shrink-0 shadow-lg">
                            <input
                                type="file"
                                accept="image/*"
                                className="hidden"
                                onChange={(e) => {
                                    const file = e.target.files?.[0];
                                    if (file) {
                                        const url = URL.createObjectURL(file);
                                        const newAtt: Attachment = {
                                            id: `att-${Date.now()}`,
                                            name: file.name,
                                            mimeType: file.type,
                                            url: url,
                                            tempUrl: url,
                                            file: file,
                                        };
                                        setActiveAttachments([...activeAttachments, newAtt]);
                                    }
                                    e.target.value = '';
                                }}
                            />
                            <ImageIcon size={18} className="text-white" />
                        </label>

                        {/* 生成按钮 */}
                        <button
                            onClick={handleGenerate}
                            disabled={!prompt.trim() || loadingState !== 'idle'}
                            className="flex-1 py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loadingState !== 'idle' ? (
                                <>
                                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    生成中...
                                </>
                            ) : (
                                <>
                                    <Send size={18} />
                                    生成视频
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    ), [loadingState, activeVideoUrl, handleDownload, controls, providerId, prompt, handleKeyDown, handleGenerate, resetParams, activeAttachments, videoMode]);

    return (
        <GenViewLayout
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            sidebarTitle="History"
            sidebarHeaderIcon={<Clock size={14} />}
            sidebar={sidebarContent}
            main={mainContent}
        />
    );
};
