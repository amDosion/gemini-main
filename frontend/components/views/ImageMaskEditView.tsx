
import React, { useState, useRef, useEffect, useMemo, useCallback, memo } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Crop, AlertCircle, Layers, User, Bot, Sparkles, SlidersHorizontal, RotateCcw, Wand2, Upload, Square, Pencil, Eraser, Trash2, ChevronDown, Move, FlipVertical2, Loader2 } from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import { ImageCompare } from '../common/ImageCompare';
import { GenViewLayout } from '../common/GenViewLayout';
import { ThinkingBlock } from '../message/ThinkingBlock';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../chat/ChatEditInputArea';
import { apiClient } from '../../services/apiClient';

interface ImageMaskEditViewProps {
    messages: Message[];
    setAppMode: (mode: AppMode) => void;
    onImageClick: (url: string) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    visibleModels?: ModelConfig[];
    allVisibleModels?: ModelConfig[];  // 新增：完整模型列表
    initialPrompt?: string;
    initialAttachments?: Attachment[];
    onExpandImage?: (url: string) => void;
    providerId?: string;
    sessionId?: string | null;
}

// 复用 ImageEditView 的比较函数
const arePropsEqual = (prevProps: ImageMaskEditViewProps, nextProps: ImageMaskEditViewProps) => {
    if (prevProps.activeModelConfig?.id !== nextProps.activeModelConfig?.id) {
        return false;
    }
    if (prevProps.loadingState !== nextProps.loadingState) return false;
    if (prevProps.messages !== nextProps.messages) return false;
    if (prevProps.sessionId !== nextProps.sessionId) return false;
    if (prevProps.providerId !== nextProps.providerId) return false;
    return true;
};

// Mask 工具类型（增加 move 用于拖动图片）
type MaskTool = 'move' | 'select' | 'brush' | 'eraser';

// Mask 模式（对应 Vertex AI MaskReferenceConfig.mask_mode）
type MaskMode =
    | 'MASK_MODE_USER_PROVIDED'  // 用户提供遮罩（手动绘制）
    | 'MASK_MODE_BACKGROUND'     // 自动检测背景
    | 'MASK_MODE_FOREGROUND'     // 自动检测前景
    | 'MASK_MODE_SEMANTIC';      // 语义分割（人物等）

// 选区矩形类型
interface SelectionRect {
    startX: number;
    startY: number;
    endX: number;
    endY: number;
}

// 复用 ImageEditMainCanvas 组件（从 ImageEditView 导入或复制）
type ImageEditMainCanvasProps = {
    loadingState: string;
    isCompareMode: boolean;
    activeAttachments: Attachment[];
    activeImageUrl: string | null;
    originalImageUrl: string | null;
    zoom: number;
    isDragging: boolean;
    canvasStyle: React.CSSProperties;
    onWheel: (e: React.WheelEvent) => void;
    onMouseDown: (e: React.MouseEvent) => void;
    onMouseMove: (e: React.MouseEvent) => void;
    onMouseUp: () => void;
    onZoomIn: (e?: React.MouseEvent) => void;
    onZoomOut: (e?: React.MouseEvent) => void;
    onReset: (e?: React.MouseEvent) => void;
    onFullscreen?: () => void;
    onExpand?: () => void;
    onToggleCompare?: () => void;
    // ✅ Mask 工具栏支持
    activeMaskTool: MaskTool;
    onMaskToolChange: (tool: MaskTool) => void;
    brushSize: number;
    onBrushSizeChange: (size: number) => void;
    // ✅ Mask 自动提取模式（Vertex AI mask_mode）
    maskMode: MaskMode;
    onMaskModeChange: (mode: MaskMode) => void;
    onImportMask?: () => void;
    onClearMask?: () => void;
    isPreviewingMask?: boolean; // 正在加载自动 mask 预览
    // ✅ Mask 反转（前景/背景切换）
    isMaskInverted: boolean;
    onToggleMaskInvert: () => void;
    // ✅ 选区和 Mask 预览支持（支持多个矩形）
    selectionRects: SelectionRect[];
    currentSelectionRect: SelectionRect | null;
    isSelecting: boolean;
    onSelectionStart: (e: React.MouseEvent) => void;
    onSelectionMove: (e: React.MouseEvent) => void;
    onSelectionEnd: () => void;
    onDeleteSelection: (index: number) => void;
    maskPreviewUrl: string | null;
    imageRef: React.RefObject<HTMLImageElement>;
    // ✅ 画笔/橡皮擦绑定支持
    onBrushStart: (e: React.MouseEvent) => void;
    onBrushMove: (e: React.MouseEvent) => void;
    onBrushEnd: () => void;
    isPainting: boolean;
    // ✅ 画笔绘制的 mask canvas URL
    maskCanvasUrl: string | null;
    // ✅ 画笔光标 ref（直接 DOM 更新，避免 React 重渲染）
    brushCursorRef: React.RefObject<HTMLDivElement | null>;
    onBrushCursorMove: (pos: { x: number; y: number } | null) => void;
    // ✅ 实时绘制的 mask canvas 引用（用于绘制过程中实时显示）
    maskCanvasRef: React.RefObject<HTMLCanvasElement | null>;
    // ✅ 显示用的 canvas ref（用于直接 DOM 更新，避免 React 重渲染）
    displayCanvasRef: React.RefObject<HTMLCanvasElement | null>;
};

