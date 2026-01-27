/**
 * 模式导航侧边栏
 * 
 * 功能：
 * - 显示所有可用模式
 * - 支持拖拽到左侧或右侧
 * - 根据模型能力动态启用/禁用模式
 */
import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { 
  MessageSquare, Wand2, Crop, Expand, PlaySquare, Mic, FileText, 
  Shirt, Search, Network, Layers, Sparkles, GripVertical, X,
  ChevronLeft, ChevronRight
} from 'lucide-react';
import { AppMode, ModelConfig } from '../../types/types';

interface ModeNavigationSidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  currentMode: AppMode;
  setMode: (mode: AppMode) => void;
  currentModel?: ModelConfig;
  visibleModels?: ModelConfig[];
  allVisibleModels?: ModelConfig[];
  /** 初始位置：'left' | 'right' */
  initialPosition?: 'left' | 'right';
  /** 位置变化回调 */
  onPositionChange?: (position: 'left' | 'right') => void;
}

// 模式配置
const MODE_CONFIG = [
  { id: 'chat', label: 'Chat', icon: MessageSquare, color: 'indigo', description: '对话聊天' },
  { id: 'deep-research', label: 'Deep Research', icon: Search, color: 'blue', description: '深度研究' },
  { id: 'multi-agent', label: 'Multi-Agent', icon: Network, color: 'teal', description: '多智能体' },
  { id: 'image-gen', label: 'Gen', icon: Wand2, color: 'emerald', description: '图片生成' },
  { id: 'image-chat-edit', label: 'Chat Edit', icon: MessageSquare, color: 'pink', description: '对话编辑' },
  { id: 'image-mask-edit', label: 'Mask', icon: Crop, color: 'pink', description: '蒙版编辑' },
  { id: 'image-inpainting', label: 'Inpaint', icon: Wand2, color: 'pink', description: '局部重绘' },
  { id: 'image-background-edit', label: 'Background', icon: Layers, color: 'pink', description: '背景编辑' },
  { id: 'image-recontext', label: 'Recontext', icon: Sparkles, color: 'pink', description: '场景重构' },
  { id: 'virtual-try-on', label: 'Try-On', icon: Shirt, color: 'rose', description: '虚拟试衣' },
  { id: 'image-outpainting', label: 'Expand', icon: Expand, color: 'orange', description: '图片扩展' },
  { id: 'video-gen', label: 'Video', icon: PlaySquare, color: 'indigo', description: '视频生成' },
  { id: 'audio-gen', label: 'Audio', icon: Mic, color: 'cyan', description: '音频生成' },
  { id: 'pdf-extract', label: 'PDF', icon: FileText, color: 'purple', description: 'PDF 提取' },
] as const;

// 颜色映射
const COLOR_MAP: Record<string, { bg: string; text: string; border: string; hover: string }> = {
  indigo: { bg: 'bg-indigo-600', text: 'text-indigo-400', border: 'border-indigo-500/50', hover: 'hover:bg-indigo-600/20' },
  blue: { bg: 'bg-blue-600', text: 'text-blue-400', border: 'border-blue-500/50', hover: 'hover:bg-blue-600/20' },
  teal: { bg: 'bg-teal-600', text: 'text-teal-400', border: 'border-teal-500/50', hover: 'hover:bg-teal-600/20' },
  emerald: { bg: 'bg-emerald-600', text: 'text-emerald-400', border: 'border-emerald-500/50', hover: 'hover:bg-emerald-600/20' },
  pink: { bg: 'bg-pink-600', text: 'text-pink-400', border: 'border-pink-500/50', hover: 'hover:bg-pink-600/20' },
  rose: { bg: 'bg-rose-600', text: 'text-rose-400', border: 'border-rose-500/50', hover: 'hover:bg-rose-600/20' },
  orange: { bg: 'bg-orange-600', text: 'text-orange-400', border: 'border-orange-500/50', hover: 'hover:bg-orange-600/20' },
  cyan: { bg: 'bg-cyan-600', text: 'text-cyan-400', border: 'border-cyan-500/50', hover: 'hover:bg-cyan-600/20' },
  purple: { bg: 'bg-purple-600', text: 'text-purple-400', border: 'border-purple-500/50', hover: 'hover:bg-purple-600/20' },
};

