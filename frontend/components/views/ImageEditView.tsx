
import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../../types';
import { Crop, Wand2, AlertCircle, Layers, User, Bot, Sparkles, Palette, PenTool, History, X } from 'lucide-react';
import { v4 as uuidv4 } from 'uuid';
import InputArea from '../chat/InputArea';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import { ImageCompare } from '../common/ImageCompare';
import { GenViewLayout } from '../common/GenViewLayout';

interface ImageEditViewProps {
    messages: Message[];
    setAppMode: (mode: AppMode) => void;
    onImageClick: (url: string) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    initialPrompt?: string;
    initialAttachments?: Attachment[];
    onExpandImage?: (url: string) => void; // Added prop
    providerId?: string;
    sessionId?: string | null;  // ✅ 会话 ID，用于查询附件
}

export const ImageEditView: React.FC<ImageEditViewProps> = ({
    messages,
    setAppMode,
    onImageClick,
    loadingState,
    onSend,
    onStop,
    activeModelConfig,
    initialPrompt,
    initialAttachments,
    onExpandImage,
    providerId,
    sessionId: currentSessionId  // ✅ 接收 sessionId
}) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    // State for reference image
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
    const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);

    // Track last processed message to auto-update view
    const [lastProcessedMsgId, setLastProcessedMsgId] = useState<string | null>(null);

    // 对比模式状态
    const [isCompareMode, setIsCompareMode] = useState(false);

    // Pan & Zoom Hook（替代原有的手动状态管理）
    const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });

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

    // Auto-select latest result logic
    useEffect(() => {
        // 1. Initial Load: If no active image, pick latest from history
        if (activeAttachments.length === 0 && !activeImageUrl) {
            const lastModelMsg = [...messages].reverse().find(m => m.role === Role.MODEL && m.attachments?.length);
            if (lastModelMsg && lastModelMsg.attachments?.[0]?.url) {
                setActiveImageUrl(lastModelMsg.attachments[0].url);
            }
        }

        // 2. New Generation Complete: Auto-switch to result
        if (loadingState === 'idle' && messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            // Check if this is a new message we haven't handled yet
            if (lastMsg.id !== lastProcessedMsgId) {
                // If it's a model response with an image
                if (lastMsg.role === Role.MODEL && lastMsg.attachments && lastMsg.attachments.length > 0 && lastMsg.attachments[0].url) {
                    setActiveImageUrl(lastMsg.attachments[0].url);
                    setLastProcessedMsgId(lastMsg.id);
                } else if (lastMsg.isError) {
                    // Just mark processed so we don't check again
                    setLastProcessedMsgId(lastMsg.id);
                }
            }
        }
    }, [messages, activeAttachments.length, loadingState, lastProcessedMsgId, activeImageUrl]);

    /**
     * 从历史消息中查找当前 activeImageUrl 对应的附件
     * 用于复用已有附件信息，避免重复上传
     * 返回附件信息和所属消息 ID
     */
    const findAttachmentFromHistory = (targetUrl: string): { attachment: Attachment; messageId: string } | null => {
        for (const msg of [...messages].reverse()) {
            for (const att of msg.attachments || []) {
                // 匹配 url 或 tempUrl
                if (att.url === targetUrl || att.tempUrl === targetUrl) {
                    console.log('[findAttachmentFromHistory] ✅ 找到匹配的附件:', {
                        id: att.id,
                        messageId: msg.id,
                        url: att.url?.substring(0, 60),
                        uploadStatus: att.uploadStatus
                    });
                    return { attachment: att, messageId: msg.id };
                }
            }
        }
        console.log('[findAttachmentFromHistory] ❌ 未找到匹配的附件');
        return null;
    };

    /**
     * 从后端查询附件的最新信息（包括云存储 URL）
     * 用于获取 Base64 对应的云存储 URL
     */
    const fetchAttachmentFromBackend = async (sessionId: string, attachmentId: string): Promise<{
        url: string;
        uploadStatus: string;
        taskId?: string;
    } | null> => {
        try {
            console.log('[fetchAttachmentFromBackend] 查询附件:', attachmentId);
            const response = await fetch(`/api/sessions/${sessionId}/attachments/${attachmentId}`);
            if (!response.ok) {
                console.log('[fetchAttachmentFromBackend] 查询失败:', response.status);
                return null;
            }
            const data = await response.json();
            console.log('[fetchAttachmentFromBackend] 查询结果:', {
                url: data.url?.substring(0, 60),
                uploadStatus: data.uploadStatus,
                taskId: data.taskId
            });
            return data;
        } catch (e) {
            console.error('[fetchAttachmentFromBackend] 查询异常:', e);
            return null;
        }
    };

    const handleSend = async (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
        console.log('========== [ImageEditView] handleSend 开始 ==========');
        console.log('[handleSend] 用户输入:', text);
        console.log('[handleSend] 用户上传的附件数量:', attachments.length);
        console.log('[handleSend] 当前 sessionId:', currentSessionId);  // ✅ 添加 sessionId 日志
        console.log('[handleSend] 当前 activeImageUrl:', activeImageUrl?.substring(0, 100) + '...');

        // 判断 activeImageUrl 的类型
        const isBase64 = activeImageUrl?.startsWith('data:');
        const isBlobUrl = activeImageUrl?.startsWith('blob:');
        const isCloudUrl = activeImageUrl?.startsWith('http://') || activeImageUrl?.startsWith('https://');
        console.log('[handleSend] activeImageUrl 类型:', isBase64 ? 'Base64' : isBlobUrl ? 'Blob URL' : isCloudUrl ? '云存储 URL' : '未知');

        let finalAttachments = [...attachments];

        // CONTINUITY LOGIC
        // 当用户没有上传新图片时，自动使用当前画布上的图片作为输入
        if (finalAttachments.length === 0 && activeImageUrl) {
            console.log('[handleSend] ✅ 触发 CONTINUITY LOGIC（用户未上传新图，使用画布图片）');

            try {
                // ===== 优先从历史消息中查找已有附件 =====
                const found = findAttachmentFromHistory(activeImageUrl);

                if (found) {
                    const { attachment: existingAttachment, messageId: _messageId } = found;
                    console.log('[handleSend] 复用历史附件模式, messageId:', _messageId);

                    let finalUrl = existingAttachment.url;
                    let finalUploadStatus = existingAttachment.uploadStatus || 'completed';

                    // ✅ 如果 uploadStatus 是 pending，查询后端获取最新 URL
                    console.log('[handleSend] 检查是否需要查询后端:', {
                        finalUploadStatus,
                        currentSessionId,
                        attachmentId: existingAttachment.id
                    });
                    if (finalUploadStatus === 'pending' && currentSessionId) {
                        console.log('[handleSend] 附件状态为 pending，查询后端获取最新 URL');
                        const backendData = await fetchAttachmentFromBackend(currentSessionId, existingAttachment.id);
                        if (backendData && backendData.url?.startsWith('http')) {
                            console.log('[handleSend] ✅ 从后端获取到云存储 URL:', backendData.url.substring(0, 60));
                            finalUrl = backendData.url;
                            finalUploadStatus = 'completed';
                        } else {
                            console.log('[handleSend] 后端尚未完成上传，继续使用 Base64');
                        }
                    }

                    const reusedAttachment: Attachment = {
                        id: uuidv4(),  // 新 ID，避免冲突
                        mimeType: existingAttachment.mimeType || 'image/png',
                        name: existingAttachment.name || `canvas-${Date.now()}.png`,
                        url: finalUrl,  // ✅ 使用最新的 URL（可能是云存储 URL）
                        uploadStatus: finalUploadStatus
                    };

                    // ✅ 获取 Base64 数据供 Google API 使用
                    // 优先使用当前 activeImageUrl（如果是 Base64），避免重复下载
                    if (isBase64 && activeImageUrl) {
                        // 原始 activeImageUrl 就是 Base64，直接使用
                        console.log('[handleSend] 原始图片是 Base64，直接使用（无需下载）');
                        (reusedAttachment as any).base64Data = activeImageUrl;
                    } else if (finalUrl?.startsWith('http')) {
                        // 原始图片不是 Base64，需要从云存储下载
                        console.log('[handleSend] 从云存储下载图片转 Base64');
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
                        // url 还是 Base64，直接使用
                        (reusedAttachment as any).base64Data = existingAttachment.url;
                    }

                    finalAttachments = [reusedAttachment];
                    console.log('[handleSend] ✅ 复用历史附件完成，uploadStatus:', reusedAttachment.uploadStatus, 'url 类型:', finalUrl?.startsWith('http') ? '云存储' : 'Base64');

                } else if (isCloudUrl) {
                    // ===== 情况 1：activeImageUrl 是云存储 URL（重载网页后） =====
                    console.log('[handleSend] 云存储 URL 模式：通过后端代理下载');
                    const fetchUrl = `/api/storage/download?url=${encodeURIComponent(activeImageUrl)}`;
                    const response = await fetch(fetchUrl);
                    const blob = await response.blob();
                    console.log('[handleSend] 图片下载完成, blob 大小:', blob.size, 'bytes');

                    const base64Url = await new Promise<string>((resolve) => {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result as string);
                        reader.readAsDataURL(blob);
                    });

                    const reusedAttachment: Attachment = {
                        id: uuidv4(),
                        mimeType: blob.type || 'image/png',
                        name: `canvas-${Date.now()}.png`,
                        url: activeImageUrl,  // ✅ 直接用云存储 URL
                        uploadStatus: 'completed'
                    };
                    (reusedAttachment as any).base64Data = base64Url;

                    finalAttachments = [reusedAttachment];
                    console.log('[handleSend] ✅ 云存储 URL 模式完成');

                } else if (isBase64 || isBlobUrl) {
                    // ===== 情况 2：activeImageUrl 是 Base64/Blob 但未在历史中找到 =====
                    // 这种情况理论上不应该发生，但作为兜底处理
                    console.log('[handleSend] Base64/Blob 兜底模式');

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
                        uploadStatus: 'completed'  // ✅ 不再触发上传，上一轮已处理
                    };
                    (reusedAttachment as any).base64Data = base64Url;

                    finalAttachments = [reusedAttachment];
                    console.log('[handleSend] ✅ Base64/Blob 兜底模式完成');
                }

            } catch (e) {
                console.error("[handleSend] ❌ CONTINUITY LOGIC 失败:", e);
            }
        } else {
            console.log('[handleSend] 未触发 CONTINUITY LOGIC，原因:',
                finalAttachments.length > 0 ? '用户已上传新图片' : '画布无图片'
            );
        }

        console.log('[handleSend] 最终附件数量:', finalAttachments.length);
        if (finalAttachments.length > 0) {
            console.log('[handleSend] 最终附件详情:', finalAttachments.map(att => ({
                id: att.id,
                name: att.name,
                urlType: att.url?.startsWith('data:') ? 'Base64' :
                    att.url?.startsWith('blob:') ? 'Blob URL' :
                        att.url?.startsWith('http') ? '云存储 URL' : '其他',
                hasBase64Data: !!(att as any).base64Data,
                uploadStatus: att.uploadStatus
            })));
        }
        console.log('========== [ImageEditView] handleSend 结束，调用 onSend ==========');
        onSend(text, options, finalAttachments, mode);
    };

    // Canvas 事件处理器现在由 useImageCanvas Hook 提供

    // Mobile History Toggle
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

    return (
        <GenViewLayout
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            sidebarTitle="History"
            sidebarHeaderIcon={<Layers size={14} />}
            sidebarContent={
                <div className="flex-1 p-4 space-y-6">
                    {messages.map((msg) => {
                        // Filter out empty placeholders to prevent "Double Bubble" issue
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
                                            className={`relative group mt-1 rounded-lg overflow-hidden border cursor-pointer transition-all ${activeImageUrl === att.url ? 'ring-2 ring-pink-500 border-transparent' : 'border-slate-700 hover:border-slate-500'
                                                }`}
                                        >
                                            <img src={att.url} className="w-full h-32 object-cover bg-slate-900" alt="thumbnail" />
                                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                                                {activeImageUrl === att.url && <div className="bg-pink-500 w-2 h-2 rounded-full absolute top-2 right-2 shadow-sm" />}
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
                            <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400">Processing request...</div>
                        </div>
                    )}
                    {/* Dummy div for scroll ref */}
                    <div ref={scrollRef} />
                </div>
            }
            mainContent={
                // RIGHT MAIN: Result / Canvas
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
                            <Wand2 size={12} className="text-pink-400" />
                            {isCompareMode ? '对比模式' : activeAttachments.length > 0 && activeImageUrl === activeAttachments[0].url ? 'Source Preview' : 'Workspace'}
                            <span className="opacity-50">|</span>
                            <span className="font-mono text-[10px] opacity-70">{Math.round(canvas.zoom * 100)}%</span>
                        </div>
                    </div>

                    {/* Main Image Display with Transformations */}
                    <div className="flex-1 flex items-center justify-center p-0 w-full h-full">
                        {loadingState !== 'idle' ? (
                            <div className="flex flex-col items-center gap-4 pointer-events-none">
                                <div className="relative">
                                    <div className="w-20 h-20 border-4 border-pink-500/30 border-t-pink-500 rounded-full animate-spin"></div>
                                </div>
                                <p className="text-slate-400 animate-pulse">Processing Image...</p>
                            </div>
                        ) : isCompareMode && originalImageUrl && activeImageUrl ? (
                            // 对比模式
                            <div
                                className="relative shadow-2xl transition-transform duration-75 ease-out"
                                style={canvas.canvasStyle}
                            >
                                <ImageCompare
                                    beforeImage={originalImageUrl}
                                    afterImage={activeImageUrl}
                                    beforeLabel="原图"
                                    afterLabel="编辑结果"
                                    accentColor="pink"
                                    className="max-w-none rounded-lg border border-slate-800"
                                    style={{ maxHeight: '80vh', maxWidth: '80vw' }}
                                />
                            </div>
                        ) : activeImageUrl ? (
                            // 普通模式
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
                            </div>
                        ) : (
                            <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
                                <Crop size={48} className="opacity-20" />
                                <div>
                                    <h3 className="text-xl font-bold text-slate-500 mb-2">Editor Workspace</h3>
                                    <p className="text-sm opacity-60 mb-4">
                                        Attach an image below to start. Gemini allows advanced conversational editing:
                                    </p>
                                    <div className="grid grid-cols-2 gap-2 text-left text-xs opacity-50">
                                        <div className="flex items-center gap-2"><Palette size={12} /> Style Transfer</div>
                                        <div className="flex items-center gap-2"><Sparkles size={12} /> Inpainting/Replacing</div>
                                        <div className="flex items-center gap-2"><PenTool size={12} /> Sketch to Image</div>
                                        <div className="flex items-center gap-2"><Layers size={12} /> Composition</div>
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
                                onExpand={onExpandImage ? () => onExpandImage(activeImageUrl) : undefined}
                                onToggleCompare={originalImageUrl ? () => setIsCompareMode(!isCompareMode) : undefined}
                                isCompareMode={isCompareMode}
                                accentColor="pink"
                            />
                        </div>
                    )}
                </div>
            }
            bottomContent={
                <InputArea
                    onSend={handleSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop}
                    currentModel={activeModelConfig}
                    mode="image-edit"
                    setMode={setAppMode}
                    initialPrompt={initialPrompt}
                    // Sync State
                    activeAttachments={activeAttachments}
                    onAttachmentsChange={setActiveAttachments}
                    providerId={providerId}
                />
            }
        />
    );
};