const ImageEditMainCanvas = memo(({
    loadingState,
    isCompareMode,
    activeAttachments,
    activeImageUrl,
    originalImageUrl,
    zoom,
    isDragging,
    canvasStyle,
    onWheel,
    onMouseDown,
    onMouseMove,
    onMouseUp,
    onZoomIn,
    onZoomOut,
    onReset,
    onFullscreen,
    onExpand,
    onToggleCompare,
    // ✅ Mask 工具栏
    activeMaskTool,
    onMaskToolChange,
    brushSize,
    onBrushSizeChange,
    // ✅ Mask 自动提取模式
    maskMode,
    onMaskModeChange,
    onImportMask,
    onClearMask,
    isPreviewingMask,
    // ✅ Mask 反转
    isMaskInverted,
    onToggleMaskInvert,
    // ✅ 选区和 Mask 预览（支持多个矩形）
    selectionRects,
    currentSelectionRect,
    isSelecting,
    onSelectionStart,
    onSelectionMove,
    onSelectionEnd,
    onDeleteSelection,
    maskPreviewUrl,
    imageRef,
    // ✅ 画笔/橡皮擦
    onBrushStart,
    onBrushMove,
    onBrushEnd,
    isPainting,
    // ✅ 画笔绘制的 mask
    maskCanvasUrl,
    // ✅ 画笔光标 ref
    brushCursorRef,
    onBrushCursorMove,
    // ✅ 实时绘制的 mask canvas
    maskCanvasRef,
    // ✅ 显示用的 canvas ref
    displayCanvasRef,
}: ImageEditMainCanvasProps) => {
    // 根据当前工具设置光标样式
    const cursor = useMemo(() => {
        if (isCompareMode) return 'default';
        if (!activeImageUrl) return 'default';

        switch (activeMaskTool) {
            case 'move':
                return isDragging ? 'grabbing' : 'grab';
            case 'brush':
            case 'eraser':
            case 'select':
            default:
                return 'crosshair';
        }
    }, [isCompareMode, activeImageUrl, activeMaskTool, isDragging]);

    // Extract mask 下拉菜单状态
    const [isExtractMenuOpen, setIsExtractMenuOpen] = useState(false);

    return (
        <div
            className="flex-1 w-full h-full select-none flex flex-col relative"
            onWheel={isCompareMode ? undefined : onWheel}
            onMouseDown={isCompareMode || activeMaskTool !== 'move' ? undefined : onMouseDown}
            onMouseMove={isCompareMode || activeMaskTool !== 'move' ? undefined : onMouseMove}
            onMouseUp={isCompareMode || activeMaskTool !== 'move' ? undefined : onMouseUp}
            onMouseLeave={isCompareMode || activeMaskTool !== 'move' ? undefined : onMouseUp}
            style={{ cursor }}
        >
            {/* Checkerboard Background */}
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
                    <Crop size={12} className="text-purple-400" />
                    {isCompareMode
                        ? '对比模式'
                        : activeAttachments.length > 0 && activeImageUrl === activeAttachments[0].url
                            ? 'Source Preview'
                            : 'Mask Editor'}
                    <span className="opacity-50">|</span>
                    <span className="font-mono text-[10px] opacity-70">{Math.round(zoom * 100)}%</span>
                </div>
            </div>

            {/* Main Image Display */}
            <div className="flex-1 flex items-center justify-center p-0 w-full h-full relative">
                {loadingState !== 'idle' ? (() => {
                    let statusText = 'Processing Image...';
                    if (loadingState === 'uploading') {
                        statusText = '上传图片中...';
                    } else if (loadingState === 'loading') {
                        statusText = 'Mask 编辑中，正在处理遮罩区域...';
                    } else if (loadingState === 'streaming') {
                        statusText = '流式处理中...';
                    }

                    return (
                        <div className="flex flex-col items-center gap-4 pointer-events-none">
                            <div className="relative">
                                <div className="w-20 h-20 border-4 border-purple-500/30 border-t-purple-500 rounded-full animate-spin"></div>
                            </div>
                            <p className="text-slate-400 animate-pulse">{statusText}</p>
                        </div>
                    );
                })() : isCompareMode && originalImageUrl && activeImageUrl ? (
                    <div className="relative shadow-2xl transition-transform duration-75 ease-out" style={canvasStyle}>
                        <ImageCompare
                            beforeImage={originalImageUrl}
                            afterImage={activeImageUrl}
                            beforeLabel="原图"
                            afterLabel="Mask 编辑结果"
                            accentColor="indigo"
                            className="max-w-none rounded-lg border border-slate-800"
                            style={{ maxHeight: '80vh', maxWidth: '80vw' }}
                        />
                    </div>
                ) : activeImageUrl ? (
                    <div
                        className="relative shadow-2xl group transition-transform duration-75 ease-out"
                        style={canvasStyle}
                    >
                        <img
                            ref={imageRef}
                            src={activeImageUrl}
                            className="max-w-none rounded-lg border border-slate-800"
                            style={{ maxHeight: '80vh', maxWidth: '80vw' }}
                            alt="Main Canvas"
                        />
                        {/* ✅ Mask 可视化层 - 支持矩形选区和画笔绘制 */}
                        {(selectionRects.length > 0 || maskCanvasUrl) && (
                            <div className="absolute inset-0 rounded-lg pointer-events-none overflow-hidden">
                                {/* 画笔绘制的 mask 层 - 透明度与 mask box 一致 (0.3) */}
                                {/* 使用固定 canvas 元素，通过 ref 直接更新，避免 React 重渲染 */}
                                <canvas
                                    ref={displayCanvasRef}
                                    className="absolute inset-0 w-full h-full"
                                    style={{
                                        opacity: isMaskInverted ? 0 : 0.3,
                                        display: (isPainting || maskCanvasUrl) ? 'block' : 'none'
                                    }}
                                />
                                {isMaskInverted ? (
                                    /* 反转模式：外部蓝色，使用 SVG mask 实现 */
                                    <svg className="absolute inset-0 w-full h-full">
                                        <defs>
                                            <mask id="invertMask">
                                                {/* 白色背景 = 可见 */}
                                                <rect x="0" y="0" width="100%" height="100%" fill="white" />
                                                {/* 黑色矩形 = 透明（挖洞） */}
                                                {selectionRects.map((rect, index) => (
                                                    <rect
                                                        key={index}
                                                        x={Math.min(rect.startX, rect.endX)}
                                                        y={Math.min(rect.startY, rect.endY)}
                                                        width={Math.abs(rect.endX - rect.startX)}
                                                        height={Math.abs(rect.endY - rect.startY)}
                                                        fill="black"
                                                    />
                                                ))}
                                            </mask>
                                        </defs>
                                        {/* 蓝色遮罩层，应用 mask */}
                                        <rect
                                            x="0" y="0"
                                            width="100%" height="100%"
                                            fill="rgba(59, 130, 246, 0.3)"
                                            mask="url(#invertMask)"
                                        />
                                        {/* 矩形边框 */}
                                        {selectionRects.map((rect, index) => (
                                            <rect
                                                key={`border-${index}`}
                                                x={Math.min(rect.startX, rect.endX)}
                                                y={Math.min(rect.startY, rect.endY)}
                                                width={Math.abs(rect.endX - rect.startX)}
                                                height={Math.abs(rect.endY - rect.startY)}
                                                fill="none"
                                                stroke="#3b82f6"
                                                strokeWidth="2"
                                            />
                                        ))}
                                    </svg>
                                ) : (
                                    /* 正常模式：内部蓝色 */
                                    selectionRects.map((rect, index) => (
                                        <div
                                            key={index}
                                            className="absolute"
                                            style={{
                                                left: Math.min(rect.startX, rect.endX),
                                                top: Math.min(rect.startY, rect.endY),
                                                width: Math.abs(rect.endX - rect.startX),
                                                height: Math.abs(rect.endY - rect.startY),
                                                border: '2px solid #3b82f6',
                                                backgroundColor: 'rgba(59, 130, 246, 0.3)',
                                            }}
                                        />
                                    ))
                                )}
                            </div>
                        )}
                        {/* ✅ 选区绘制交互层 - 仅在 select 工具激活时启用 */}
                        {activeMaskTool === 'select' && (
                            <div
                                className="absolute inset-0 rounded-lg"
                                style={{ cursor: 'crosshair' }}
                                onMouseDown={onSelectionStart}
                                onMouseMove={onSelectionMove}
                                onMouseUp={onSelectionEnd}
                                onMouseLeave={onSelectionEnd}
                            >
                                {/* 当前正在绘制的选区 */}
                                {currentSelectionRect && (
                                    <div
                                        className="absolute"
                                        style={{
                                            left: Math.min(currentSelectionRect.startX, currentSelectionRect.endX),
                                            top: Math.min(currentSelectionRect.startY, currentSelectionRect.endY),
                                            width: Math.abs(currentSelectionRect.endX - currentSelectionRect.startX),
                                            height: Math.abs(currentSelectionRect.endY - currentSelectionRect.startY),
                                            border: '2px dashed #60a5fa',
                                            backgroundColor: 'rgba(96, 165, 250, 0.2)',
                                        }}
                                    />
                                )}
                            </div>
                        )}
                        {/* ✅ 画笔/橡皮擦交互层 */}
                        {(activeMaskTool === 'brush' || activeMaskTool === 'eraser') && (
                            <div
                                className="absolute inset-0 rounded-lg"
                                style={{ cursor: 'none' }} // 隐藏默认光标
                                onMouseDown={onBrushStart}
                                onMouseMove={(e) => {
                                    // 更新光标位置（需要除以 zoom 以匹配缩放后的坐标系）
                                    const rect = e.currentTarget.getBoundingClientRect();
                                    onBrushCursorMove({
                                        x: (e.clientX - rect.left) / zoom,
                                        y: (e.clientY - rect.top) / zoom
                                    });
                                    // 调用原有的绘制逻辑
                                    onBrushMove(e);
                                }}
                                onMouseUp={onBrushEnd}
                                onMouseLeave={() => {
                                    onBrushCursorMove(null); // 鼠标离开时隐藏光标
                                    onBrushEnd();
                                }}
                                onMouseEnter={(e) => {
                                    // 鼠标进入时显示光标（需要除以 zoom）
                                    const rect = e.currentTarget.getBoundingClientRect();
                                    onBrushCursorMove({
                                        x: (e.clientX - rect.left) / zoom,
                                        y: (e.clientY - rect.top) / zoom
                                    });
                                }}
                            >
                                {/* 自定义圆形光标 - 使用 ref 直接 DOM 更新，避免 React 重渲染 */}
                                <div
                                    ref={brushCursorRef}
                                    className="pointer-events-none absolute rounded-full border-2"
                                    style={{
                                        display: 'none', // 初始隐藏，由 handleBrushCursorMove 控制
                                        width: brushSize,
                                        height: brushSize,
                                        borderColor: activeMaskTool === 'eraser' ? '#f87171' : '#3b82f6',
                                        backgroundColor: activeMaskTool === 'eraser'
                                            ? 'rgba(248, 113, 113, 0.2)'
                                            : 'rgba(59, 130, 246, 0.2)',
                                    }}
                                />
                            </div>
                        )}
                        {/* ✅ 序号圆点/撤销按钮 - 放在所有交互层之后，确保可点击 */}
                        {selectionRects.length > 0 && selectionRects.map((rect, index) => (
                            <button
                                key={`btn-${index}`}
                                onMouseDown={(e) => {
                                    e.stopPropagation();
                                    e.preventDefault();
                                }}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onDeleteSelection(index);
                                }}
                                className="absolute w-5 h-5 bg-blue-500 hover:bg-red-500 rounded-full flex items-center justify-center text-[10px] text-white font-bold cursor-pointer transition-colors z-30"
                                style={{
                                    left: Math.min(rect.startX, rect.endX) - 10,
                                    top: Math.min(rect.startY, rect.endY) - 10,
                                }}
                                title="点击撤销此选区"
                            >
                                {index + 1}
                            </button>
                        ))}
                    </div>
                ) : (
                    <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
                        <Crop size={48} className="opacity-20" />
                        <div>
                            <h3 className="text-xl font-bold text-slate-500 mb-2">Mask Editor</h3>
                            <p className="text-sm opacity-60">
                                上传图片并指定遮罩区域进行编辑
                            </p>
                        </div>
                    </div>
                )}

                {/* ✅ Mask 工具栏 - 底部居中（始终显示，不依赖图片） */}
                {loadingState === 'idle' && (
                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20">
                        <div className="flex items-center gap-1 py-2 px-3 bg-slate-800/95 backdrop-blur-md rounded-xl border border-slate-700/50 shadow-xl">
                            {/* Extract mask 下拉按钮 - 对应 Vertex AI MaskReferenceConfig.mask_mode */}
                            <div className="relative">
                                <button
                                    onClick={() => setIsExtractMenuOpen(!isExtractMenuOpen)}
                                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                                        maskMode !== 'MASK_MODE_USER_PROVIDED'
                                            ? 'bg-purple-500/20 text-purple-400'
                                            : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
                                    }`}
                                >
                                    {isPreviewingMask ? (
                                        <Loader2 size={14} className="animate-spin text-purple-400" />
                                    ) : (
                                        <Wand2 size={14} className={maskMode !== 'MASK_MODE_USER_PROVIDED' ? 'text-purple-400' : 'text-slate-400'} />
                                    )}
                                    <span>
                                        {isPreviewingMask ? 'Loading...' :
                                         maskMode === 'MASK_MODE_BACKGROUND' ? 'Background' :
                                         maskMode === 'MASK_MODE_FOREGROUND' ? 'Foreground' :
                                         maskMode === 'MASK_MODE_SEMANTIC' ? 'People' : 'Extract mask'}
                                    </span>
                                    <ChevronDown size={12} className={`transition-transform ${isExtractMenuOpen ? 'rotate-180' : ''}`} />
                                </button>
                                {/* 下拉菜单 */}
                                {isExtractMenuOpen && (
                                    <div className="absolute bottom-full left-0 mb-2 py-1 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-30 min-w-[220px]">
                                        {/* Background 选项 */}
                                        <button
                                            onClick={() => { onMaskModeChange('MASK_MODE_BACKGROUND'); setIsExtractMenuOpen(false); }}
                                            className={`w-full px-3 py-2.5 text-left text-xs transition-colors flex items-center gap-2.5 whitespace-nowrap ${
                                                maskMode === 'MASK_MODE_BACKGROUND'
                                                    ? 'bg-purple-500/20 text-purple-400'
                                                    : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                                            }`}
                                        >
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="flex-shrink-0">
                                                <rect x="3" y="3" width="18" height="18" rx="2" />
                                                <path d="M3 15l4-4 4 4 6-6 4 4" />
                                                <circle cx="8" cy="9" r="2" />
                                            </svg>
                                            Background (自动背景)
                                            {maskMode === 'MASK_MODE_BACKGROUND' && <span className="ml-auto text-purple-400">✓</span>}
                                        </button>
                                        {/* Foreground 选项 */}
                                        <button
                                            onClick={() => { onMaskModeChange('MASK_MODE_FOREGROUND'); setIsExtractMenuOpen(false); }}
                                            className={`w-full px-3 py-2.5 text-left text-xs transition-colors flex items-center gap-2.5 whitespace-nowrap ${
                                                maskMode === 'MASK_MODE_FOREGROUND'
                                                    ? 'bg-purple-500/20 text-purple-400'
                                                    : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                                            }`}
                                        >
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="flex-shrink-0">
                                                <rect x="3" y="3" width="18" height="18" rx="2" strokeDasharray="4 2" />
                                                <rect x="7" y="7" width="10" height="10" rx="1" />
                                            </svg>
                                            Foreground (自动前景)
                                            {maskMode === 'MASK_MODE_FOREGROUND' && <span className="ml-auto text-purple-400">✓</span>}
                                        </button>
                                        {/* Semantic/People 选项 */}
                                        <button
                                            onClick={() => { onMaskModeChange('MASK_MODE_SEMANTIC'); setIsExtractMenuOpen(false); }}
                                            className={`w-full px-3 py-2.5 text-left text-xs transition-colors flex items-center gap-2.5 whitespace-nowrap ${
                                                maskMode === 'MASK_MODE_SEMANTIC'
                                                    ? 'bg-purple-500/20 text-purple-400'
                                                    : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                                            }`}
                                        >
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="flex-shrink-0">
                                                <circle cx="12" cy="7" r="4" />
                                                <path d="M5 21c0-4 3-7 7-7s7 3 7 7" />
                                            </svg>
                                            People (人物分割)
                                            {maskMode === 'MASK_MODE_SEMANTIC' && <span className="ml-auto text-purple-400">✓</span>}
                                        </button>
                                        <div className="border-t border-slate-700 my-1" />
                                        {/* 清除自动提取 - 切换回手动模式 */}
                                        {maskMode !== 'MASK_MODE_USER_PROVIDED' && (
                                            <button
                                                onClick={() => { onMaskModeChange('MASK_MODE_USER_PROVIDED'); setIsExtractMenuOpen(false); }}
                                                className="w-full px-3 py-2.5 text-left text-xs text-slate-400 hover:bg-slate-700 hover:text-white transition-colors flex items-center gap-2.5 whitespace-nowrap"
                                            >
                                                <Trash2 size={14} className="flex-shrink-0" />
                                                清除自动提取 (切换手动)
                                            </button>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* 分隔线 */}
                            <div className="w-px h-6 bg-slate-600/50 mx-1" />

                            {/* Import mask */}
                            <button
                                onClick={onImportMask}
                                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
                            >
                                <Upload size={14} />
                                <span>Import mask</span>
                            </button>

                            {/* 分隔线 */}
                            <div className="w-px h-6 bg-slate-600/50 mx-1" />

                            {/* Edit mask 标签 */}
                            <span className="text-xs text-slate-500 px-2">Edit mask:</span>

                            {/* 移动/平移工具 */}
                            <button
                                onClick={() => onMaskToolChange('move')}
                                className={`p-2 rounded-lg transition-colors ${
                                    activeMaskTool === 'move'
                                        ? 'bg-purple-500/20 text-purple-400'
                                        : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                                }`}
                                title="移动/平移图片"
                            >
                                <Move size={16} />
                            </button>

                            {/* 矩形选择工具 */}
                            <button
                                onClick={() => onMaskToolChange('select')}
                                className={`p-2 rounded-lg transition-colors ${
                                    activeMaskTool === 'select'
                                        ? 'bg-purple-500/20 text-purple-400'
                                        : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                                }`}
                                title="矩形选择"
                            >
                                <Square size={16} />
                            </button>

                            {/* 画笔工具 */}
                            <button
                                onClick={() => onMaskToolChange('brush')}
                                className={`p-2 rounded-lg transition-colors ${
                                    activeMaskTool === 'brush'
                                        ? 'bg-purple-500/20 text-purple-400'
                                        : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                                }`}
                                title="画笔"
                            >
                                <Pencil size={16} />
                            </button>

                            {/* 橡皮擦工具 */}
                            <button
                                onClick={() => onMaskToolChange('eraser')}
                                className={`p-2 rounded-lg transition-colors ${
                                    activeMaskTool === 'eraser'
                                        ? 'bg-purple-500/20 text-purple-400'
                                        : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                                }`}
                                title="橡皮擦"
                            >
                                <Eraser size={16} />
                            </button>

                            {/* 前景/背景切换 */}
                            <button
                                onClick={onToggleMaskInvert}
                                className={`p-2 rounded-lg transition-colors ${
                                    isMaskInverted
                                        ? 'bg-amber-500/20 text-amber-400'
                                        : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                                }`}
                                title={isMaskInverted ? '当前: 背景模式（点击切换到前景）' : '当前: 前景模式（点击切换到背景）'}
                            >
                                <FlipVertical2 size={16} />
                            </button>

                            {/* 分隔线 */}
                            <div className="w-px h-6 bg-slate-600/50 mx-1" />

                            {/* 画笔大小调节 */}
                            {(activeMaskTool === 'brush' || activeMaskTool === 'eraser') && (
                                <div className="flex items-center gap-2 px-2">
                                    <span className="text-xs text-slate-500">Size:</span>
                                    <input
                                        type="range"
                                        min="1"
                                        max="100"
                                        value={brushSize}
                                        onChange={(e) => onBrushSizeChange(Number(e.target.value))}
                                        className="w-20 h-1 bg-slate-600 rounded-lg appearance-none cursor-pointer accent-purple-500"
                                        title={`画笔大小: ${brushSize}px`}
                                    />
                                    <span className="text-xs text-slate-400 font-mono w-8">{brushSize}px</span>
                                </div>
                            )}

                            {/* 分隔线 */}
                            {(activeMaskTool === 'brush' || activeMaskTool === 'eraser') && (
                                <div className="w-px h-6 bg-slate-600/50 mx-1" />
                            )}

                            {/* 清除按钮 */}
                            <button
                                onClick={onClearMask}
                                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                                title="清除蒙版"
                            >
                                <Trash2 size={14} />
                                <span>Clear</span>
                            </button>
                        </div>
                    </div>
                )}

                {/* ✅ Mask 预览 - 画布右下角浮动显示 */}
                {maskPreviewUrl && (
                    <div className="absolute bottom-20 right-4 z-20">
                        <div className="bg-slate-800/95 backdrop-blur-md rounded-xl border border-slate-700/50 shadow-xl p-3">
                            <div className="text-xs text-slate-400 mb-2 font-medium">Mask Preview</div>
                            <div className="relative w-24 h-24 rounded-lg overflow-hidden border border-slate-600 bg-black">
                                <img
                                    src={maskPreviewUrl}
                                    alt="Mask Preview"
                                    className="w-full h-full object-contain"
                                />
                            </div>
                            <div className="text-[10px] text-slate-500 mt-2">
                                {selectionRects.length} 个选区
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Floating Controls */}
            {activeImageUrl && (
                <div className="absolute bottom-6 right-6 z-20">
                    <ImageCanvasControls
                        zoom={zoom}
                        onZoomIn={onZoomIn}
                        onZoomOut={onZoomOut}
                        onReset={onReset}
                        onFullscreen={onFullscreen}
                        downloadUrl={activeImageUrl}
                        onExpand={onExpand}
                        onToggleCompare={onToggleCompare}
                        isCompareMode={isCompareMode}
                        accentColor="indigo"
                    />
                </div>
            )}
        </div>
    );
});

ImageEditMainCanvas.displayName = 'ImageEditMainCanvas';

export const ImageMaskEditView = memo(({
    messages,
    setAppMode,
    onImageClick,
    loadingState,
    onSend,
    onStop,
    activeModelConfig,
    visibleModels = [],
    allVisibleModels = [],
    initialPrompt,
    initialAttachments,
    onExpandImage,
    providerId,
    sessionId: currentSessionId
}: ImageMaskEditViewProps) => {
    const { showError } = useToastContext();
    const scrollRef = useRef<HTMLDivElement>(null);

    // State for reference image
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
    const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);
    
    // 固定使用 image-mask-edit 模式
    const editMode: AppMode = 'image-mask-edit';
    
    // ✅ 参数面板状态
    const controls = useControlsState(editMode, activeModelConfig);

    // 重置参数（mask 编辑特有参数）
    const resetParams = useCallback(() => {
        controls.setEditMode('EDIT_MODE_INPAINT_INSERTION');
        controls.setMaskDilation(0.06);
        controls.setGuidanceScale(15.0);
        controls.setNumberOfImages(1);
        controls.setNegativePrompt('');
        controls.setOutputMimeType('image/png');
        controls.setOutputCompressionQuality(95);
    }, [controls]);
    
    // State for thinking block
    const [isThinkingOpen, setIsThinkingOpen] = useState(true);
    const [displayedThinkingContent, setDisplayedThinkingContent] = useState('');

    // Stable canvas URL
    const canvasObjectUrlRef = useRef<string | null>(null);
    const canvasObjectUrlFileRef = useRef<File | null>(null);

    const getStableCanvasUrlFromAttachment = useCallback((att: Attachment) => {
        if (att.file) {
            const file = att.file;
            if (!canvasObjectUrlRef.current || canvasObjectUrlFileRef.current !== file) {
                if (canvasObjectUrlRef.current) URL.revokeObjectURL(canvasObjectUrlRef.current);
                canvasObjectUrlRef.current = URL.createObjectURL(file);
                canvasObjectUrlFileRef.current = file;
            }
            return canvasObjectUrlRef.current;
        }
        return att.url || att.tempUrl || null;
    }, []);

    useEffect(() => {
        return () => {
            if (canvasObjectUrlRef.current) {
                URL.revokeObjectURL(canvasObjectUrlRef.current);
                canvasObjectUrlRef.current = null;
                canvasObjectUrlFileRef.current = null;
            }
        };
    }, []);

    const [lastProcessedMsgId, setLastProcessedMsgId] = useState<string | null>(null);
    const [isCompareMode, setIsCompareMode] = useState(false);
    const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });

    // ✅ Mask 工具状态（默认 select 矩形选择工具）
    const [activeMaskTool, setActiveMaskTool] = useState<MaskTool>('select');
    const [brushSize, setBrushSize] = useState(20); // 默认画笔大小 20px
    const [isMaskInverted, setIsMaskInverted] = useState(false); // 前景/背景切换
    const [isPreviewingMask, setIsPreviewingMask] = useState(false); // 正在加载自动 mask 预览
    // maskMode 使用 controls.maskMode，以便在发送请求时能够正确传递给后端

    // ✅ 选区状态（支持多个矩形）
    const [selectionRects, setSelectionRects] = useState<SelectionRect[]>([]);
    const [currentSelectionRect, setCurrentSelectionRect] = useState<SelectionRect | null>(null);
    const [isSelecting, setIsSelecting] = useState(false);
    const [maskPreviewUrl, setMaskPreviewUrl] = useState<string | null>(null);
    const imageRef = useRef<HTMLImageElement>(null);

    // ✅ 画笔/橡皮擦状态
    const [isPainting, setIsPainting] = useState(false);
    const maskCanvasRef = useRef<HTMLCanvasElement | null>(null); // 存储画笔绘制的 mask 数据
    const [maskCanvasUrl, setMaskCanvasUrl] = useState<string | null>(null); // mask canvas 的 object URL（用于触发 useEffect）
    const lastBrushPosRef = useRef<{ x: number; y: number } | null>(null); // 上一次画笔位置（用于连续绘制）
    // 贝塞尔曲线控制点历史（用于平滑绘制）
    const brushPointsRef = useRef<Array<{ x: number; y: number }>>([]);
    // 显示用的 canvas ref（用于直接 DOM 更新，避免 React 重渲染）
    const displayCanvasRef = useRef<HTMLCanvasElement | null>(null);

    // ✅ 性能优化：RAF 节流相关
    const rafIdRef = useRef<number | null>(null); // requestAnimationFrame ID
    const pendingDrawRef = useRef<{ x: number; y: number; isEraser: boolean } | null>(null); // 待绘制的数据
    const hasBrushContentRef = useRef<boolean>(false); // 是否有画笔内容（避免全图扫描）
    const maskCompositeCanvasRef = useRef<HTMLCanvasElement | null>(null); // 复用的合成 canvas
    const maskPreviewBlobUrlRef = useRef<string | null>(null); // 存储 maskCanvasUrl 的 blob URL 用于清理
    const maskPreviewUrlRef = useRef<string | null>(null); // 存储 maskPreviewUrl 的 blob URL 用于清理（避免循环依赖）

    // ✅ 性能优化：光标位置使用 ref + 直接 DOM 更新（避免 React 重渲染）
    const brushCursorRef = useRef<HTMLDivElement | null>(null);
    const brushCursorPosRef = useRef<{ x: number; y: number } | null>(null);

    // Mask 工具回调
    const handleMaskToolChange = useCallback((tool: MaskTool) => {
        setActiveMaskTool(tool);
    }, []);

    const handleBrushSizeChange = useCallback((size: number) => {
        setBrushSize(size);
    }, []);

    const handleToggleMaskInvert = useCallback(() => {
        setIsMaskInverted(prev => !prev);
    }, []);

    // ✅ 画笔光标位置更新（使用 ref + 直接 DOM 更新，避免 React 重渲染）
    const handleBrushCursorMove = useCallback((pos: { x: number; y: number } | null) => {
        brushCursorPosRef.current = pos;
        const cursorEl = brushCursorRef.current;
        if (!cursorEl) return;

        if (pos) {
            cursorEl.style.display = 'block';
            cursorEl.style.left = `${pos.x - brushSize / 2}px`;
            cursorEl.style.top = `${pos.y - brushSize / 2}px`;
        } else {
            cursorEl.style.display = 'none';
        }
    }, [brushSize]);

    // ✅ 初始化/获取 mask canvas
    const getMaskCanvas = useCallback(() => {
        const img = imageRef.current;
        if (!img) return null;

        // 如果 canvas 不存在或尺寸不匹配，创建新的
        if (!maskCanvasRef.current ||
            maskCanvasRef.current.width !== img.naturalWidth ||
            maskCanvasRef.current.height !== img.naturalHeight) {
            const canvas = document.createElement('canvas');
            canvas.width = img.naturalWidth;
            canvas.height = img.naturalHeight;
            // 初始化为全透明
            const ctx = canvas.getContext('2d', { willReadFrequently: true });
            if (ctx) {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
            maskCanvasRef.current = canvas;
        }
        return maskCanvasRef.current;
    }, []);

    // ✅ 直接更新显示 canvas（不触发 React 重渲染）
    const updateDisplayCanvas = useCallback(() => {
        const srcCanvas = maskCanvasRef.current;
        const dstCanvas = displayCanvasRef.current;
        if (!srcCanvas || !dstCanvas) return;

        const ctx = dstCanvas.getContext('2d', { willReadFrequently: true });
        if (!ctx) return;

        // 确保尺寸匹配
        if (dstCanvas.width !== srcCanvas.width || dstCanvas.height !== srcCanvas.height) {
            dstCanvas.width = srcCanvas.width;
            dstCanvas.height = srcCanvas.height;
        }

        // 清除并绘制
        ctx.clearRect(0, 0, dstCanvas.width, dstCanvas.height);
        ctx.drawImage(srcCanvas, 0, 0);
    }, []);

    // ✅ 更新 mask canvas 显示 URL（仅在笔画结束时调用）
    // 优化：使用布尔标记代替全图扫描，使用 toBlob + objectURL 代替 toDataURL
    const updateMaskCanvasUrl = useCallback(() => {
        const canvas = maskCanvasRef.current;
        if (!canvas) return;

        // 使用布尔标记判断是否有内容（避免全图扫描）
        if (hasBrushContentRef.current) {
            // 清理之前的 blob URL
            if (maskPreviewBlobUrlRef.current) {
                URL.revokeObjectURL(maskPreviewBlobUrlRef.current);
                maskPreviewBlobUrlRef.current = null;
            }

            // 使用 toBlob + objectURL 代替 toDataURL（更快，内存占用更小）
            canvas.toBlob((blob) => {
                if (blob) {
                    const url = URL.createObjectURL(blob);
                    maskPreviewBlobUrlRef.current = url;
                    setMaskCanvasUrl(url);
                }
            }, 'image/png');
        } else {
            setMaskCanvasUrl(null);
        }

        // 同时更新显示 canvas
        updateDisplayCanvas();
    }, [updateDisplayCanvas]);

    // ✅ 在 mask canvas 上绘制（使用贝塞尔曲线实现平滑笔画）
    const drawOnMaskCanvas = useCallback((x: number, y: number, isEraser: boolean = false, isStart: boolean = false) => {
        const canvas = getMaskCanvas();
        if (!canvas) return;

        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        if (!ctx) return;

        const img = imageRef.current;
        if (!img) return;

        // 转换坐标：从显示坐标到实际图片坐标
        const scaleX = img.naturalWidth / img.clientWidth;
        const scaleY = img.naturalHeight / img.clientHeight;
        const actualX = x * scaleX;
        const actualY = y * scaleY;
        const actualBrushSize = brushSize * Math.max(scaleX, scaleY);

        // 设置绘制模式
        // 注意：画笔使用完全不透明的蓝色，显示时通过 CSS 应用透明度
        // 这样橡皮擦可以正确擦除（destination-out 需要完全不透明的像素才能完全擦除）
        if (isEraser) {
            ctx.globalCompositeOperation = 'destination-out';
            ctx.fillStyle = 'rgba(255, 255, 255, 1)'; // 使用白色擦除
            ctx.strokeStyle = 'rgba(255, 255, 255, 1)';
        } else {
            ctx.globalCompositeOperation = 'source-over';
            ctx.fillStyle = 'rgba(59, 130, 246, 1)'; // 完全不透明的蓝色
            ctx.strokeStyle = 'rgba(59, 130, 246, 1)';
        }

        // 如果是新笔画开始，重置点历史并绘制起始点
        if (isStart) {
            brushPointsRef.current = [{ x: actualX, y: actualY }];
            ctx.beginPath();
            ctx.arc(actualX, actualY, actualBrushSize / 2, 0, Math.PI * 2);
            ctx.fill();
        } else {
            // 添加新点到历史
            brushPointsRef.current.push({ x: actualX, y: actualY });
            const points = brushPointsRef.current;

            ctx.lineWidth = actualBrushSize;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';

            if (points.length >= 3) {
                // 使用二次贝塞尔曲线绘制平滑路径
                // 取最后三个点：p0, p1 (控制点), p2
                const p0 = points[points.length - 3];
                const p1 = points[points.length - 2]; // 控制点
                const p2 = points[points.length - 1];

                // 计算曲线的起点和终点（使用中点来确保曲线连续）
                const startX = (p0.x + p1.x) / 2;
                const startY = (p0.y + p1.y) / 2;
                const endX = (p1.x + p2.x) / 2;
                const endY = (p1.y + p2.y) / 2;

                ctx.beginPath();
                ctx.moveTo(startX, startY);
                ctx.quadraticCurveTo(p1.x, p1.y, endX, endY);
                ctx.stroke();

                // 绘制终点圆形确保笔画末端圆润
                ctx.beginPath();
                ctx.arc(endX, endY, actualBrushSize / 2, 0, Math.PI * 2);
                ctx.fill();

                // 保留最后两个点用于下一段曲线
                if (points.length > 4) {
                    brushPointsRef.current = points.slice(-3);
                }
            } else if (points.length === 2) {
                // 只有两个点时，绘制直线
                const p0 = points[0];
                const p1 = points[1];
                ctx.beginPath();
                ctx.moveTo(p0.x, p0.y);
                ctx.lineTo(p1.x, p1.y);
                ctx.stroke();

                // 绘制终点圆形
                ctx.beginPath();
                ctx.arc(p1.x, p1.y, actualBrushSize / 2, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // 重置混合模式
        ctx.globalCompositeOperation = 'source-over';

        // 标记有画笔内容（用于避免全图扫描）
        if (!isEraser) {
            hasBrushContentRef.current = true;
        }

        // 更新上一个位置（用于其他逻辑）
        lastBrushPosRef.current = { x, y };
    }, [getMaskCanvas, brushSize]);

    // ✅ 画笔/橡皮擦事件处理
    const handleBrushStart = useCallback((e: React.MouseEvent) => {
        if (activeMaskTool !== 'brush' && activeMaskTool !== 'eraser') return;

        const rect = e.currentTarget.getBoundingClientRect();
        const x = (e.clientX - rect.left) / canvas.zoom;
        const y = (e.clientY - rect.top) / canvas.zoom;

        setIsPainting(true);
        lastBrushPosRef.current = null; // 开始新笔画时重置
        brushPointsRef.current = []; // 重置贝塞尔曲线点历史
        drawOnMaskCanvas(x, y, activeMaskTool === 'eraser', true); // isStart = true
        // 直接更新显示 canvas（不触发 React 重渲染）
        updateDisplayCanvas();
    }, [activeMaskTool, canvas.zoom, drawOnMaskCanvas, updateDisplayCanvas]);

    // ✅ 使用 RAF 节流的画笔移动处理（将多次 mousemove 合并为每帧一次绘制）
    const handleBrushMove = useCallback((e: React.MouseEvent) => {
        if (!isPainting) return;

        const rect = e.currentTarget.getBoundingClientRect();
        const x = (e.clientX - rect.left) / canvas.zoom;
        const y = (e.clientY - rect.top) / canvas.zoom;

        // 存储待绘制数据
        pendingDrawRef.current = { x, y, isEraser: activeMaskTool === 'eraser' };

        // 如果没有 pending 的 RAF，则请求一个
        if (rafIdRef.current === null) {
            rafIdRef.current = requestAnimationFrame(() => {
                const pending = pendingDrawRef.current;
                if (pending) {
                    drawOnMaskCanvas(pending.x, pending.y, pending.isEraser);
                    updateDisplayCanvas();
                    pendingDrawRef.current = null;
                }
                rafIdRef.current = null;
            });
        }
    }, [isPainting, activeMaskTool, canvas.zoom, drawOnMaskCanvas, updateDisplayCanvas]);

    const handleBrushEnd = useCallback(() => {
        if (!isPainting) return;

        // 取消未完成的 RAF
        if (rafIdRef.current !== null) {
            cancelAnimationFrame(rafIdRef.current);
            rafIdRef.current = null;
        }

        // 处理最后一个待绘制的点
        const pending = pendingDrawRef.current;
        if (pending) {
            drawOnMaskCanvas(pending.x, pending.y, pending.isEraser);
            updateDisplayCanvas();
            pendingDrawRef.current = null;
        }

        setIsPainting(false);
        lastBrushPosRef.current = null;
        updateMaskCanvasUrl();
    }, [isPainting, drawOnMaskCanvas, updateDisplayCanvas, updateMaskCanvasUrl]);

    const handleMaskModeChange = useCallback(async (mode: MaskMode) => {
        controls.setMaskMode(mode);
        console.log('[ImageMaskEditView] Mask mode changed to:', mode);

        // 当切换到自动模式时，清除手动绘制的选区并获取自动 mask 预览
        if (mode !== 'MASK_MODE_USER_PROVIDED') {
            setSelectionRects([]);
            setCurrentSelectionRect(null);

            // 如果有图片，调用 API 获取自动 mask 预览
            if (activeImageUrl) {
                setIsPreviewingMask(true);
                try {
                    // 获取图片的 base64 数据
                    const response = await fetch(activeImageUrl);
                    const blob = await response.blob();
                    const base64 = await new Promise<string>((resolve) => {
                        const reader = new FileReader();
                        reader.onloadend = () => {
                            const result = reader.result as string;
                            // 移除 data:image/...;base64, 前缀
                            const base64Data = result.split(',')[1] || result;
                            resolve(base64Data);
                        };
                        reader.readAsDataURL(blob);
                    });

                    // 调用 mask 预览 API
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    const result = await apiClient.request<any>(`/api/modes/${providerId || 'google'}/image-mask-preview`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            modelId: 'image-segmentation-001',
                            prompt: '',
                            attachments: [{
                                name: 'image',
                                mimeType: 'image/png',
                                base64Data: base64,
                            }],
                            extra: {
                                maskMode: mode,
                            },
                        }),
                    });

                    // 响应格式: { success: true, data: { success: true, masks: [...] }, provider: ..., mode: ... }
                    console.log('[ImageMaskEditView] API response:', result);
                    const maskData = result.data || result;
                    if (maskData?.success && maskData?.masks?.length > 0) {
                        // 显示第一个 mask 预览
                        const maskUrl = maskData.masks[0].url;
                        console.log('[ImageMaskEditView] Auto mask preview loaded, url length:', maskUrl?.length);
                        setMaskPreviewUrl(maskUrl);
                    } else {
                        const errorMsg = maskData?.error || result?.error || 'Unknown error';
                        console.warn('[ImageMaskEditView] Auto mask preview failed:', errorMsg);
                        console.warn('[ImageMaskEditView] Full response:', JSON.stringify(result, null, 2));
                        setMaskPreviewUrl(null);
                    }
                } catch (error) {
                    console.error('[ImageMaskEditView] Failed to get auto mask preview:', error);
                    setMaskPreviewUrl(null);
                } finally {
                    setIsPreviewingMask(false);
                }
            } else {
                setMaskPreviewUrl(null);
            }
        } else {
            // 切换回手动模式时，清除自动 mask 预览
            setMaskPreviewUrl(null);
        }
    }, [controls, activeImageUrl, providerId]);

    const handleImportMask = useCallback(() => {
        console.log('[ImageMaskEditView] Import mask clicked');
        // TODO: 实现蒙版导入功能
    }, []);

    const handleClearMask = useCallback(() => {
        console.log('[ImageMaskEditView] Clear mask clicked');
        setSelectionRects([]);
        setCurrentSelectionRect(null);
        setMaskPreviewUrl(null);
        // 清除画笔绘制的 mask
        if (maskCanvasRef.current) {
            const ctx = maskCanvasRef.current.getContext('2d', { willReadFrequently: true });
            if (ctx) {
                ctx.clearRect(0, 0, maskCanvasRef.current.width, maskCanvasRef.current.height);
            }
        }
        // 清除显示 canvas
        if (displayCanvasRef.current) {
            const ctx = displayCanvasRef.current.getContext('2d', { willReadFrequently: true });
            if (ctx) {
                ctx.clearRect(0, 0, displayCanvasRef.current.width, displayCanvasRef.current.height);
            }
        }
        // 重置画笔内容标记
        hasBrushContentRef.current = false;
        // 清理 blob URL
        if (maskPreviewBlobUrlRef.current) {
            URL.revokeObjectURL(maskPreviewBlobUrlRef.current);
            maskPreviewBlobUrlRef.current = null;
        }
        if (maskPreviewUrlRef.current) {
            URL.revokeObjectURL(maskPreviewUrlRef.current);
            maskPreviewUrlRef.current = null;
        }
        setMaskCanvasUrl(null);
    }, []);

    // ✅ 生成 Mask 图像（支持正常/反转模式，合并矩形和画笔数据）
    // 优化：复用 canvas、使用 drawImage + globalCompositeOperation 替代逐像素遍历、使用 toBlob
    const generateMaskFromSelections = useCallback((rects: SelectionRect[], inverted: boolean = false) => {
        const img = imageRef.current;
        const hasBrushMask = hasBrushContentRef.current;

        // 如果既没有矩形也没有画笔数据，清除 mask
        if ((!img || rects.length === 0) && !hasBrushMask) {
            setMaskPreviewUrl(null);
            return;
        }

        if (!img) return;

        // 获取图片的实际尺寸
        const imgWidth = img.naturalWidth;
        const imgHeight = img.naturalHeight;

        // 获取图片在页面上的显示尺寸
        const displayWidth = img.clientWidth;
        const displayHeight = img.clientHeight;

        // 计算缩放比例
        const scaleX = imgWidth / displayWidth;
        const scaleY = imgHeight / displayHeight;

        // 复用合成 canvas（避免每次创建新的）
        if (!maskCompositeCanvasRef.current ||
            maskCompositeCanvasRef.current.width !== imgWidth ||
            maskCompositeCanvasRef.current.height !== imgHeight) {
            maskCompositeCanvasRef.current = document.createElement('canvas');
            maskCompositeCanvasRef.current.width = imgWidth;
            maskCompositeCanvasRef.current.height = imgHeight;
        }
        const canvas = maskCompositeCanvasRef.current;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        if (!ctx) return;

        // 清除画布
        ctx.clearRect(0, 0, imgWidth, imgHeight);

        if (inverted) {
            // 反转模式：白色背景，黑色选区（选中区域外部为编辑区域）
            ctx.fillStyle = 'white';
            ctx.fillRect(0, 0, imgWidth, imgHeight);
            ctx.fillStyle = 'black';
        } else {
            // 正常模式：黑色背景，白色选区（选中区域内部为编辑区域）
            ctx.fillStyle = 'black';
            ctx.fillRect(0, 0, imgWidth, imgHeight);
            ctx.fillStyle = 'white';
        }

        // 绘制所有矩形
        rects.forEach(rect => {
            const x = Math.min(rect.startX, rect.endX) * scaleX;
            const y = Math.min(rect.startY, rect.endY) * scaleY;
            const width = Math.abs(rect.endX - rect.startX) * scaleX;
            const height = Math.abs(rect.endY - rect.startY) * scaleY;
            ctx.fillRect(x, y, width, height);
        });

        // 合并画笔绘制的 mask（如果有）
        // 优化：使用 drawImage + globalCompositeOperation 替代逐像素遍历
        if (maskCanvasRef.current && hasBrushMask) {
            const brushCanvas = maskCanvasRef.current;

            // 保存当前状态
            ctx.save();

            // 使用 destination-out（反转模式）或 source-over（正常模式）合成
            // 首先需要将画笔的蓝色区域转换为黑白 mask
            // 创建临时 canvas 来转换
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = brushCanvas.width;
            tempCanvas.height = brushCanvas.height;
            const tempCtx = tempCanvas.getContext('2d', { willReadFrequently: true });
            if (tempCtx) {
                // 先填充目标颜色
                tempCtx.fillStyle = inverted ? 'black' : 'white';
                tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);

                // 使用 destination-in 只保留画笔区域
                tempCtx.globalCompositeOperation = 'destination-in';
                tempCtx.drawImage(brushCanvas, 0, 0);

                // 合并到主 canvas
                ctx.globalCompositeOperation = 'source-over';
                ctx.drawImage(tempCanvas, 0, 0);
            }

            ctx.restore();
        }

        // 使用 toBlob + objectURL 代替 toDataURL（更快，内存占用更小）
        canvas.toBlob((blob) => {
            if (blob) {
                // 清理之前的 URL（使用 ref 避免循环依赖）
                if (maskPreviewUrlRef.current) {
                    URL.revokeObjectURL(maskPreviewUrlRef.current);
                }
                const url = URL.createObjectURL(blob);
                maskPreviewUrlRef.current = url;
                setMaskPreviewUrl(url);
            }
        }, 'image/png');

        console.log('[ImageMaskEditView] Mask 生成完成:', {
            imageSize: { imgWidth, imgHeight },
            displaySize: { displayWidth, displayHeight },
            rectCount: rects.length,
            hasBrushMask,
            inverted
        });
    }, []); // 移除 maskPreviewUrl 依赖，使用 ref 避免循环

    // ✅ 选区开始（考虑缩放比例）
    const handleSelectionStart = useCallback((e: React.MouseEvent) => {
        if (activeMaskTool !== 'select') return;

        const rect = e.currentTarget.getBoundingClientRect();
        // 除以缩放比例，转换到图片原始坐标系
        const x = (e.clientX - rect.left) / canvas.zoom;
        const y = (e.clientY - rect.top) / canvas.zoom;

        setIsSelecting(true);
        setCurrentSelectionRect({
            startX: x,
            startY: y,
            endX: x,
            endY: y
        });
    }, [activeMaskTool, canvas.zoom]);

    // ✅ 选区移动（考虑缩放比例）
    const handleSelectionMove = useCallback((e: React.MouseEvent) => {
        if (!isSelecting || activeMaskTool !== 'select') return;

        const rect = e.currentTarget.getBoundingClientRect();
        // 除以缩放比例，转换到图片原始坐标系
        const x = (e.clientX - rect.left) / canvas.zoom;
        const y = (e.clientY - rect.top) / canvas.zoom;

        setCurrentSelectionRect((prev: SelectionRect | null) => prev ? {
            ...prev,
            endX: x,
            endY: y
        } : null);
    }, [isSelecting, activeMaskTool, canvas.zoom]);

    // ✅ 选区结束
    // 注意：只设置 state，mask 生成由 useEffect 统一处理，避免冗余调用
    const handleSelectionEnd = useCallback(() => {
        if (!isSelecting || !currentSelectionRect) return;

        setIsSelecting(false);

        const width = Math.abs(currentSelectionRect.endX - currentSelectionRect.startX);
        const height = Math.abs(currentSelectionRect.endY - currentSelectionRect.startY);

        // 只有当选区大小有效时才添加到数组
        if (width > 5 && height > 5) {
            const newRects = [...selectionRects, currentSelectionRect];
            setSelectionRects(newRects);
            // mask 生成由 useEffect (line ~1315) 统一处理
        }

        setCurrentSelectionRect(null);
    }, [isSelecting, currentSelectionRect, selectionRects]);

    // ✅ 删除单个选区
    // 注意：只设置 state，mask 生成/清除由 useEffect 统一处理
    const handleDeleteSelection = useCallback((index: number) => {
        const newRects = selectionRects.filter((_, i) => i !== index);
        setSelectionRects(newRects);
        // 当没有选区且没有画笔数据时，useEffect 会清除 maskPreviewUrl
        // mask 生成由 useEffect (line ~1315) 统一处理
    }, [selectionRects]);

    // ✅ 当反转模式变化、选区变化或画笔数据变化时，重新生成 mask
    // 使用 maskCanvasUrl 作为画笔数据变化的触发器
    useEffect(() => {
        const hasBrushData = maskCanvasUrl !== null;
        const isAutoMaskMode = controls.maskMode !== 'MASK_MODE_USER_PROVIDED';

        if (selectionRects.length > 0 || hasBrushData) {
            // 有选区或画笔数据时生成 mask（仅在手动模式下有效）
            generateMaskFromSelections(selectionRects, isMaskInverted);
        } else if (!isAutoMaskMode) {
            // 手动模式下，既没有选区也没有画笔数据时，清除 mask 预览
            // 注意：自动 mask 模式下，maskPreviewUrl 由 API 返回设置，不应在此清除
            if (maskPreviewUrlRef.current) {
                URL.revokeObjectURL(maskPreviewUrlRef.current);
                maskPreviewUrlRef.current = null;
            }
            setMaskPreviewUrl(null);
        }
        // 自动 mask 模式下，保留 API 返回的 maskPreviewUrl
    }, [isMaskInverted, selectionRects, generateMaskFromSelections, maskCanvasUrl, controls.maskMode]);

    // ✅ 当 maskCanvasUrl 变化时，同步更新显示 canvas
    useEffect(() => {
        if (maskCanvasUrl && maskCanvasRef.current) {
            updateDisplayCanvas();
        }
    }, [maskCanvasUrl, updateDisplayCanvas]);

    // ✅ 组件卸载时清理 blob URL
    useEffect(() => {
        return () => {
            // 清理 maskCanvasUrl 的 blob URL
            if (maskPreviewBlobUrlRef.current) {
                URL.revokeObjectURL(maskPreviewBlobUrlRef.current);
            }
            // 清理 maskPreviewUrl 的 blob URL
            if (maskPreviewUrlRef.current) {
                URL.revokeObjectURL(maskPreviewUrlRef.current);
            }
            // 取消未完成的 RAF
            if (rafIdRef.current !== null) {
                cancelAnimationFrame(rafIdRef.current);
            }
        };
    }, []);

    useEffect(() => {
        canvas.resetView();
        setIsCompareMode(false);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeImageUrl]); // canvas.resetView 是稳定的函数，不需要作为依赖

    useEffect(() => {
        if (canvasObjectUrlRef.current && activeImageUrl !== canvasObjectUrlRef.current) {
            URL.revokeObjectURL(canvasObjectUrlRef.current);
            canvasObjectUrlRef.current = null;
            canvasObjectUrlFileRef.current = null;
        }
    }, [activeImageUrl]);

    const originalImageUrl = useMemo(() => {
        const lastUserMsg = [...messages].reverse().find(m => m.role === Role.USER && m.attachments?.length);
        return lastUserMsg?.attachments?.[0]?.url || null;
    }, [messages]);

    useEffect(() => {
        if (initialAttachments && initialAttachments.length > 0) {
            setActiveAttachments(initialAttachments);
            setActiveImageUrl(getStableCanvasUrlFromAttachment(initialAttachments[0]));
        }
    }, [initialAttachments, getStableCanvasUrlFromAttachment]);

    useEffect(() => {
        if (activeAttachments.length > 0) {
            setActiveImageUrl(getStableCanvasUrlFromAttachment(activeAttachments[0]));
        }
    }, [activeAttachments, getStableCanvasUrlFromAttachment]);

    useEffect(() => {
        const container = scrollRef.current;
        if (!container) return;
        requestAnimationFrame(() => {
            container.scrollTo({
                top: container.scrollHeight,
                behavior: 'smooth'
            });
        });
    }, [messages, activeAttachments]);

    useEffect(() => {
        const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
        if (!lastMessage) {
            setDisplayedThinkingContent('');
            return;
        }
        
        const thoughts = lastMessage?.thoughts || [];
        const textResponse = lastMessage?.textResponse;
        const thinkingParts: string[] = [];
        thoughts.forEach((thought) => {
            if (thought.type === 'text') {
                thinkingParts.push(thought.content);
            } else {
                thinkingParts.push('[图片思考过程]');
            }
        });
        if (textResponse) {
            thinkingParts.push(`\n\n💬 AI 响应：\n${textResponse}`);
        }
        const fullContent = thinkingParts.join('\n\n');
        
        if (!fullContent) {
            setDisplayedThinkingContent('');
            return;
        }
        
        if (loadingState === 'idle') {
            setDisplayedThinkingContent(fullContent);
            return;
        }
        
        const targetLength = fullContent.length;
        const currentLength = displayedThinkingContent.length;
        
        if (currentLength < targetLength) {
            const chunkSize = 5;
            const nextLength = Math.min(currentLength + chunkSize, targetLength);
            
            const timer = setTimeout(() => {
                setDisplayedThinkingContent(fullContent.substring(0, nextLength));
            }, 30);
            
            return () => clearTimeout(timer);
        } else if (fullContent !== displayedThinkingContent) {
            setDisplayedThinkingContent(fullContent);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [messages, loadingState]); // displayedThinkingContent 故意不加入依赖，避免打字机效果导致无限循环
    
    useEffect(() => {
        if (activeAttachments.length === 0 && !activeImageUrl) {
            const lastUserMsg = [...messages].reverse().find(m => m.role === Role.USER && m.attachments?.length);
            if (lastUserMsg && lastUserMsg.attachments?.[0]?.url) {
                setActiveImageUrl(lastUserMsg.attachments[0].url);
            } else {
                const lastModelMsg = [...messages].reverse().find(m => m.role === Role.MODEL && m.attachments?.length);
                if (lastModelMsg && lastModelMsg.attachments?.[0]?.url) {
                    setActiveImageUrl(lastModelMsg.attachments[0].url);
                }
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

    // ✅ ChatEditInputArea 已经处理了附件和参数，这里只需要直接转发
    const handleSend = useCallback((text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
        onSend(text, options, attachments, editMode);
    }, [onSend, editMode]);

    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

    const sidebarContent = useMemo(() => (
        <div ref={scrollRef} className="flex-1 p-4 space-y-6 overflow-y-auto custom-scrollbar">
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
                                    className={`relative group mt-1 rounded-lg overflow-hidden border cursor-pointer transition-all ${activeImageUrl === att.url ? 'ring-2 ring-purple-500 border-transparent' : 'border-slate-700 hover:border-slate-500'
                                        }`}
                                >
                                    <img src={att.url} className="w-full h-32 object-cover bg-slate-900" alt="thumbnail" />
                                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                                        {activeImageUrl === att.url && <div className="bg-purple-500 w-2 h-2 rounded-full absolute top-2 right-2 shadow-sm" />}
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
            {loadingState !== 'idle' && (() => {
                let statusText = 'Processing request...';
                let statusIcon = <Bot size={16} className="text-slate-500" />;
                
                if (loadingState === 'uploading') {
                    statusText = '上传图片中...';
                    statusIcon = <Layers size={16} className="text-blue-400" />;
                } else if (loadingState === 'loading') {
                    statusText = 'Mask 编辑中，正在处理遮罩区域...';
                    statusIcon = <Crop size={16} className="text-purple-400" />;
                } else if (loadingState === 'streaming') {
                    statusText = '流式处理中...';
                    statusIcon = <Sparkles size={16} className="text-purple-400 animate-pulse" />;
                }
                
                const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
                const thoughts = lastMessage?.thoughts || [];
                const textResponse = lastMessage?.textResponse;
                const hasTextContent = lastMessage?.content && lastMessage.content.trim().length > 0;
                const isThinkingComplete = loadingState === 'idle';
                
                return (
                    <div className="flex items-start gap-2">
                        <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0">
                            {statusIcon}
                        </div>
                        <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400 flex-1">
                            <div className={`font-medium mb-1 ${loadingState !== 'idle' ? 'animate-pulse' : ''}`}>
                                {statusText}
                            </div>
                            
                            {displayedThinkingContent && (
                                <div className="mt-2">
                                    <ThinkingBlock
                                        content={displayedThinkingContent}
                                        isOpen={isThinkingOpen}
                                        onToggle={() => setIsThinkingOpen(!isThinkingOpen)}
                                        isComplete={isThinkingComplete}
                                    />
                                </div>
                            )}
                            
                            {hasTextContent && !thoughts.length && !textResponse && (
                                <div className="mt-2 pt-2 border-t border-slate-700/50 text-slate-500 italic">
                                    {lastMessage.content.substring(0, 100)}
                                    {lastMessage.content.length > 100 ? '...' : ''}
                                </div>
                            )}
                        </div>
                    </div>
                );
            })()}
            <div />
        </div>
    ), [messages, loadingState, activeModelConfig?.name, activeImageUrl, activeAttachments, displayedThinkingContent, isThinkingOpen]);

    const toggleCompare = useCallback(() => setIsCompareMode(prev => !prev), []);
    const handleFullscreen = useCallback(() => {
        if (activeImageUrl) onImageClick(activeImageUrl);
    }, [activeImageUrl, onImageClick]);
    const handleExpand = useCallback(() => {
        if (activeImageUrl && onExpandImage) onExpandImage(activeImageUrl);
    }, [activeImageUrl, onExpandImage]);

    // ✅ 主区域：两栏布局（画布 + 参数面板）
    const mainContent = useMemo(() => (
        <div className="flex-1 flex flex-row h-full">
            {/* ========== 左侧：画布区域 ========== */}
            <ImageEditMainCanvas
                loadingState={loadingState}
                isCompareMode={isCompareMode}
                activeAttachments={activeAttachments}
                activeImageUrl={activeImageUrl}
                originalImageUrl={originalImageUrl}
                zoom={canvas.zoom}
                isDragging={canvas.isDragging}
                canvasStyle={canvas.canvasStyle}
                onWheel={canvas.handleWheel}
                onMouseDown={canvas.handleMouseDown}
                onMouseMove={canvas.handleMouseMove}
                onMouseUp={canvas.handleMouseUp}
                onZoomIn={canvas.handleZoomIn}
                onZoomOut={canvas.handleZoomOut}
                onReset={canvas.handleReset}
                onFullscreen={activeImageUrl ? handleFullscreen : undefined}
                onExpand={onExpandImage && activeImageUrl ? handleExpand : undefined}
                onToggleCompare={originalImageUrl ? toggleCompare : undefined}
                // ✅ Mask 工具栏
                activeMaskTool={activeMaskTool}
                onMaskToolChange={handleMaskToolChange}
                brushSize={brushSize}
                onBrushSizeChange={handleBrushSizeChange}
                // ✅ Mask 自动提取模式
                maskMode={controls.maskMode}
                onMaskModeChange={handleMaskModeChange}
                onImportMask={handleImportMask}
                onClearMask={handleClearMask}
                isPreviewingMask={isPreviewingMask}
                // ✅ Mask 反转（前景/背景切换）
                isMaskInverted={isMaskInverted}
                onToggleMaskInvert={handleToggleMaskInvert}
                // ✅ 选区和 Mask 预览（支持多个矩形）
                selectionRects={selectionRects}
                currentSelectionRect={currentSelectionRect}
                isSelecting={isSelecting}
                onSelectionStart={handleSelectionStart}
                onSelectionMove={handleSelectionMove}
                onSelectionEnd={handleSelectionEnd}
                onDeleteSelection={handleDeleteSelection}
                maskPreviewUrl={maskPreviewUrl}
                imageRef={imageRef}
                // ✅ 画笔/橡皮擦
                onBrushStart={handleBrushStart}
                onBrushMove={handleBrushMove}
                onBrushEnd={handleBrushEnd}
                isPainting={isPainting}
                maskCanvasUrl={maskCanvasUrl}
                brushCursorRef={brushCursorRef}
                onBrushCursorMove={handleBrushCursorMove}
                maskCanvasRef={maskCanvasRef}
                displayCanvasRef={displayCanvasRef}
            />

            {/* ========== 右侧：参数面板 ========== */}
            <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
                {/* 头部 */}
                <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal size={14} className="text-purple-400" />
                        <span className="text-xs font-bold text-white">Mask 参数</span>
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
                        mode={editMode}
                        providerId={providerId || 'google'}
                        controls={controls}
                    />
                </div>

                {/* 底部固定区：使用 ChatEditInputArea 组件 */}
                <ChatEditInputArea
                    onSend={handleSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop}
                    mode={editMode}
                    activeAttachments={activeAttachments}
                    onAttachmentsChange={setActiveAttachments}
                    activeImageUrl={activeImageUrl}
                    onActiveImageUrlChange={setActiveImageUrl}
                    messages={messages}
                    sessionId={currentSessionId}
                    initialPrompt={initialPrompt}
                    initialAttachments={initialAttachments}
                    providerId={providerId}
                    controls={controls}
                />
            </div>
        </div>
    ), [loadingState, isCompareMode, activeAttachments, activeImageUrl, originalImageUrl, canvas, handleFullscreen, handleExpand, toggleCompare, onExpandImage, controls, providerId, resetParams, editMode, activeModelConfig, onStop, messages, currentSessionId, initialPrompt, initialAttachments, handleSend, activeMaskTool, handleMaskToolChange, brushSize, handleBrushSizeChange, handleMaskModeChange, handleImportMask, handleClearMask, isMaskInverted, handleToggleMaskInvert, selectionRects, currentSelectionRect, isSelecting, handleSelectionStart, handleSelectionMove, handleSelectionEnd, handleDeleteSelection, maskPreviewUrl, handleBrushStart, handleBrushMove, handleBrushEnd, isPainting, maskCanvasUrl, handleBrushCursorMove]);

    return (
        <GenViewLayout
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            sidebarTitle="History"
            sidebarHeaderIcon={<Layers size={14} />}
            sidebar={sidebarContent}
            main={mainContent}
        />
    );
}, arePropsEqual);
