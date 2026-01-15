/**
 * Virtual Try-On 视图组件
 * 
 * 功能：虚拟试衣 - 上传人物照片，通过 AI 替换服装
 * 复用 ImageEditView 的布局结构和交互模式
 */
import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Shirt, AlertCircle, Layers, User, Bot, Sparkles } from 'lucide-react';
import { v4 as uuidv4 } from 'uuid';
import InputArea from '../chat/InputArea';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import { ImageCompare } from '../common/ImageCompare';
import { GenViewLayout } from '../common/GenViewLayout';
import { useToastContext } from '../../contexts/ToastContext';

interface VirtualTryOnViewProps {
    messages: Message[];
    setAppMode: (mode: AppMode) => void;
    onImageClick: (url: string) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    visibleModels?: ModelConfig[];  // 新增
    initialPrompt?: string;
    initialAttachments?: Attachment[];
    providerId?: string;
    sessionId?: string | null;
    apiKey?: string;  // ✅ API Key，用于调用 Gemini API
}

/**
 * useDebounce Hook - 防抖工具函数
 * 用于延迟更新值，避免频繁触发副作用
 * 
 * @template T - 值的类型
 * @param value - 需要防抖的值
 * @param delay - 延迟时间（毫秒）
 * @returns 防抖后的值
 */
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    // 设置延迟更新
    const handler = setTimeout(() => {
      console.log('[useDebounce] 防抖值更新:', value);
      setDebouncedValue(value);
    }, delay);

    // 清理函数：值变化或组件卸载时清除 timeout
    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

