/**
 * ImageCanvasControls 组件
 * 
 * 统一的图片操作控制按钮组件，支持两种变体：
 * 
 * 1. canvas 变体（默认）：用于画布模式（ImageEditView 等）
 *    - 缩放控制（放大/缩小/重置）
 *    - 操作按钮（编辑/扩图/全屏/下载/对比）
 * 
 * 2. overlay 变体：用于图片网格悬浮按钮（ImageGenView）
 *    - 只显示操作按钮，无缩放控制
 *    - 悬浮样式，更紧凑
 * 
 * 按钮显示逻辑：
 * - 基础规则：传入对应回调即显示
 * - 模式感知：根据 mode 自动决定按钮可见性（可选）
 * 
 * 模式与按钮关系：
 * | 模式                    | 编辑 | 扩图 | 全屏 | 下载 | 对比 | 缩放 |
 * |------------------------|------|------|------|------|------|------|
 * | image-gen              | ✅   | ✅   | ✅   | ✅   | ❌   | ❌   |
 * | image-chat-edit        | ❌   | ✅   | ✅   | ✅   | ✅   | ✅   |
 * | image-mask-edit        | ❌   | ✅   | ✅   | ✅   | ✅   | ✅   |
 * | image-inpainting       | ❌   | ✅   | ✅   | ✅   | ✅   | ✅   |
 * | image-background-edit  | ❌   | ✅   | ✅   | ✅   | ✅   | ✅   |
 * | image-recontext        | ❌   | ✅   | ✅   | ✅   | ✅   | ✅   |
 * | virtual-try-on         | ❌   | ❌   | ✅   | ✅   | ❌   | ❌   |
 * | image-outpainting      | ✅   | ❌   | ✅   | ✅   | ✅   | ✅   |
 */

import React, { useMemo } from 'react';
import { Plus, Minus, RotateCcw, Maximize2, Download, Expand, SplitSquareHorizontal, Crop } from 'lucide-react';
import { AppMode, Attachment } from '../../types/types';

// 模式按钮配置表
const MODE_BUTTON_CONFIG: Record<string, {
  edit: boolean;
  expand: boolean;
  compare: boolean;
  zoom: boolean;
}> = {
  // 图片生成：可编辑、可扩图、无对比、无缩放
  'image-gen': { edit: true, expand: true, compare: false, zoom: false },
  // 编辑类模式：不可编辑（已在编辑）、可扩图、有对比、有缩放
  'image-chat-edit': { edit: false, expand: true, compare: true, zoom: true },
  'image-mask-edit': { edit: false, expand: true, compare: true, zoom: true },
  'image-inpainting': { edit: false, expand: true, compare: true, zoom: true },
  'image-background-edit': { edit: false, expand: true, compare: true, zoom: true },
  'image-recontext': { edit: false, expand: true, compare: true, zoom: true },
  // 虚拟试衣：只有全屏和下载
  'virtual-try-on': { edit: false, expand: false, compare: false, zoom: false },
  // 扩图模式：可编辑（结果）、不可扩图（已在扩图）、有对比、有缩放
  'image-outpainting': { edit: true, expand: false, compare: true, zoom: true },
  // 默认配置
  'default': { edit: true, expand: true, compare: true, zoom: true },
};

export interface ImageCanvasControlsProps {
  /** 变体：canvas=画布控制，overlay=悬浮按钮 */
  variant?: 'canvas' | 'overlay';
  /** 当前模式（用于自动控制按钮显示） */
  mode?: AppMode;
  /** 是否使用模式感知（默认 true，设为 false 则完全由回调决定显示） */
  modeAware?: boolean;
  
  // ========== 缩放控制（仅 canvas 变体 + 支持缩放的模式） ==========
  /** 当前缩放比例 */
  zoom?: number;
  /** 放大回调 */
  onZoomIn?: (e?: React.MouseEvent) => void;
  /** 缩小回调 */
  onZoomOut?: (e?: React.MouseEvent) => void;
  /** 重置回调 */
  onReset?: (e?: React.MouseEvent) => void;
  
  // ========== 操作按钮（回调存在 + 模式允许 = 显示） ==========
  /** 编辑跳转回调 */
  onEdit?: () => void;
  /** 扩图跳转回调 */
  onExpand?: () => void;
  /** 全屏查看回调 */
  onFullscreen?: () => void;
  /** 下载 URL */
  downloadUrl?: string;
  /** 对比模式切换回调 */
  onToggleCompare?: () => void;
  /** 是否处于对比模式 */
  isCompareMode?: boolean;
  
  // ========== 样式配置 ==========
  /** 主题色，默认 slate */
  accentColor?: 'pink' | 'orange' | 'emerald' | 'indigo';
  /** 自定义类名 */
  className?: string;
}