export const ModeNavigationSidebar: React.FC<ModeNavigationSidebarProps> = ({
  isOpen,
  setIsOpen,
  currentMode,
  setMode,
  currentModel,
  visibleModels = [],
  allVisibleModels = [],
  initialPosition = 'right',
  onPositionChange,
}) => {
  const [position, setPosition] = useState<'left' | 'right'>(initialPosition);
  const [isDragging, setIsDragging] = useState(false);
  const [dragX, setDragX] = useState<number | null>(null);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const dragStartX = useRef<number>(0);
  const dragStartPosition = useRef<'left' | 'right'>('right');

  // 计算模式可用性
  const modeAvailability = useMemo(() => {
    const models = allVisibleModels.length > 0 ? allVisibleModels : (visibleModels.length > 0 ? visibleModels : (currentModel ? [currentModel] : []));
    
    const hasImageGenModels = models.some(m => {
      const id = m.id.toLowerCase();
      const isImageGenModel = id.includes('dall') || id.includes('wanx') || id.includes('flux') || 
             id.includes('midjourney') || id.includes('-t2i') || id.includes('z-image') || 
             id.includes('imagen');
      const isGeminiImageModel = id.includes('gemini') && id.includes('image');
      const isNanoBananaModel = id.includes('nano-banana');
      return isImageGenModel || isGeminiImageModel || isNanoBananaModel;
    });
    
    const hasVisionModels = models.some(m => {
      const id = m.id.toLowerCase();
      return m.capabilities.vision && !id.includes('veo');
    });
    
    const hasDeepResearchModels = models.some(m => {
      const name = (m.name || m.id || '').toLowerCase();
      return name.includes('deep-research') || name.includes('deep research') || name.includes('deepresearch');
    });
    
    const hasVideoModels = models.some(m => {
      const id = m.id.toLowerCase();
      return id.includes('veo') || id.includes('sora') || id.includes('video') || id.includes('luma');
    });
    
    const hasAudioModels = models.some(m => {
      const id = m.id.toLowerCase();
      return id.includes('tts') || id.includes('audio') || id.includes('speech');
    });
    
    const hasPdfModels = models.some(m => {
      const id = m.id.toLowerCase();
      return !id.includes('veo') && !id.includes('tts') && !id.includes('wanx') && 
             !id.includes('imagen') && !id.includes('-t2i') && !id.includes('z-image');
    });
    
    return {
      chat: true,
      'deep-research': hasDeepResearchModels,
      'multi-agent': true,
      'image-gen': hasImageGenModels,
      'image-chat-edit': hasVisionModels || hasImageGenModels,
      'image-mask-edit': hasVisionModels || hasImageGenModels,
      'image-inpainting': hasVisionModels || hasImageGenModels,
      'image-background-edit': hasVisionModels || hasImageGenModels,
      'image-recontext': hasVisionModels || hasImageGenModels,
      'virtual-try-on': hasVisionModels,
      'image-outpainting': true,
      'video-gen': hasVideoModels,
      'audio-gen': hasAudioModels || true,
      'pdf-extract': hasPdfModels
    };
  }, [allVisibleModels, visibleModels, currentModel]);

  // 拖拽处理
  const handleDragStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    setIsDragging(true);
    dragStartPosition.current = position;
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    dragStartX.current = clientX;
  }, [position]);

  const handleDragMove = useCallback((e: MouseEvent | TouchEvent) => {
    if (!isDragging) return;
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    setDragX(clientX);
    
    // 根据拖拽位置决定停靠侧
    const windowWidth = window.innerWidth;
    const threshold = windowWidth / 2;
    const newPosition = clientX < threshold ? 'left' : 'right';
    if (newPosition !== position) {
      setPosition(newPosition);
      onPositionChange?.(newPosition);
    }
  }, [isDragging, position, onPositionChange]);

  const handleDragEnd = useCallback(() => {
    setIsDragging(false);
    setDragX(null);
  }, []);

  // 绑定全局事件
  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleDragMove);
      window.addEventListener('mouseup', handleDragEnd);
      window.addEventListener('touchmove', handleDragMove);
      window.addEventListener('touchend', handleDragEnd);
    }
    return () => {
      window.removeEventListener('mousemove', handleDragMove);
      window.removeEventListener('mouseup', handleDragEnd);
      window.removeEventListener('touchmove', handleDragMove);
      window.removeEventListener('touchend', handleDragEnd);
    };
  }, [isDragging, handleDragMove, handleDragEnd]);

  // 切换位置
  const togglePosition = useCallback(() => {
    const newPosition = position === 'left' ? 'right' : 'left';
    setPosition(newPosition);
    onPositionChange?.(newPosition);
  }, [position, onPositionChange]);

  // 模式分组
  const modeGroups = useMemo(() => [
    { label: '基础', modes: MODE_CONFIG.filter(m => ['chat', 'deep-research', 'multi-agent'].includes(m.id)) },
    { label: '图片生成', modes: MODE_CONFIG.filter(m => m.id === 'image-gen') },
    { label: '图片编辑', modes: MODE_CONFIG.filter(m => ['image-chat-edit', 'image-mask-edit', 'image-inpainting', 'image-background-edit', 'image-recontext', 'virtual-try-on', 'image-outpainting'].includes(m.id)) },
    { label: '媒体', modes: MODE_CONFIG.filter(m => ['video-gen', 'audio-gen', 'pdf-extract'].includes(m.id)) },
  ], []);

  if (!isOpen) return null;

  const isLeft = position === 'left';

  return (
    <>
      {/* 移动端遮罩 */}
      <div 
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
        onClick={() => setIsOpen(false)}
      />

      {/* 侧边栏 */}
      <div
        ref={sidebarRef}
        className={`fixed inset-y-0 z-50 w-72 bg-slate-900 border-slate-800 transform transition-transform duration-300 ease-in-out flex flex-col ${
          isLeft 
            ? 'left-0 border-r' 
            : 'right-0 border-l'
        } ${isDragging ? 'cursor-grabbing shadow-2xl' : ''}`}
        style={isDragging && dragX !== null ? {
          transform: `translateX(${isLeft ? 0 : 0}px)`,
          opacity: 0.95,
        } : undefined}
      >
        {/* 头部 */}
        <div className="p-4 flex items-center justify-between border-b border-slate-800/50">
          {/* 拖拽手柄 */}
          <div 
            className="flex items-center gap-2 cursor-grab active:cursor-grabbing"
            onMouseDown={handleDragStart}
            onTouchStart={handleDragStart}
          >
            <GripVertical size={16} className="text-slate-500 hover:text-slate-300" />
            <span className="font-bold text-white">模式切换</span>
          </div>
          
          <div className="flex items-center gap-2">
            {/* 切换位置按钮 */}
            <button 
              onClick={togglePosition}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
              title={isLeft ? '移到右侧' : '移到左侧'}
            >
              {isLeft ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
            {/* 关闭按钮 */}
            <button 
              onClick={() => setIsOpen(false)} 
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* 模式列表 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
          {modeGroups.map((group) => (
            <div key={group.label} className="space-y-2">
              <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider px-1">
                {group.label}
              </div>
              <div className="space-y-1">
                {group.modes.map((mode) => {
                  const isActive = currentMode === mode.id;
                  const isDisabled = !modeAvailability[mode.id as keyof typeof modeAvailability];
                  const colors = COLOR_MAP[mode.color];
                  const Icon = mode.icon;
                  
                  return (
                    <button
                      key={mode.id}
                      onClick={() => !isDisabled && setMode(mode.id as AppMode)}
                      disabled={isDisabled}
                      className={`w-full flex items-center gap-3 p-2.5 rounded-xl transition-all text-left group ${
                        isDisabled
                          ? 'opacity-40 cursor-not-allowed'
                          : isActive
                            ? `${colors.bg} text-white shadow-lg`
                            : `bg-slate-800/40 hover:bg-slate-800 text-slate-300 hover:text-white border border-transparent hover:border-slate-700`
                      }`}
                    >
                      <div className={`p-2 rounded-lg transition-colors ${
                        isActive 
                          ? 'bg-white/20' 
                          : `bg-slate-800 ${colors.text} group-hover:${colors.bg} group-hover:text-white`
                      }`}>
                        <Icon size={16} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">{mode.label}</div>
                        <div className={`text-[10px] truncate ${isActive ? 'text-white/70' : 'text-slate-500'}`}>
                          {mode.description}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* 底部提示 */}
        <div className="p-4 border-t border-slate-800/50 bg-slate-900">
          <div className="text-[10px] text-slate-500 text-center">
            拖拽顶部可移动位置
          </div>
        </div>
      </div>

      {/* 拖拽时的位置指示器 */}
      {isDragging && (
        <div className="fixed inset-0 z-40 pointer-events-none">
          <div className={`absolute inset-y-0 w-1/2 transition-colors ${
            position === 'left' ? 'left-0 bg-indigo-500/10' : 'right-0 bg-indigo-500/10'
          }`} />
        </div>
      )}
    </>
  );
};

export default ModeNavigationSidebar;
