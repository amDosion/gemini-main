
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { 
  Image as ImageIcon, Layers, Clock, AlertCircle, Grid,
  Wand2, SlidersHorizontal, RotateCcw, ChevronLeft, ChevronRight, Sparkles
} from 'lucide-react';
import { GenViewLayout } from '../common/GenViewLayout';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import { getUrlType } from '../../hooks/handlers/attachmentUtils';
import { useControlsState } from '../../hooks/useControlsState';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';

interface ImageGenViewProps {
    messages: Message[];
    setAppMode: (mode: AppMode) => void;
    onImageClick: (url: string) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    visibleModels?: ModelConfig[];  // 当前模式下可见的模型列表
    allVisibleModels?: ModelConfig[];  // ✅ 新增：完整模型列表
    initialPrompt?: string;
    onEditImage?: (url: string, attachment?: Attachment) => void;
    onExpandImage?: (url: string, attachment?: Attachment) => void;  // ✅ 修复：添加可选的 attachment 参数
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
    allVisibleModels = [],  // ✅ 新增
    initialPrompt,
    onEditImage,
    onExpandImage,
    providerId
}) => {
    // Track selected MESSAGE ID (Batch)
    const [selectedMsgId, setSelectedMsgId] = useState<string | null>(null);
    // Mobile History Toggle
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
    // 旋转木马当前索引
    const [carouselIndex, setCarouselIndex] = useState(0);
    
    // ✅ 使用统一的状态管理 hook
    const controls = useControlsState('image-gen', activeModelConfig);
    
    // ✅ 图片缩放 hook（用于单图放大查看）
    const canvas = useImageCanvas({ minZoom: 0.5, maxZoom: 5, initialZoom: 1 });
    
    // ✅ 本地 UI 状态
    const [prompt, setPrompt] = useState(initialPrompt || '');
    const [showAdvanced, setShowAdvanced] = useState(true); // 默认展开高级参数
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    
    const isLoading = loadingState !== 'idle';

    // ✅ 检测提供商类型
    const isOpenAI = providerId === 'openai';

    // ✅ 最大图片数量（OpenAI 只支持 1 张）
    const maxImageCount = isOpenAI ? 1 : 4;

    // ✅ OpenAI 只支持 1 张图片
    useEffect(() => {
        if (isOpenAI && controls.numberOfImages !== 1) {
            controls.setNumberOfImages(1);
        } else if (controls.numberOfImages > maxImageCount) {
            controls.setNumberOfImages(maxImageCount);
        }
    }, [isOpenAI, controls.numberOfImages, maxImageCount, controls]);

    // ✅ 重置参数
    const resetParams = useCallback(() => {
        controls.setStyle('None');
        controls.setNumberOfImages(1);
        controls.setAspectRatio('1:1');
        controls.setResolution('1K');
        controls.setNegativePrompt('');
        controls.setSeed(-1);
        controls.setOutputMimeType('image/png');
        controls.setOutputCompressionQuality(80);
        controls.setEnhancePrompt(false);
    }, [controls]);

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

    // ✅ 当批次切换时，重置旋转木马索引和缩放
    useEffect(() => {
        setCarouselIndex(0);
        canvas.resetView();
    }, [activeBatchMessage?.id]);

    // ✅ 确保 carouselIndex 不越界
    useEffect(() => {
        if (carouselIndex >= displayImages.length && displayImages.length > 0) {
            setCarouselIndex(displayImages.length - 1);
        }
    }, [displayImages.length, carouselIndex]);

    // ✅ 键盘左右键切换图片
    useEffect(() => {
        if (displayImages.length <= 1) return;
        
        const handleKeyDown = (e: KeyboardEvent) => {
            // 如果焦点在输入框内，不处理
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
                return;
            }
            
            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                setCarouselIndex((prev) => (prev - 1 + displayImages.length) % displayImages.length);
                canvas.resetView();
            } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                setCarouselIndex((prev) => (prev + 1) % displayImages.length);
                canvas.resetView();
            }
        };
        
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [displayImages.length, canvas]);
    
    // ✅ 详细日志：记录显示图片时使用的URL类型
    useEffect(() => {
        if (displayImages.length > 0) {
            console.log('[ImageGenView] ========== 显示图片URL类型分析 ==========');
            displayImages.forEach((att, idx) => {
                const urlType = getUrlType(att.url, att.uploadStatus);
                
                const hasCloudUrl = att.uploadStatus === 'completed' && 
                                   (att.url?.startsWith('http://') || att.url?.startsWith('https://'));
                
                // 对于BASE64 URL，只输出类型和长度，不输出实际内容
                const formatUrlForLog = (url: string | undefined): string => {
                    if (!url) return 'N/A';
                    if (url.startsWith('data:')) {
                        return `Base64 Data URL (长度: ${url.length} 字符)`;
                    }
                    return url.length > 80 ? url.substring(0, 80) + '...' : url;
                };

                console.log(`[ImageGenView] 图片 ${idx + 1}/${displayImages.length}:`, {
                    attachmentId: att.id || 'N/A',
                    displayUrlType: urlType,
                    displayUrl: formatUrlForLog(att.url),
                    uploadStatus: att.uploadStatus,
                    hasCloudUrl: hasCloudUrl,
                    cloudUrl: hasCloudUrl ? formatUrlForLog(att.url!) : 'N/A',
                    tempUrl: formatUrlForLog(att.tempUrl),
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

    // ✅ 生成处理函数
    const handleGenerate = useCallback(() => {
        if (!prompt.trim() || isLoading) return;
        
        const options: ChatOptions = {
            enableSearch: false,
            enableThinking: false,
            enableCodeExecution: false,
            // 基础参数
            imageAspectRatio: controls.aspectRatio,
            imageResolution: controls.resolution,
            numberOfImages: controls.numberOfImages,
            imageStyle: controls.style !== 'None' ? controls.style : undefined,
            // Google Imagen 高级参数
            negativePrompt: controls.negativePrompt || undefined,
            seed: controls.seed !== -1 ? controls.seed : undefined,
            outputMimeType: controls.outputMimeType,
            outputCompressionQuality: controls.outputCompressionQuality,
            enhancePrompt: controls.enhancePrompt,
            // TongYi 专用参数
            promptExtend: controls.promptExtend,
            addMagicSuffix: controls.addMagicSuffix,
        };
        
        onSend(prompt, options, [], 'image-gen');
        setPrompt(''); // 发送后清空提示词
    }, [prompt, controls, isLoading, onSend]);

    // ✅ 键盘快捷键
    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleGenerate();
        }
    }, [handleGenerate]);

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
                            <p className="text-[11px] text-slate-300 leading-relaxed font-medium whitespace-pre-wrap break-words">
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

    // ✅ 主区域：两栏布局（结果显示 + 控制面板）
    // 注意：GenViewLayout 的 main 容器已有 overflow-hidden，这里不需要重复
    const mainContent = useMemo(() => (
        <div className="flex-1 flex flex-row h-full">
            {/* ========== 左侧：结果显示区 ========== */}
            <div className="flex-1 w-full h-full select-none flex flex-col relative">
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

                {/* 主图片显示区域 - 简化布局，居中显示 */}
                {isLoading ? (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="flex flex-col items-center gap-6 p-8 rounded-3xl bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 shadow-2xl">
                            <div className="relative">
                                <div className="w-20 h-20 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin"></div>
                                <div className="absolute inset-0 flex items-center justify-center text-xs font-mono text-emerald-400 font-bold">GEN</div>
                            </div>
                            <div className="text-center space-y-2">
                                <p className="text-slate-200 font-medium text-lg">生成中...</p>
                                <p className="text-slate-500 text-sm">这可能需要几秒钟</p>
                            </div>
                        </div>
                    </div>
                ) : isBatchError ? (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="flex flex-col items-center gap-4 text-center p-8 bg-slate-900/50 rounded-2xl border border-red-900/30">
                            <AlertCircle size={48} className="text-red-500 opacity-80" />
                            <div>
                                <h3 className="text-lg font-bold text-slate-200">生成失败</h3>
                                <p className="text-sm text-red-400 mt-2 max-w-md">{activeBatchMessage?.content || "未知错误"}</p>
                            </div>
                        </div>
                    </div>
                ) : displayImages.length > 0 ? (
                    <>
                        {/* 旋转木马视图（直接支持缩放） */}
                        <div 
                            className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden"
                            onWheel={canvas.handleWheel}
                        >
                            {/* 主图展示区 - 支持拖拽 */}
                            <div 
                                className="flex-1 w-full flex items-center justify-center relative px-16 overflow-hidden"
                                onMouseDown={canvas.handleMouseDown}
                                onMouseMove={canvas.handleMouseMove}
                                onMouseUp={canvas.handleMouseUp}
                                onMouseLeave={canvas.handleMouseUp}
                                style={{ cursor: canvas.isDragging ? 'grabbing' : (canvas.zoom > 1 ? 'grab' : 'default') }}
                            >
                                {/* 左箭头 */}
                                {displayImages.length > 1 && (
                                    <button
                                        onClick={() => { setCarouselIndex((prev) => (prev - 1 + displayImages.length) % displayImages.length); canvas.resetView(); }}
                                        className="absolute left-4 z-10 p-3 rounded-full bg-black/50 hover:bg-black/70 text-white backdrop-blur border border-white/10 transition-all hover:scale-110"
                                        title="上一张"
                                    >
                                        <ChevronLeft size={24} />
                                    </button>
                                )}
                                
                                {/* 当前图片 */}
                                <div className="relative group max-w-full max-h-full flex items-center justify-center">
                                    {displayImages[carouselIndex]?.url ? (
                                        <img
                                            src={displayImages[carouselIndex].url}
                                            className="block max-h-[70vh] max-w-full object-contain rounded-2xl shadow-2xl border border-slate-800/50 select-none"
                                            style={canvas.canvasStyle}
                                            onDoubleClick={() => onImageClick(displayImages[carouselIndex].url!)}
                                            alt={`生成图片 ${carouselIndex + 1}`}
                                            draggable={false}
                                        />
                                    ) : (
                                        <div className="w-64 h-64 flex items-center justify-center text-slate-600 bg-slate-900 rounded-2xl">
                                            <ImageIcon size={48} className="opacity-50" />
                                        </div>
                                    )}
                                    {/* 悬浮操作按钮（包含缩放控制） */}
                                    <ImageCanvasControls
                                        variant="canvas"
                                        mode="image-gen"
                                        modeAware={false}
                                        className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                                        zoom={canvas.zoom}
                                        onZoomIn={canvas.handleZoomIn}
                                        onZoomOut={canvas.handleZoomOut}
                                        onReset={canvas.handleReset}
                                        onEdit={onEditImage ? () => onEditImage(displayImages[carouselIndex].url!, displayImages[carouselIndex]) : undefined}
                                        onExpand={onExpandImage ? () => onExpandImage(displayImages[carouselIndex].url!, displayImages[carouselIndex]) : undefined}
                                        onFullscreen={() => onImageClick(displayImages[carouselIndex].url!)}
                                        downloadUrl={displayImages[carouselIndex].url}
                                    />
                                </div>
                                
                                {/* 右箭头 */}
                                {displayImages.length > 1 && (
                                    <button
                                        onClick={() => { setCarouselIndex((prev) => (prev + 1) % displayImages.length); canvas.resetView(); }}
                                        className="absolute right-4 z-10 p-3 rounded-full bg-black/50 hover:bg-black/70 text-white backdrop-blur border border-white/10 transition-all hover:scale-110"
                                        title="下一张"
                                    >
                                        <ChevronRight size={24} />
                                    </button>
                                )}
                                
                                {/* 缩放提示（仅在缩放时显示） */}
                                {canvas.zoom !== 1 && (
                                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-slate-400 text-xs bg-black/60 px-3 py-1.5 rounded-full backdrop-blur pointer-events-none">
                                        {Math.round(canvas.zoom * 100)}% · 拖拽移动 · 双击全屏
                                    </div>
                                )}
                            </div>
                            
                            {/* 底部缩略图导航 */}
                            {displayImages.length > 1 && (
                                <div className="flex items-center gap-3 py-4 px-4">
                                    {displayImages.map((att, idx) => (
                                        <button
                                            key={idx}
                                            onClick={() => { setCarouselIndex(idx); canvas.resetView(); }}
                                            className={`relative rounded-lg overflow-hidden transition-all duration-200 ${
                                                idx === carouselIndex 
                                                    ? 'ring-2 ring-emerald-500 scale-110' 
                                                    : 'opacity-60 hover:opacity-100 hover:scale-105'
                                            }`}
                                        >
                                            {att.url ? (
                                                <img
                                                    src={att.url}
                                                    className="w-16 h-16 object-cover"
                                                    alt={`缩略图 ${idx + 1}`}
                                                />
                                            ) : (
                                                <div className="w-16 h-16 bg-slate-800 flex items-center justify-center">
                                                    <ImageIcon size={20} className="text-slate-600" />
                                                </div>
                                            )}
                                            {/* 当前选中指示 */}
                                            {idx === carouselIndex && (
                                                <div className="absolute inset-0 bg-emerald-500/20" />
                                            )}
                                        </button>
                                    ))}
                                    {/* 图片计数 */}
                                    <span className="ml-2 text-sm text-slate-400 font-mono">
                                        {carouselIndex + 1} / {displayImages.length}
                                    </span>
                                </div>
                            )}
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
                            <ImageIcon size={48} className="opacity-20" />
                            <div>
                                <h3 className="text-xl font-bold text-slate-500 mb-2">Image Generator</h3>
                                <p className="text-sm opacity-60">在右侧输入提示词，设置参数后点击生成</p>
                            </div>
                        </div>
                    </div>
                )}

                {/* 批次信息提示 */}
                {displayImages.length > 1 && (
                    <div className="absolute top-4 left-4 z-10 animate-[fadeIn_0.3s_ease-out] pointer-events-none">
                        <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-xl">
                            <Grid size={14} className="text-emerald-400" />
                            批次结果 ({displayImages.length})
                        </div>
                    </div>
                )}
            </div>

            {/* ========== 中间：控制面板 ========== */}
            <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
                {/* 头部 */}
                <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal size={14} className="text-emerald-400" />
                        <span className="text-xs font-bold text-white">生成参数</span>
                    </div>
                    <button
                        onClick={resetParams}
                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                        title="重置为默认值"
                    >
                        <RotateCcw size={12} />
                    </button>
                </div>

                {/* 参数滚动区 - 通过 ModeControlsCoordinator 分发对应的参数组件 */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
                    <ModeControlsCoordinator
                        mode="image-gen"
                        providerId={providerId || 'google'}
                        currentModel={activeModelConfig}
                        controls={controls}
                        maxImageCount={maxImageCount}
                    />
                </div>

                {/* 底部固定区：提示词 + 生成按钮 */}
                <div className="border-t border-slate-800 p-3 space-y-2 bg-slate-900/80">
                    {/* 提示词输入 - 自动调整高度 */}
                    <textarea
                        ref={textareaRef}
                        value={prompt}
                        onChange={(e) => {
                            setPrompt(e.target.value);
                            // 自动调整高度
                            e.target.style.height = 'auto';
                            e.target.style.height = Math.min(e.target.scrollHeight, 300) + 'px';
                        }}
                        onKeyDown={handleKeyDown}
                        placeholder="描述你想要生成的图片..."
                        className="w-full min-h-[80px] max-h-[300px] bg-slate-800/80 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 overflow-y-auto"
                    />

                    {/* 生成按钮 */}
                    <button
                        onClick={handleGenerate}
                        disabled={!prompt.trim() || isLoading}
                        className="w-full py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isLoading ? (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                生成中...
                            </>
                        ) : (
                            <>
                                <Sparkles size={18} />
                                生成图片
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    ), [isLoading, isBatchError, displayImages, activeBatchMessage, onImageClick, onEditImage, onExpandImage, prompt, controls, handleGenerate, handleKeyDown, maxImageCount, resetParams, providerId, activeModelConfig, carouselIndex, canvas]);

    return (
        <GenViewLayout
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            sidebarTitle="History"
            sidebarHeaderIcon={sidebarHeaderIcon}
            sidebarExtraHeader={sidebarExtraHeader}
            sidebar={sidebarContent}
            main={mainContent}
        />
    );
};
