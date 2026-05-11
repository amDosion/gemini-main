/**
 * Mask 编辑器底部工具栏（Extract mask 下拉 + Import + 工具切换 + 大小 + Clear）。
 *
 * 抽离自 `ImageMaskEditView.tsx` 内部 ImageEditMainCanvas 的 L536-810 inline JSX
 * （JIRA-frontend-view-decomposition.md P0 #2 Step 4）。
 *
 * 1:1 行为等价：UI 类名、ARIA、内部 `isExtractMenuOpen` 下拉状态均保留。
 * 渲染条件 `loadingState === 'idle'` 内化为组件早返 — 调用方不再需要 `&&` 包裹。
 */

import { memo, useState } from 'react';
import {
  Wand2,
  Upload,
  Move,
  Square,
  Pencil,
  Eraser,
  Trash2,
  ChevronDown,
  FlipVertical2,
  Loader2,
} from 'lucide-react';
import { type MaskTool, type MaskMode } from '../../../utils/maskHelpers';

export interface MaskToolbarProps {
  loadingState: string;
  // Mask mode（Vertex AI mask_mode 自动提取）
  maskMode: MaskMode;
  onMaskModeChange: (mode: MaskMode) => void;
  isPreviewingMask: boolean | undefined;
  // Import/Clear
  onImportMask?: () => void;
  onClearMask?: () => void;
  // 工具
  activeMaskTool: MaskTool;
  onMaskToolChange: (tool: MaskTool) => void;
  // 前景/背景反转
  isMaskInverted: boolean;
  onToggleMaskInvert: () => void;
  // 画笔大小
  brushSize: number;
  onBrushSizeChange: (size: number) => void;
}

export const MaskToolbar = memo(
  ({
    loadingState,
    maskMode,
    onMaskModeChange,
    isPreviewingMask,
    onImportMask,
    onClearMask,
    activeMaskTool,
    onMaskToolChange,
    isMaskInverted,
    onToggleMaskInvert,
    brushSize,
    onBrushSizeChange,
  }: MaskToolbarProps) => {
    const [isExtractMenuOpen, setIsExtractMenuOpen] = useState(false);

    if (loadingState !== 'idle') return null;

    return (
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
                <Wand2
                  size={14}
                  className={
                    maskMode !== 'MASK_MODE_USER_PROVIDED' ? 'text-purple-400' : 'text-slate-400'
                  }
                />
              )}
              <span>
                {isPreviewingMask
                  ? 'Loading...'
                  : maskMode === 'MASK_MODE_BACKGROUND'
                    ? 'Background'
                    : maskMode === 'MASK_MODE_FOREGROUND'
                      ? 'Foreground'
                      : maskMode === 'MASK_MODE_SEMANTIC'
                        ? 'People'
                        : 'Extract mask'}
              </span>
              <ChevronDown
                size={12}
                className={`transition-transform ${isExtractMenuOpen ? 'rotate-180' : ''}`}
              />
            </button>
            {/* 下拉菜单 */}
            {isExtractMenuOpen && (
              <div className="absolute bottom-full left-0 mb-2 py-1 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-30 min-w-[220px]">
                {/* Background 选项 */}
                <button
                  onClick={() => {
                    onMaskModeChange('MASK_MODE_BACKGROUND');
                    setIsExtractMenuOpen(false);
                  }}
                  className={`w-full px-3 py-2.5 text-left text-xs transition-colors flex items-center gap-2.5 whitespace-nowrap ${
                    maskMode === 'MASK_MODE_BACKGROUND'
                      ? 'bg-purple-500/20 text-purple-400'
                      : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                  }`}
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="flex-shrink-0"
                  >
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <path d="M3 15l4-4 4 4 6-6 4 4" />
                    <circle cx="8" cy="9" r="2" />
                  </svg>
                  Background (自动背景)
                  {maskMode === 'MASK_MODE_BACKGROUND' && (
                    <span className="ml-auto text-purple-400">✓</span>
                  )}
                </button>
                {/* Foreground 选项 */}
                <button
                  onClick={() => {
                    onMaskModeChange('MASK_MODE_FOREGROUND');
                    setIsExtractMenuOpen(false);
                  }}
                  className={`w-full px-3 py-2.5 text-left text-xs transition-colors flex items-center gap-2.5 whitespace-nowrap ${
                    maskMode === 'MASK_MODE_FOREGROUND'
                      ? 'bg-purple-500/20 text-purple-400'
                      : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                  }`}
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="flex-shrink-0"
                  >
                    <rect x="3" y="3" width="18" height="18" rx="2" strokeDasharray="4 2" />
                    <rect x="7" y="7" width="10" height="10" rx="1" />
                  </svg>
                  Foreground (自动前景)
                  {maskMode === 'MASK_MODE_FOREGROUND' && (
                    <span className="ml-auto text-purple-400">✓</span>
                  )}
                </button>
                {/* Semantic/People 选项 */}
                <button
                  onClick={() => {
                    onMaskModeChange('MASK_MODE_SEMANTIC');
                    setIsExtractMenuOpen(false);
                  }}
                  className={`w-full px-3 py-2.5 text-left text-xs transition-colors flex items-center gap-2.5 whitespace-nowrap ${
                    maskMode === 'MASK_MODE_SEMANTIC'
                      ? 'bg-purple-500/20 text-purple-400'
                      : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                  }`}
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="flex-shrink-0"
                  >
                    <circle cx="12" cy="7" r="4" />
                    <path d="M5 21c0-4 3-7 7-7s7 3 7 7" />
                  </svg>
                  People (人物分割)
                  {maskMode === 'MASK_MODE_SEMANTIC' && (
                    <span className="ml-auto text-purple-400">✓</span>
                  )}
                </button>
                <div className="border-t border-slate-700 my-1" />
                {/* 清除自动提取 - 切换回手动模式 */}
                {maskMode !== 'MASK_MODE_USER_PROVIDED' && (
                  <button
                    onClick={() => {
                      onMaskModeChange('MASK_MODE_USER_PROVIDED');
                      setIsExtractMenuOpen(false);
                    }}
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
            title={
              isMaskInverted
                ? '当前: 背景模式（点击切换到前景）'
                : '当前: 前景模式（点击切换到背景）'
            }
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
    );
  }
);

MaskToolbar.displayName = 'MaskToolbar';