export const VirtualTryOnView: React.FC<VirtualTryOnViewProps> = ({
    messages,
    setAppMode,
    onImageClick,
    loadingState,
    onSend,
    onStop,
    activeModelConfig,
    visibleModels = [],
    initialPrompt,
    initialAttachments,
    providerId,
    sessionId: currentSessionId,
    apiKey  // ✅ 接收 apiKey prop
}) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    // State for reference image
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
    const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);
    const [lastProcessedMsgId, setLastProcessedMsgId] = useState<string | null>(null);
    const [isCompareMode, setIsCompareMode] = useState(false);
    const { showError, showWarning } = useToastContext();
    
    // State for Try-On Target (跟踪当前选择的服装类型)
    const [currentTryOnTarget, setCurrentTryOnTarget] = useState('upper');
    
    // State for Upscale (视图层状态，完全在 View 中管理)
    const [enableUpscale, setEnableUpscale] = useState(false);
    const [upscaleFactor, setUpscaleFactor] = useState<2 | 4>(2);
    const [addWatermark, setAddWatermark] = useState(false);
    
    // State for Mask Preview (视图层状态，完全在 View 中管理)
    const [showMaskPreview, setShowMaskPreview] = useState(false);
    const [maskPreviewUrl, setMaskPreviewUrl] = useState<string | null>(null);
    const [isGeneratingMask, setIsGeneratingMask] = useState(false);
    
    // State for Mask Preview Parameters (掩码预览参数)
    const [maskAlpha, setMaskAlpha] = useState(0.7);        // 透明度，默认 70%
    const [maskThreshold, setMaskThreshold] = useState(50);  // 阈值，默认 50

    // 防抖值（用于自动重新生成掩码预览）
    const debouncedAlpha = useDebounce(maskAlpha, 300);
    const debouncedThreshold = useDebounce(maskThreshold, 300);

    // Pan & Zoom Hook
    const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });

    // 参数持久化：从 localStorage 恢复用户偏好
    useEffect(() => {
        const savedAlpha = localStorage.getItem('maskPreviewAlpha');
        const savedThreshold = localStorage.getItem('maskPreviewThreshold');
        
        if (savedAlpha) {
            const alphaValue = Number(savedAlpha);
            if (alphaValue >= 0.3 && alphaValue <= 1.0) {
                setMaskAlpha(alphaValue);
            }
        }
        if (savedThreshold) {
            const thresholdValue = Number(savedThreshold);
            if (thresholdValue >= 10 && thresholdValue <= 200) {
                setMaskThreshold(thresholdValue);
            }
        }
    }, []);

    // 参数持久化：保存用户偏好到 localStorage
    useEffect(() => {
        localStorage.setItem('maskPreviewAlpha', maskAlpha.toString());
        localStorage.setItem('maskPreviewThreshold', maskThreshold.toString());
    }, [maskAlpha, maskThreshold]);

    // 防抖值监听：参数变化时自动重新生成掩码预览
    const isFirstRender = useRef(true);

    useEffect(() => {
        // 跳过首次渲染
        if (isFirstRender.current) {
            isFirstRender.current = false;
            console.log('[VirtualTryOnView] 跳过首次渲染的掩码重新生成');
            return;
        }

        // 只有在掩码预览已开启且已生成过掩码时才自动重新生成
        if (showMaskPreview && maskPreviewUrl && activeImageUrl && apiKey) {
            console.log('[VirtualTryOnView] 防抖值变化，重新生成掩码预览', {
                alpha: debouncedAlpha,
                threshold: debouncedThreshold
            });
            // eslint-disable-next-line react-hooks/exhaustive-deps
            handleGenerateMaskPreview();
        }
    }, [debouncedAlpha, debouncedThreshold, showMaskPreview, maskPreviewUrl, activeImageUrl, apiKey]);

    // Reset View when image changes
    useEffect(() => {
        canvas.resetView();
        setIsCompareMode(false);
    }, [activeImageUrl]);

    // 获取原图 URL（用于对比）
    const originalImageUrl = useMemo(() => {
        const lastUserMsg = [...messages].reverse().find(m => m.role === Role.USER && m.attachments?.length);
        return lastUserMsg?.attachments?.[0]?.url || null;
    }, [messages]);

    // Sync initial attachments
    useEffect(() => {
        if (initialAttachments && initialAttachments.length > 0) {
            setActiveAttachments(initialAttachments);
            setActiveImageUrl(initialAttachments[0].url || null);
        }
    }, [initialAttachments]);

    // Sync uploaded attachment to main view
    useEffect(() => {
        if (activeAttachments.length > 0 && activeAttachments[0].url) {
            setActiveImageUrl(activeAttachments[0].url);
        }
    }, [activeAttachments]);

    // Auto-scroll history
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, activeAttachments]);

    // Auto-select latest result
    useEffect(() => {
        if (activeAttachments.length === 0 && !activeImageUrl) {
            const lastModelMsg = [...messages].reverse().find(m => m.role === Role.MODEL && m.attachments?.length);
            if (lastModelMsg && lastModelMsg.attachments?.[0]?.url) {
                setActiveImageUrl(lastModelMsg.attachments[0].url);
            }
        }

        if (loadingState === 'idle' && messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            if (lastMsg.id !== lastProcessedMsgId) {
                if (lastMsg.role === Role.MODEL && lastMsg.attachments && lastMsg.attachments.length > 0 && lastMsg.attachments[0].url) {
                    setActiveImageUrl(lastMsg.attachments[0].url);
                    setLastProcessedMsgId(lastMsg.id);
                } else if (lastMsg.isError) {
                    setLastProcessedMsgId(lastMsg.id);
                }
            }
        }
    }, [messages, activeAttachments.length, loadingState, lastProcessedMsgId, activeImageUrl]);


    // 从历史消息中查找附件
    const findAttachmentFromHistory = useCallback((targetUrl: string): { attachment: Attachment; messageId: string } | null => {
        for (const msg of [...messages].reverse()) {
            for (const att of msg.attachments || []) {
                if (att.url === targetUrl || att.tempUrl === targetUrl) {
                    return { attachment: att, messageId: msg.id };
                }
            }
        }
        return null;
    }, [messages]);

    // 从后端查询附件信息
    const fetchAttachmentFromBackend = useCallback(async (sessionId: string, attachmentId: string): Promise<{
        url: string;
        uploadStatus: string;
        taskId?: string;
    } | null> => {
        try {
            const response = await fetch(`/api/sessions/${sessionId}/attachments/${attachmentId}`);
            if (!response.ok) return null;
            return await response.json();
        } catch (e) {
            console.error('[fetchAttachmentFromBackend] 查询异常:', e);
            return null;
        }
    }, []);

    // 生成掩码预览
    const handleGenerateMaskPreview = useCallback(async () => {
        if (!activeImageUrl || !apiKey) {
            console.warn('[handleGenerateMaskPreview] 缺少图片或 API Key');
            showWarning('请先上传图片并确保已配置 API Key');
            return;
        }
        
        setIsGeneratingMask(true);
        try {
            // ===== 图片 URL 类型转换 =====
            // 确保传递给 API 的是 Base64 格式的图片
            let imageBase64: string;
            
            const isBase64 = activeImageUrl.startsWith('data:');
            const isBlobUrl = activeImageUrl.startsWith('blob:');
            const isCloudUrl = activeImageUrl.startsWith('http://') || activeImageUrl.startsWith('https://');
            
            console.log('[handleGenerateMaskPreview] 图片 URL 类型:', 
                isBase64 ? 'Base64' : isBlobUrl ? 'Blob URL' : isCloudUrl ? '云存储 URL' : '未知');
            
            if (isBase64) {
                // 已经是 Base64，直接使用
                imageBase64 = activeImageUrl;
            } else if (isBlobUrl) {
                // Blob URL，读取并转换为 Base64
                console.log('[handleGenerateMaskPreview] 转换 Blob URL 为 Base64');
                const response = await fetch(activeImageUrl);
                const blob = await response.blob();
                imageBase64 = await new Promise<string>((resolve) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result as string);
                    reader.readAsDataURL(blob);
                });
            } else if (isCloudUrl) {
                // 云存储 URL，通过后端代理下载并转换为 Base64
                console.log('[handleGenerateMaskPreview] 从云存储下载图片并转换为 Base64');
                const fetchUrl = `/api/storage/download?url=${encodeURIComponent(activeImageUrl)}`;
                const response = await fetch(fetchUrl);
                const blob = await response.blob();
                imageBase64 = await new Promise<string>((resolve) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result as string);
                    reader.readAsDataURL(blob);
                });
            } else {
                throw new Error('不支持的图片 URL 格式');
            }
            
            console.log('[handleGenerateMaskPreview] 图片转换完成，Base64 长度:', imageBase64.length);
            
            // ===== 调用掩码预览生成 =====
            const { generateMaskPreview } = await import('../../services/providers/google/media/virtual-tryon');
            
            // 将 tryOnTarget 映射到完整的服装类型描述
            const targetClothingMap: Record<string, string> = {
                'upper': 'upper body clothing',
                'lower': 'lower body clothing',
                'full': 'full body clothing'
            };
            const targetClothing = targetClothingMap[currentTryOnTarget] || 'upper body clothing';
            
            console.log(`[handleGenerateMaskPreview] 生成掩码预览: ${targetClothing}, Alpha: ${maskAlpha}, Threshold: ${maskThreshold}`);

            const previewUrl = await generateMaskPreview(
                imageBase64,  // ✅ 使用转换后的 Base64
                targetClothing,
                apiKey,
                activeModelConfig?.id,  // ✅ 传递当前选择的模型 ID
                maskAlpha,
                maskThreshold
            );
            
            setMaskPreviewUrl(previewUrl);
            setShowMaskPreview(true);
            console.log('[handleGenerateMaskPreview] 掩码预览生成成功');
        } catch (error) {
            console.error('[handleGenerateMaskPreview] 生成失败:', error);
            // 掩码预览生成失败
            // Error handling is done via toast
        } finally {
            setIsGeneratingMask(false);
        }
    }, [activeImageUrl, apiKey, currentTryOnTarget, activeModelConfig?.id, maskAlpha, maskThreshold]);

    const handleSend = useCallback(async (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
        console.log('========== [VirtualTryOnView] handleSend 开始 ==========');
        console.log('[handleSend] 服装描述:', text);
        console.log('[handleSend] tryOnTarget:', options.virtualTryOnTarget);

        let finalAttachments = [...attachments];

        // CONTINUITY LOGIC: 当用户没有上传新图片时，使用画布上的图片
        if (finalAttachments.length === 0 && activeImageUrl) {
            console.log('[handleSend] 触发 CONTINUITY LOGIC');

            try {
                const isBase64 = activeImageUrl?.startsWith('data:');
                const isBlobUrl = activeImageUrl?.startsWith('blob:');
                const isCloudUrl = activeImageUrl?.startsWith('http://') || activeImageUrl?.startsWith('https://');

                const found = findAttachmentFromHistory(activeImageUrl);

                if (found) {
                    const { attachment: existingAttachment } = found;
                    let finalUrl = existingAttachment.url;
                    let finalUploadStatus = existingAttachment.uploadStatus || 'completed';

                    if (finalUploadStatus === 'pending' && currentSessionId) {
                        const backendData = await fetchAttachmentFromBackend(currentSessionId, existingAttachment.id);
                        if (backendData && backendData.url?.startsWith('http')) {
                            finalUrl = backendData.url;
                            finalUploadStatus = 'completed';
                        }
                    }

                    const reusedAttachment: Attachment = {
                        id: uuidv4(),
                        mimeType: existingAttachment.mimeType || 'image/png',
                        name: existingAttachment.name || `canvas-${Date.now()}.png`,
                        url: finalUrl,
                        uploadStatus: finalUploadStatus
                    };

                    if (isBase64 && activeImageUrl) {
                        (reusedAttachment as any).base64Data = activeImageUrl;
                    } else if (finalUrl?.startsWith('http')) {
                        const fetchUrl = `/api/storage/download?url=${encodeURIComponent(finalUrl)}`;
                        const response = await fetch(fetchUrl);
                        const blob = await response.blob();
                        const base64Url = await new Promise<string>((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result as string);
                            reader.readAsDataURL(blob);
                        });
                        (reusedAttachment as any).base64Data = base64Url;
                    } else {
                        (reusedAttachment as any).base64Data = existingAttachment.url;
                    }

                    finalAttachments = [reusedAttachment];

                } else if (isCloudUrl) {
                    const fetchUrl = `/api/storage/download?url=${encodeURIComponent(activeImageUrl)}`;
                    const response = await fetch(fetchUrl);
                    const blob = await response.blob();
                    const base64Url = await new Promise<string>((resolve) => {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result as string);
                        reader.readAsDataURL(blob);
                    });

                    const reusedAttachment: Attachment = {
                        id: uuidv4(),
                        mimeType: blob.type || 'image/png',
                        name: `canvas-${Date.now()}.png`,
                        url: activeImageUrl,
                        uploadStatus: 'completed'
                    };
                    (reusedAttachment as any).base64Data = base64Url;
                    finalAttachments = [reusedAttachment];

                } else if (isBase64 || isBlobUrl) {
                    let base64Url: string;
                    if (isBlobUrl) {
                        const response = await fetch(activeImageUrl);
                        const blob = await response.blob();
                        base64Url = await new Promise<string>((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result as string);
                            reader.readAsDataURL(blob);
                        });
                    } else {
                        base64Url = activeImageUrl;
                    }

                    const reusedAttachment: Attachment = {
                        id: uuidv4(),
                        mimeType: 'image/png',
                        name: `canvas-${Date.now()}.png`,
                        url: base64Url,
                        uploadStatus: 'completed'
                    };
                    (reusedAttachment as any).base64Data = base64Url;
                    finalAttachments = [reusedAttachment];
                }
            } catch (e) {
                console.error("[handleSend] CONTINUITY LOGIC 失败:", e);
            }
        }

        console.log('[handleSend] 最终附件数量:', finalAttachments.length);
        
        // 更新当前选择的服装类型（用于掩码预览）
        if (options.virtualTryOnTarget) {
            setCurrentTryOnTarget(options.virtualTryOnTarget);
        }
        
        // 添加 Upscale 选项到 options（从 View 内部状态）
        const finalOptions = {
            ...options,
            enableUpscale,
            upscaleFactor,
            addWatermark
        };
        
        onSend(text, finalOptions, finalAttachments, mode);
    }, [activeImageUrl, currentSessionId, findAttachmentFromHistory, fetchAttachmentFromBackend, enableUpscale, upscaleFactor, addWatermark, onSend]);

    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

    // 缓存 sidebarContent
    const sidebarContent = useMemo(() => (
                <div className="flex-1 p-4 space-y-6">
                    {messages.map((msg) => {
                        const isPlaceholder = !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
                        if (isPlaceholder) return null;

                        return (
                            <div key={msg.id} className={`flex flex-col gap-2 ${msg.role === Role.USER ? 'items-end' : 'items-start'}`}>
                                <div className="flex items-center gap-2 text-xs text-slate-500 px-1">
                                    {msg.role === Role.USER ? <User size={12} /> : <Bot size={12} />}
                                    <span>{msg.role === Role.USER ? 'You' : (activeModelConfig?.name || 'AI')}</span>
                                </div>
                                <div className={`p-3 rounded-2xl max-w-full text-sm shadow-sm ${msg.role === Role.USER
                                    ? 'bg-slate-800 text-slate-200 rounded-tr-sm'
                                    : 'bg-slate-800/50 text-slate-300 border border-slate-700/50 rounded-tl-sm'
                                    }`}>
                                    {msg.content && <p className="mb-2">{msg.content}</p>}
                                    {msg.attachments?.filter(att => att.url && att.url.length > 0).map((att, idx) => (
                                        <div
                                            key={idx}
                                            onClick={() => setActiveImageUrl(att.url || null)}
                                            className={`relative group mt-1 rounded-lg overflow-hidden border cursor-pointer transition-all ${activeImageUrl === att.url ? 'ring-2 ring-rose-500 border-transparent' : 'border-slate-700 hover:border-slate-500'
                                                }`}
                                        >
                                            <img src={att.url} className="w-full h-32 object-cover bg-slate-900" alt="thumbnail" />
                                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                                                {activeImageUrl === att.url && <div className="bg-rose-500 w-2 h-2 rounded-full absolute top-2 right-2 shadow-sm" />}
                                            </div>
                                        </div>
                                    ))}
                                    {msg.isError && (
                                        <div className="flex items-center gap-2 text-red-400 text-xs mt-1">
                                            <AlertCircle size={12} /> Error generating
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                    {loadingState !== 'idle' && (
                        <div className="flex items-start gap-2 animate-pulse">
                            <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center"><Bot size={16} className="text-slate-500" /></div>
                            <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400">Processing try-on...</div>
                        </div>
                    )}
                    <div ref={scrollRef} />
                </div>
    ), [messages, loadingState, activeModelConfig?.name, activeImageUrl]);

    // 缓存 mainContent
    const mainContent = useMemo(() => (
                <div
                    className="flex-1 w-full h-full select-none flex flex-col relative"
                    onWheel={isCompareMode ? undefined : canvas.handleWheel}
                    onMouseDown={isCompareMode ? undefined : canvas.handleMouseDown}
                    onMouseMove={isCompareMode ? undefined : canvas.handleMouseMove}
                    onMouseUp={isCompareMode ? undefined : canvas.handleMouseUp}
                    onMouseLeave={isCompareMode ? undefined : canvas.handleMouseUp}
                    style={{ cursor: isCompareMode ? 'default' : canvas.isDragging ? 'grabbing' : activeImageUrl ? 'grab' : 'default' }}
                >
                    {/* Checkerboard Background */}
                    <div className="absolute inset-0 opacity-20 pointer-events-none"
                        style={{
                            backgroundImage: `
                               linear-gradient(45deg, #334155 25%, transparent 25%), 
                               linear-gradient(-45deg, #334155 25%, transparent 25%), 
                               linear-gradient(45deg, transparent 75%, #334155 75%), 
                               linear-gradient(-45deg, transparent 75%, #334155 75%)
                           `,
                            backgroundSize: '20px 20px',
                            backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px'
                        }}
                    />

                    {/* Canvas Header */}
                    <div className="absolute top-4 left-4 z-10 pointer-events-none">
                        <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-lg">
                            <Shirt size={12} className="text-rose-400" />
                            {isCompareMode ? '对比模式' : activeAttachments.length > 0 && activeImageUrl === activeAttachments[0].url ? 'Source Preview' : 'Try-On Result'}
                            <span className="opacity-50">|</span>
                            <span className="font-mono text-[10px] opacity-70">{Math.round(canvas.zoom * 100)}%</span>
                        </div>
                    </div>

                    {/* Upscale & Mask Preview Controls (视图层功能，保留在 View 中) */}
                    {activeImageUrl && (
                        <div 
                            className="absolute top-4 right-4 z-10 flex flex-col gap-2 pointer-events-auto"
                            onMouseDown={(e) => e.stopPropagation()}
                            onMouseMove={(e) => e.stopPropagation()}
                        >
                            {/* Upscale Controls */}
                            <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-lg p-3 text-xs">
                                <div className="flex items-center gap-2 mb-2">
                                    <Sparkles size={12} className="text-rose-400" />
                                    <span className="font-medium text-slate-300">Upscale</span>
                                </div>
                                <div className="flex items-center gap-2 mb-2">
                                    <input
                                        type="checkbox"
                                        checked={enableUpscale}
                                        onChange={(e) => setEnableUpscale(e.target.checked)}
                                        className="w-3 h-3"
                                    />
                                    <span className="text-slate-400">启用超分辨率</span>
                                </div>
                                {enableUpscale && (
                                    <>
                                        <div className="flex gap-2 mb-2">
                                            <button
                                                onClick={() => setUpscaleFactor(2)}
                                                className={`px-2 py-1 rounded text-[10px] ${upscaleFactor === 2 ? 'bg-rose-500 text-white' : 'bg-slate-700 text-slate-300'}`}
                                            >
                                                2x
                                            </button>
                                            <button
                                                onClick={() => setUpscaleFactor(4)}
                                                className={`px-2 py-1 rounded text-[10px] ${upscaleFactor === 4 ? 'bg-rose-500 text-white' : 'bg-slate-700 text-slate-300'}`}
                                            >
                                                4x
                                            </button>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <input
                                                type="checkbox"
                                                checked={addWatermark}
                                                onChange={(e) => setAddWatermark(e.target.checked)}
                                                className="w-3 h-3"
                                            />
                                            <span className="text-slate-400">添加水印</span>
                                        </div>
                                    </>
                                )}
                            </div>

                            {/* Mask Preview Controls */}
                            <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-lg p-3 text-xs text-slate-300">
                                <button
                                    onClick={() => showMaskPreview ? setShowMaskPreview(false) : handleGenerateMaskPreview()}
                                    disabled={isGeneratingMask}
                                    className="w-full text-left font-medium pb-2 mb-2 border-b border-white/10 flex items-center justify-between hover:text-white transition-colors disabled:opacity-50"
                                >
                                    <span>掩码预览 ({showMaskPreview ? '开启' : '关闭'})</span>
                                    <Sparkles size={12} className={showMaskPreview ? 'text-rose-400' : 'text-slate-400'} />
                                </button>

                                {showMaskPreview && (
                                    <div className="space-y-4 pt-2">
                                        {/* Transparency Slider (Alpha) */}
                                        <div>
                                            <div className="flex items-center justify-between mb-1">
                                                <label htmlFor="mask-alpha" className="text-slate-400">透明度</label>
                                                <span className="text-slate-300 font-mono text-[10px]">{Math.round(maskAlpha * 100)}%</span>
                                            </div>
                                            <input
                                                type="range"
                                                id="mask-alpha"
                                                min="0.3"
                                                max="1.0"
                                                step="0.05"
                                                value={maskAlpha}
                                                onChange={(e) => {
                                                  const value = parseFloat(e.target.value);
                                                  if (!isNaN(value)) {
                                                    setMaskAlpha(Math.max(0.3, Math.min(1.0, value)));
                                                  }
                                                }}
                                                className="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer accent-rose-500"
                                            />
                                            <p className="text-[10px] text-slate-500 mt-1">调整掩码透明度，以便查看底层图像。</p>
                                        </div>

                                        {/* Threshold Slider */}
                                        <div>
                                            <div className="flex items-center justify-between mb-1">
                                                <label htmlFor="mask-threshold" className="text-slate-400">阈值</label>
                                                <span className="text-slate-300 font-mono text-[10px]">{maskThreshold}</span>
                                            </div>
                                            <input
                                                type="range"
                                                id="mask-threshold"
                                                min="10"
                                                max="200"
                                                step="5"
                                                value={maskThreshold}
                                                onChange={(e) => {
                                                  const value = parseInt(e.target.value);
                                                  if (!isNaN(value)) {
                                                    setMaskThreshold(Math.max(10, Math.min(200, value)));
                                                  }
                                                }}
                                                className="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer accent-rose-500"
                                            />
                                            <p className="text-[10px] text-slate-500 mt-1">控制像素被识别为掩码的敏感度。</p>
                                        </div>

                                        {/* Generate Mask Button */}
                                        <button
                                            onClick={handleGenerateMaskPreview}
                                            disabled={isGeneratingMask}
                                            className="w-full bg-rose-700/50 hover:bg-rose-700 text-white rounded-md px-3 py-2 text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-2"
                                        >
                                            {isGeneratingMask ? '生成中...' : '重新生成掩码'}
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Main Image Display */}
                    <div className="flex-1 flex items-center justify-center p-0 w-full h-full">
                        {loadingState !== 'idle' ? (
                            <div className="flex flex-col items-center gap-4 pointer-events-none">
                                <div className="relative">
                                    <div className="w-20 h-20 border-4 border-rose-500/30 border-t-rose-500 rounded-full animate-spin"></div>
                                </div>
                                <p className="text-slate-400 animate-pulse">Processing Try-On...</p>
                            </div>
                        ) : isCompareMode && originalImageUrl && activeImageUrl ? (
                            <div
                                className="relative shadow-2xl transition-transform duration-75 ease-out"
                                style={canvas.canvasStyle}
                            >
                                <ImageCompare
                                    beforeImage={originalImageUrl}
                                    afterImage={activeImageUrl}
                                    beforeLabel="原图"
                                    afterLabel="试衣结果"
                                    accentColor="pink"
                                    className="max-w-none rounded-lg border border-slate-800"
                                    style={{ maxHeight: '80vh', maxWidth: '80vw' }}
                                />
                            </div>
                        ) : activeImageUrl ? (
                            <div
                                className="relative shadow-2xl group transition-transform duration-75 ease-out"
                                style={canvas.canvasStyle}
                            >
                                <img
                                    src={activeImageUrl}
                                    className="max-w-none rounded-lg border border-slate-800 pointer-events-none"
                                    style={{ maxHeight: '80vh', maxWidth: '80vw' }}
                                    alt="Main Canvas"
                                />
                                {/* Mask Preview Overlay */}
                                {showMaskPreview && maskPreviewUrl && (
                                    <div className="absolute inset-0 pointer-events-none">
                                        <img
                                            src={maskPreviewUrl}
                                            className="max-w-none rounded-lg opacity-50 mix-blend-multiply"
                                            style={{ maxHeight: '80vh', maxWidth: '80vw', filter: 'hue-rotate(330deg)' }}
                                            alt="Mask Preview"
                                        />
                                        <div className="absolute top-4 left-4 bg-black/60 text-white px-3 py-1 rounded-full text-xs">
                                            红色区域将被替换
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
                                <Shirt size={48} className="opacity-20" />
                                <div>
                                    <h3 className="text-xl font-bold text-slate-500 mb-2">Virtual Try-On</h3>
                                    <p className="text-sm opacity-60 mb-4">
                                        上传人物照片，描述想要的服装，AI 将为您虚拟试衣
                                    </p>
                                    <div className="grid grid-cols-2 gap-2 text-left text-xs opacity-50">
                                        <div className="flex items-center gap-2"><Sparkles size={12} /> 上衣替换</div>
                                        <div className="flex items-center gap-2"><Sparkles size={12} /> 下装替换</div>
                                        <div className="flex items-center gap-2"><Sparkles size={12} /> 全身换装</div>
                                        <div className="flex items-center gap-2"><Sparkles size={12} /> 风格转换</div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* 浮动控制按钮 */}
                    {activeImageUrl && (
                        <div className="absolute bottom-6 right-6 z-20">
                            <ImageCanvasControls
                                zoom={canvas.zoom}
                                onZoomIn={canvas.handleZoomIn}
                                onZoomOut={canvas.handleZoomOut}
                                onReset={canvas.handleReset}
                                onFullscreen={() => onImageClick(activeImageUrl)}
                                downloadUrl={activeImageUrl}
                                onToggleCompare={originalImageUrl ? () => setIsCompareMode(!isCompareMode) : undefined}
                                isCompareMode={isCompareMode}
                                accentColor="pink"
                            />
                        </div>
                    )}
                </div>
    ), [loadingState, isCompareMode, originalImageUrl, activeImageUrl, canvas.canvasStyle, canvas.zoom, canvas.handleZoomIn, canvas.handleZoomOut, canvas.handleReset, onImageClick, showMaskPreview, maskPreviewUrl, enableUpscale, upscaleFactor, addWatermark, isGeneratingMask, handleGenerateMaskPreview, maskAlpha, maskThreshold, currentTryOnTarget]);

    // 缓存 bottomContent
    const bottomContent = useMemo(() => (
                <InputArea
                    onSend={handleSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop}
                    currentModel={activeModelConfig}
                    visibleModels={visibleModels}
                    mode="virtual-try-on"
                    setMode={setAppMode}
                    initialPrompt={initialPrompt}
                    activeAttachments={activeAttachments}
                    onAttachmentsChange={setActiveAttachments}
                    providerId={providerId}
                />
    ), [handleSend, loadingState, onStop, activeModelConfig, visibleModels, setAppMode, initialPrompt, activeAttachments, providerId]);

    return (
        <GenViewLayout
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            sidebarTitle="History"
            sidebarHeaderIcon={<Layers size={14} />}
            sidebar={sidebarContent}
            main={mainContent}
            bottom={bottomContent}
        />
    );
};

export default VirtualTryOnView;