export const ImageCanvasControls: React.FC<ImageCanvasControlsProps> = ({
  variant = 'canvas',
  mode,
  modeAware = true,
  zoom = 1,
  onZoomIn,
  onZoomOut,
  onReset,
  onEdit,
  onExpand,
  onFullscreen,
  downloadUrl,
  onToggleCompare,
  isCompareMode = false,
  accentColor = 'pink',
  className = '',
}) => {
  // 获取当前模式的按钮配置
  const buttonConfig = useMemo(() => {
    if (!modeAware || !mode) return MODE_BUTTON_CONFIG['default'];
    return MODE_BUTTON_CONFIG[mode] || MODE_BUTTON_CONFIG['default'];
  }, [mode, modeAware]);

  // 计算各按钮是否显示（回调存在 + 模式允许）
  const showEdit = onEdit && buttonConfig.edit;
  const showExpand = onExpand && buttonConfig.expand;
  const showCompare = onToggleCompare && buttonConfig.compare;
  const showZoomControls = variant === 'canvas' && buttonConfig.zoom && onZoomIn && onZoomOut && onReset;
  
  // 按钮样式
  const buttonBase = 'p-2 hover:bg-white/10 rounded-lg text-slate-300 hover:text-white transition-colors';
  const overlayButton = 'p-2.5 rounded-xl shadow-lg transition-all';

  // 下载处理函数
  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!downloadUrl) return;
    
    const isBase64 = downloadUrl.startsWith('data:');
    const isBlob = downloadUrl.startsWith('blob:');
    const isCloudUrl = downloadUrl.startsWith('http://') || downloadUrl.startsWith('https://');
    
    if (isBase64 || isBlob) {
      const response = await fetch(downloadUrl);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `image-${Date.now()}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } else if (isCloudUrl) {
      const proxyUrl = `/api/storage/download?url=${encodeURIComponent(downloadUrl)}`;
      const a = document.createElement('a');
      a.href = proxyUrl;
      a.download = `image-${Date.now()}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  };

  // ========== Overlay 变体（悬浮按钮） ==========
  if (variant === 'overlay') {
    return (
      <div className={`flex flex-col gap-2 ${className}`}>
        {/* 编辑 - 模式感知 */}
        {showEdit && (
          <button 
            onClick={(e) => { e.stopPropagation(); onEdit!(); }}
            className={`${overlayButton} bg-pink-600 hover:bg-pink-500 text-white`}
            title="编辑"
          >
            <Crop size={18} />
          </button>
        )}
        {/* 扩图 - 模式感知 */}
        {showExpand && (
          <button 
            onClick={(e) => { e.stopPropagation(); onExpand!(); }}
            className={`${overlayButton} bg-orange-600 hover:bg-orange-500 text-white`}
            title="扩展"
          >
            <Expand size={18} />
          </button>
        )}
        {/* 全屏 - 始终显示（如果有回调） */}
        {onFullscreen && (
          <button 
            onClick={(e) => { e.stopPropagation(); onFullscreen(); }}
            className={`${overlayButton} bg-black/60 hover:bg-black/80 text-white backdrop-blur border border-white/10`}
            title="全屏"
          >
            <Maximize2 size={18} />
          </button>
        )}
        {/* 下载 - 始终显示（如果有 URL） */}
        {downloadUrl && (
          <button 
            onClick={handleDownload}
            className={`${overlayButton} bg-emerald-600 hover:bg-emerald-500 text-white`}
            title="下载"
          >
            <Download size={18} />
          </button>
        )}
      </div>
    );
  }

  // ========== Canvas 变体（画布控制） ==========
  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {/* 缩放控制 */}
      {showZoomControls && (
        <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-xl p-1.5 flex flex-col gap-1 shadow-xl">
          <button onClick={onZoomIn} className={buttonBase} title="放大">
            <Plus size={18} />
          </button>
          <button onClick={onReset} className={buttonBase} title="重置视图">
            <RotateCcw size={16} />
          </button>
          <button onClick={onZoomOut} className={buttonBase} title="缩小">
            <Minus size={18} />
          </button>
          <div className="text-center text-[10px] text-slate-500 font-mono py-1 border-t border-white/10">
            {Math.round(zoom * 100)}%
          </div>
        </div>
      )}

      {/* 操作按钮 */}
      <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-xl p-1.5 flex flex-col gap-1 shadow-xl">
        {/* 对比模式切换 - 模式感知 */}
        {showCompare && (
          <button 
            onClick={(e) => { e.stopPropagation(); onToggleCompare!(); }}
            className={`${buttonBase} ${isCompareMode ? 'bg-white/20 text-white' : ''}`}
            title={isCompareMode ? '退出对比' : '对比原图'}
          >
            <SplitSquareHorizontal size={18} />
          </button>
        )}
        
        {/* 编辑 - 模式感知 */}
        {showEdit && (
          <button 
            onClick={(e) => { e.stopPropagation(); onEdit!(); }}
            className={`${buttonBase} hover:bg-pink-600/80 text-pink-400 hover:text-white`}
            title="编辑"
          >
            <Crop size={18} />
          </button>
        )}

        {/* 扩图跳转 - 模式感知 */}
        {showExpand && (
          <button 
            onClick={(e) => { e.stopPropagation(); onExpand!(); }}
            className={`${buttonBase} hover:bg-orange-600/80 text-orange-400 hover:text-white`}
            title="扩图"
          >
            <Expand size={18} />
          </button>
        )}

        {/* 全屏查看 - 始终显示 */}
        {onFullscreen && (
          <button 
            onClick={(e) => { e.stopPropagation(); onFullscreen(); }}
            className={buttonBase}
            title="全屏查看"
          >
            <Maximize2 size={18} />
          </button>
        )}

        {/* 下载 - 始终显示 */}
        {downloadUrl && (
          <button 
            onClick={handleDownload}
            className={`${buttonBase} hover:bg-emerald-600/80 text-emerald-400 hover:text-white`}
            title="下载"
          >
            <Download size={18} />
          </button>
        )}
      </div>
    </div>
  );
};

export default ImageCanvasControls;
