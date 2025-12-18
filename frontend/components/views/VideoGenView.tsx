
import React, { useState, useRef, useEffect } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../../types';
import { Video as VideoIcon, Clock, AlertCircle, User, Bot, Download, Maximize2, Film, Play, History, X } from 'lucide-react';
import InputArea from '../chat/InputArea';
import { GenViewLayout } from '../common/GenViewLayout';

interface VideoGenViewProps {
    messages: Message[];
    setAppMode: (mode: AppMode) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    initialPrompt?: string;
}

export const VideoGenView: React.FC<VideoGenViewProps> = ({
    messages,
    setAppMode,
    loadingState,
    onSend,
    onStop,
    activeModelConfig,
    initialPrompt
}) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    // State for the currently displayed video in the main stage
    const [activeVideoUrl, setActiveVideoUrl] = useState<string | null>(null);

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

    const handleDownload = (url: string) => {
        const link = document.createElement('a');
        link.href = url;
        link.download = `gemini-video-${Date.now()}.mp4`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    // Mobile History Toggle
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

    return (
        <GenViewLayout
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            sidebarTitle="History"
            sidebarHeaderIcon={<Clock size={14} />}
            sidebarContent={
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
            }
            mainContent={
                /* Main Content (Stage) */
                <div className="flex-1 flex flex-col items-center justify-center p-8 overflow-hidden bg-[url('https://grainy-gradients.vercel.app/noise.svg')] bg-slate-950 relative">
                    {/* Stage Header */}
                    <div className="absolute top-4 left-4 z-10">
                        <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-lg">
                            <Film size={12} className="text-indigo-400" />
                            Video Workspace
                        </div>
                    </div>

                    {loadingState !== 'idle' ? (
                        <div className="flex flex-col items-center gap-6 p-8 rounded-3xl bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 shadow-2xl">
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
                        <div className="relative max-w-full max-h-full shadow-2xl group rounded-xl overflow-hidden bg-black ring-1 ring-white/10 flex items-center justify-center">
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
                        <div className="text-center text-slate-600 flex flex-col items-center gap-6">
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
            }
            bottomContent={
                <InputArea
                    onSend={onSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop}
                    currentModel={activeModelConfig}
                    mode="video-gen"
                    setMode={setAppMode}
                    initialPrompt={initialPrompt}
                />
            }
        />
    );
};
