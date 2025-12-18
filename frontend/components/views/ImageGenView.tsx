
import React, { useMemo, useState, useEffect } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../../types';
import { Image as ImageIcon, Maximize2, Crop, Download, Layers, Clock, AlertCircle, Grid, X, History, Expand } from 'lucide-react';
import InputArea from '../chat/InputArea';
import { GenViewLayout } from '../common/GenViewLayout';

interface ImageGenViewProps {
    messages: Message[];
    setAppMode: (mode: AppMode) => void;
    onImageClick: (url: string) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    initialPrompt?: string;
    onEditImage?: (url: string) => void;
    onExpandImage?: (url: string) => void; // Added prop
    providerId?: string;
}

export const ImageGenView: React.FC<ImageGenViewProps> = ({
    messages,
    setAppMode,
    onImageClick,
    loadingState,
    onSend,
    onStop,
    activeModelConfig,
    initialPrompt,
    onEditImage,
    onExpandImage,
    providerId
}) => {
    const [contextMenu, setContextMenu] = useState<{ x: number, y: number, url: string } | null>(null);

    // Track selected MESSAGE ID (Batch)
    const [selectedMsgId, setSelectedMsgId] = useState<string | null>(null);
    // Mobile History Toggle
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

    // Auto-switch to latest generation when new one starts
    useEffect(() => {
        if (loadingState === 'loading') {
            setSelectedMsgId(null);
            // Close mobile history if a new generation starts
            setIsMobileHistoryOpen(false);
        }
    }, [loadingState]);

    // 1. Group History by Message (Batch)
    const historyBatches = useMemo(() => {
        return messages
            .filter(m => m.role === Role.MODEL && ((m.attachments && m.attachments.length > 0) || m.isError))
            .reverse();
    }, [messages]);

    // 2. Determine Active Batch to Display
    const activeBatchMessage = useMemo(() => {
        if (selectedMsgId) {
            return historyBatches.find(m => m.id === selectedMsgId);
        }
        return historyBatches[0];
    }, [selectedMsgId, historyBatches]);

    const displayImages = (activeBatchMessage?.attachments || []).filter(att => att.url && att.url.length > 0);
    const isBatchError = activeBatchMessage?.isError;

    const handleContextMenu = (e: React.MouseEvent, url: string) => {
        e.preventDefault();
        setContextMenu({ x: e.clientX, y: e.clientY, url });
    };

    const handleDownload = (url: string) => {
        const link = document.createElement('a');
        link.href = url;
        link.download = `gemini-gen-${Date.now()}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    return (
        <>
            <GenViewLayout
                isMobileHistoryOpen={isMobileHistoryOpen}
                setIsMobileHistoryOpen={setIsMobileHistoryOpen}
                sidebarTitle="History"
                sidebarHeaderIcon={<Clock size={14} />}
                sidebarExtraHeader={
                    <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-500">{historyBatches.length}</span>
                }
                sidebarContent={
                    <div className="p-3 space-y-3">
                        {/* Existing History Batch Logic */}
                        {historyBatches.map((msg, i) => {
                            const firstImage = msg.attachments?.[0]?.url;
                            const count = msg.attachments?.length || 0;
                            const isSelected = activeBatchMessage?.id === msg.id;

                            return (
                                <div
                                    key={msg.id}
                                    className={`group relative rounded-xl overflow-hidden border cursor-pointer transition-all flex flex-col gap-2 bg-slate-800/40 p-2 ${isSelected ? 'ring-1 ring-emerald-500 border-transparent bg-slate-800' : 'border-slate-700/50 hover:border-slate-600 hover:bg-slate-800'
                                        }`}
                                    onClick={() => {
                                        setSelectedMsgId(msg.id);
                                        if (window.innerWidth < 768) setIsMobileHistoryOpen(false);
                                    }}
                                >
                                    <div className="aspect-square w-full rounded-lg overflow-hidden bg-slate-900 relative">
                                        {msg.isError ? (
                                            <div className="w-full h-full flex items-center justify-center text-red-400 bg-red-900/10">
                                                <AlertCircle size={24} />
                                            </div>
                                        ) : (
                                            <>
                                                <img src={firstImage} className="w-full h-full object-cover transition-transform group-hover:scale-105" loading="lazy" />
                                                {count > 1 && (
                                                    <div className="absolute top-1 right-1 bg-black/60 backdrop-blur-sm text-white text-[10px] px-1.5 py-0.5 rounded-md flex items-center gap-1 font-medium border border-white/10">
                                                        <Layers size={10} /> {count}
                                                    </div>
                                                )}
                                            </>
                                        )}
                                    </div>
                                    <div className="px-1">
                                        <p className="text-[11px] text-slate-300 line-clamp-2 leading-relaxed font-medium">
                                            {msg.content || "Generated Image Batch"}
                                        </p>
                                        <p className="text-[10px] text-slate-600 mt-1">
                                            {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </p>
                                    </div>
                                </div>
                            );
                        })}

                        {historyBatches.length === 0 && (
                            <div className="text-center py-10 text-slate-600 text-xs italic">
                                No generation history.
                            </div>
                        )}
                    </div>
                }
                mainContent={
                    /* Main Content (Canvas) */
                    <div className="flex-1 w-full h-full overflow-y-auto p-6 relative custom-scrollbar bg-[url('https://grainy-gradients.vercel.app/noise.svg')]">
                        <div className="min-h-full flex flex-col items-center justify-center">

                            {loadingState !== 'idle' ? (
                                <div className="flex flex-col items-center gap-6 p-8 rounded-3xl bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 shadow-2xl">
                                    <div className="relative">
                                        <div className="w-20 h-20 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin"></div>
                                        <div className="absolute inset-0 flex items-center justify-center text-xs font-mono text-emerald-400 font-bold">GEN</div>
                                    </div>
                                    <div className="text-center space-y-2">
                                        <p className="text-slate-200 font-medium text-lg">Dreaming up your image...</p>
                                        <p className="text-slate-500 text-sm">This may take a few seconds</p>
                                    </div>
                                </div>
                            ) : isBatchError ? (
                                <div className="flex flex-col items-center gap-4 text-center p-8 bg-slate-900/50 rounded-2xl border border-red-900/30">
                                    <AlertCircle size={48} className="text-red-500 opacity-80" />
                                    <div>
                                        <h3 className="text-lg font-bold text-slate-200">Generation Failed</h3>
                                        <p className="text-sm text-red-400 mt-2 max-w-md">{activeBatchMessage?.content || "An unknown error occurred."}</p>
                                    </div>
                                </div>
                            ) : displayImages.length > 0 ? (
                                <div className={`w-full max-w-6xl grid gap-6 transition-all duration-300 ${displayImages.length === 1 ? 'grid-cols-1 place-items-center' :
                                    displayImages.length === 2 ? 'grid-cols-1 md:grid-cols-2 place-items-start' :
                                        displayImages.length === 3 ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-2 place-items-start' :
                                            'grid-cols-1 md:grid-cols-2 lg:grid-cols-2 place-items-start' /* 2x2 Layout for 4 images */
                                    }`}>
                                    {displayImages.map((att, idx) => (
                                        <div
                                            key={idx}
                                            className={`relative rounded-2xl overflow-hidden shadow-2xl group border border-slate-800/50 bg-slate-900 animate-[fadeIn_0.5s_ease-out] mx-auto ${displayImages.length === 1 ? 'max-w-full' : 'w-full'
                                                }`}
                                            style={{ animationDelay: `${idx * 100}ms` }}
                                            onContextMenu={(e) => handleContextMenu(e, att.url!)}
                                        >
                                            <img
                                                src={att.url}
                                                className={`block ${displayImages.length === 1
                                                    ? 'max-h-[80vh] w-auto object-contain'
                                                    : 'w-full h-auto object-cover'
                                                    }`}
                                                onClick={() => onImageClick(att.url!)}
                                            />

                                            {/* Hover Overlay */}
                                            <div className="absolute top-4 right-4 flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-all translate-x-4 group-hover:translate-x-0">
                                                {onEditImage && (
                                                    <button onClick={() => onEditImage(att.url!)} className="p-2.5 bg-pink-600 hover:bg-pink-500 text-white rounded-xl shadow-lg" title="Edit this image">
                                                        <Crop size={18} />
                                                    </button>
                                                )}
                                                {onExpandImage && (
                                                    <button onClick={() => onExpandImage(att.url!)} className="p-2.5 bg-orange-600 hover:bg-orange-500 text-white rounded-xl shadow-lg" title="Expand (Outpaint)">
                                                        <Expand size={18} />
                                                    </button>
                                                )}
                                                <button onClick={() => onImageClick(att.url!)} className="p-2.5 bg-black/60 hover:bg-black/80 text-white rounded-xl backdrop-blur border border-white/10 shadow-lg" title="Fullscreen">
                                                    <Maximize2 size={18} />
                                                </button>
                                                <button onClick={() => handleDownload(att.url!)} className="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl shadow-lg" title="Download">
                                                    <Download size={18} />
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="flex flex-col items-center text-slate-600 gap-6">
                                    <div className="w-24 h-24 rounded-3xl bg-slate-900 border border-slate-800 flex items-center justify-center shadow-inner">
                                        <ImageIcon size={48} className="opacity-20" />
                                    </div>
                                    <div className="text-center">
                                        <h3 className="text-xl font-bold text-slate-500 mb-2">Image Generator</h3>
                                        <p className="max-w-xs mx-auto text-sm opacity-60">Enter a prompt below to start generating high-quality AI images.</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                }
                mainAreaOverlay={
                    /* Batch Indicator Overlay */
                    displayImages.length > 1 && (
                        <div className="absolute top-4 left-16 md:left-4 z-10 animate-[fadeIn_0.3s_ease-out] pointer-events-none">
                            <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-xl">
                                <Grid size={14} className="text-emerald-400" />
                                Batch Result ({displayImages.length})
                            </div>
                        </div>
                    )
                }
                bottomContent={
                    /* Input Area (Centered by Layout) */
                    <InputArea
                        onSend={onSend}
                        isLoading={loadingState !== 'idle'}
                        onStop={onStop}
                        currentModel={activeModelConfig}
                        mode="image-gen"
                        setMode={setAppMode}
                        initialPrompt={initialPrompt}
                        providerId={providerId}
                    />
                }
            />

            {/* Context Menu */}
            {contextMenu && (
                <div
                    className="fixed z-[100] bg-slate-900 border border-slate-700 rounded-xl shadow-2xl py-1 w-48 animate-[fadeIn_0.1s_ease-out] overflow-hidden"
                    style={{ top: contextMenu.y, left: contextMenu.x }}
                    onClick={(e) => e.stopPropagation()}
                >
                    <button
                        onClick={() => {
                            onEditImage?.(contextMenu.url);
                            setContextMenu(null);
                        }}
                        className="w-full text-left px-4 py-2.5 text-sm text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition-colors"
                    >
                        <Crop size={14} className="text-pink-400" /> Edit Image
                    </button>
                    <button
                        onClick={() => {
                            onExpandImage?.(contextMenu.url);
                            setContextMenu(null);
                        }}
                        className="w-full text-left px-4 py-2.5 text-sm text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition-colors"
                    >
                        <Expand size={14} className="text-orange-400" /> Expand Image
                    </button>
                    <button
                        onClick={() => {
                            handleDownload(contextMenu.url);
                            setContextMenu(null);
                        }}
                        className="w-full text-left px-4 py-2.5 text-sm text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition-colors border-t border-slate-800"
                    >
                        <Download size={14} className="text-emerald-400" /> Download
                    </button>
                </div>
            )}
        </>
    );
};
