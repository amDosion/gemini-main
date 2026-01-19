
import React, { useState, useEffect, useMemo } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
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
    visibleModels?: ModelConfig[];  // 新增
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
    visibleModels = [],
    initialPrompt,
    onEditImage,
    onExpandImage,
    providerId
}) => {
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

    const displayImages = useMemo(() => {
        return (activeBatchMessage?.attachments || []).filter(att => att.url && att.url.length > 0);
    }, [activeBatchMessage?.attachments]);
    
    // ✅ 详细日志：记录显示图片时使用的URL类型
    useEffect(() => {
        if (displayImages.length > 0) {
            console.log('[ImageGenView] ========== 显示图片URL类型分析 ==========');
            displayImages.forEach((att, idx) => {
                const urlType = att.url?.startsWith('data:') ? 'Base64 Data URL (AI原始返回)' :
                               att.url?.startsWith('blob:') ? 'Blob URL (处理后的本地URL)' :
                               att.url?.startsWith('http://') || att.url?.startsWith('https://') ? 
                                 (att.uploadStatus === 'completed' ? '云存储URL (已上传完成)' : 'HTTP临时URL (AI原始返回)') :
                               '未知类型';
                
                const hasCloudUrl = att.uploadStatus === 'completed' && 
                                   (att.url?.startsWith('http://') || att.url?.startsWith('https://'));
                
                console.log(`[ImageGenView] 图片 ${idx + 1}/${displayImages.length}:`, {
                    attachmentId: att.id?.substring(0, 8) + '...',
                    displayUrlType: urlType,
                    displayUrl: att.url ? (att.url.length > 80 ? att.url.substring(0, 80) + '...' : att.url) : 'N/A',
                    uploadStatus: att.uploadStatus,
                    hasCloudUrl: hasCloudUrl,
                    cloudUrl: hasCloudUrl ? (att.url!.length > 80 ? att.url!.substring(0, 80) + '...' : att.url!) : 'N/A',
                    tempUrl: att.tempUrl ? (att.tempUrl.length > 80 ? att.tempUrl.substring(0, 80) + '...' : att.tempUrl) : 'N/A',
                    source: hasCloudUrl ? '云存储URL (处理后的永久URL)' : 
                           urlType.includes('Base64') ? 'AI返回的原始Base64地址' :
                           urlType.includes('Blob') ? '处理后的Blob URL (从HTTP临时URL转换)' :
                           urlType.includes('HTTP临时URL') ? 'AI返回的HTTP临时地址' : '未知来源',
                    note: '前端<img>标签将使用此URL进行显示'
                });
            });
            console.log('[ImageGenView] ============================================');
        }
    }, [displayImages]);
    const isBatchError = activeBatchMessage?.isError;

    // Sidebar header icon and extra header
    const sidebarHeaderIcon = <Clock size={14} />;
    
    // ✅ 使用 useMemo 缓存 sidebarExtraHeader，确保在 historyBatches 变化时更新
    const sidebarExtraHeader = useMemo(() => (
        <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-500">
            {historyBatches.length}
        </span>
    ), [historyBatches.length]);

    // ✅ 使用 useMemo 缓存 sidebarContent，确保在 historyBatches 或 selectedMsgId 变化时更新
    const sidebarContent = useMemo(() => (
        <div className="p-3 space-y-3">
            {historyBatches.map((msg, i) => {
                const firstImage = msg.attachments?.[0]?.url;
                const count = msg.attachments?.length || 0;
                const isSelected = activeBatchMessage?.id === msg.id;

                return (
                    <div
                        key={msg.id}
                        className={`group relative rounded-xl overflow-hidden border cursor-pointer transition-all flex flex-col gap-2 bg-slate-800/40 p-2 ${
                            isSelected ? 'ring-1 ring-emerald-500 border-transparent bg-slate-800' : 'border-slate-700/50 hover:border-slate-600 hover:bg-slate-800'
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
                            ) : firstImage ? (
                                <>
                                    <img src={firstImage} className="w-full h-full object-cover transition-transform group-hover:scale-105" loading="lazy" alt="Generated image" />
                                    {count > 1 && (
                                        <div className="absolute top-1 right-1 bg-black/60 backdrop-blur-sm text-white text-[10px] px-1.5 py-0.5 rounded-md flex items-center gap-1 font-medium border border-white/10">
                                            <Layers size={10} /> {count}
                                        </div>
                                    )}
                                </>
                            ) : (
                                <div className="w-full h-full flex items-center justify-center text-slate-600">
                                    <ImageIcon size={24} className="opacity-50" />
                                </div>
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
    ), [historyBatches, activeBatchMessage?.id]);

    const handleDownload = async (url: string) => {
        // 判断 URL 类型
        const isBase64 = url.startsWith('data:');
        const isBlob = url.startsWith('blob:');
        const isCloudUrl = url.startsWith('http://') || url.startsWith('https://');
        
        if (isBase64 || isBlob) {
            // 同源图片：直接 fetch 下载
            const response = await fetch(url);
            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = objectUrl;
            a.download = `gemini-gen-${Date.now()}.png`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(objectUrl);
        } else if (isCloudUrl) {
            // 跨域云存储 URL：通过后端代理下载
            const proxyUrl = `/api/storage/download?url=${encodeURIComponent(url)}`;
            const a = document.createElement('a');
            a.href = proxyUrl;
            a.download = `gemini-gen-${Date.now()}.png`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    };

    // Main content area
    const mainContent = (
        <div className="flex-1 w-full h-full overflow-y-auto relative custom-scrollbar">
            <div className="min-h-full flex flex-col items-center justify-center p-6 relative z-10">
                {/* 棋盘格背景 - 使用伪元素层，不影响内容透明度 */}
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
                    <div className={`w-full max-w-6xl grid gap-6 transition-all duration-300 ${
                        displayImages.length === 1 ? 'grid-cols-1 place-items-center' :
                        displayImages.length === 2 ? 'grid-cols-1 md:grid-cols-2 place-items-start' :
                        displayImages.length === 3 ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-2 place-items-start' :
                        'grid-cols-1 md:grid-cols-2 lg:grid-cols-2 place-items-start'
                    }`}>
                        {displayImages.map((att, idx) => (
                            <div
                                key={idx}
                                className={`relative rounded-2xl overflow-hidden shadow-2xl group border border-slate-800/50 bg-slate-900 animate-[fadeIn_0.5s_ease-out] mx-auto ${
                                    displayImages.length === 1 ? 'max-w-full' : 'w-full'
                                }`}
                                style={{ animationDelay: `${idx * 100}ms` }}
                            >
                                {att.url ? (
                                    <img
                                        src={att.url}
                                        className={`block ${
                                            displayImages.length === 1
                                                ? 'max-h-[80vh] w-auto object-contain'
                                                : 'w-full h-auto object-cover'
                                        }`}
                                        onClick={() => onImageClick(att.url!)}
                                        alt="Generated image"
                                    />
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center text-slate-600 bg-slate-900">
                                        <ImageIcon size={48} className="opacity-50" />
                                    </div>
                                )}
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
                                    <button 
                                        onClick={async () => {
                                            const isBase64 = att.url!.startsWith('data:');
                                            const isBlob = att.url!.startsWith('blob:');
                                            const isCloudUrl = att.url!.startsWith('http://') || att.url!.startsWith('https://');
                                            
                                            if (isBase64 || isBlob) {
                                                onImageClick(att.url!);
                                            } else if (isCloudUrl) {
                                                try {
                                                    const proxyUrl = `/api/storage/download?url=${encodeURIComponent(att.url!)}`;
                                                    const response = await fetch(proxyUrl);
                                                    const blob = await response.blob();
                                                    const blobUrl = URL.createObjectURL(blob);
                                                    onImageClick(blobUrl);
                                                } catch (error) {
                                                    console.error('Failed to load image for fullscreen:', error);
                                                    onImageClick(att.url!);
                                                }
                                            } else {
                                                onImageClick(att.url!);
                                            }
                                        }} 
                                        className="p-2.5 bg-black/60 hover:bg-black/80 text-white rounded-xl backdrop-blur border border-white/10 shadow-lg" 
                                        title="Fullscreen"
                                    >
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
    );

    // Main area overlay
    const mainAreaOverlay = (
        displayImages.length > 1 && (
            <div className="absolute top-4 left-16 md:left-4 z-10 animate-[fadeIn_0.3s_ease-out] pointer-events-none">
                <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-xl">
                    <Grid size={14} className="text-emerald-400" />
                    Batch Result ({displayImages.length})
                </div>
            </div>
        )
    );

    // Bottom input area
    const bottomContent = (
        <InputArea
            onSend={onSend}
            isLoading={loadingState !== 'idle'}
            onStop={onStop}
            currentModel={activeModelConfig}
            visibleModels={visibleModels}
            mode="image-gen"
            setMode={setAppMode}
            initialPrompt={initialPrompt}
            providerId={providerId}
        />
    );

    return (
        <GenViewLayout
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            sidebarTitle="History"
            sidebarHeaderIcon={sidebarHeaderIcon}
            sidebarExtraHeader={sidebarExtraHeader}
            sidebar={sidebarContent}
            main={mainContent}
            mainOverlay={mainAreaOverlay}
            bottom={bottomContent}
        />
    );
};
