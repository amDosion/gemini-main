/**
 * 内嵌模式导航组件
 * 
 * 功能：
 * - 固定显示在工作区右侧
 * - 显示所有可用模式
 * - 根据模型能力动态启用/禁用模式
 * - 用于 AppLayout 的插槽
 */
import React, { useMemo } from 'react';
import { 
  MessageSquare, Wand2, Crop, Expand, PlaySquare, Mic, FileText, 
  Shirt, Search, Network, Layers, Sparkles, LayoutGrid
} from 'lucide-react';
import { AppMode, ModelConfig } from '../../types/types';

interface InlineModeNavigationProps {
  currentMode: AppMode;
  setMode: (mode: AppMode) => void;
  currentModel?: ModelConfig;
  visibleModels?: ModelConfig[];
  allVisibleModels?: ModelConfig[];
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
const COLOR_MAP: Record<string, { bg: string; text: string }> = {
  indigo: { bg: 'bg-indigo-600', text: 'text-indigo-400' },
  blue: { bg: 'bg-blue-600', text: 'text-blue-400' },
  teal: { bg: 'bg-teal-600', text: 'text-teal-400' },
  emerald: { bg: 'bg-emerald-600', text: 'text-emerald-400' },
  pink: { bg: 'bg-pink-600', text: 'text-pink-400' },
  rose: { bg: 'bg-rose-600', text: 'text-rose-400' },
  orange: { bg: 'bg-orange-600', text: 'text-orange-400' },
  cyan: { bg: 'bg-cyan-600', text: 'text-cyan-400' },
  purple: { bg: 'bg-purple-600', text: 'text-purple-400' },
};

// 模式分组
const MODE_GROUPS = [
  { label: '基础', modes: ['chat', 'deep-research', 'multi-agent'] },
  { label: '图片生成', modes: ['image-gen'] },
  { label: '图片编辑', modes: ['image-chat-edit', 'image-mask-edit', 'image-inpainting', 'image-background-edit', 'image-recontext', 'virtual-try-on', 'image-outpainting'] },
  { label: '媒体', modes: ['video-gen', 'audio-gen', 'pdf-extract'] },
];

export const InlineModeNavigation: React.FC<InlineModeNavigationProps> = ({
  currentMode,
  setMode,
  currentModel,
  visibleModels = [],
  allVisibleModels = [],
}) => {
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

  // 获取分组后的模式
  const groupedModes = useMemo(() => {
    return MODE_GROUPS.map(group => ({
      ...group,
      modes: MODE_CONFIG.filter(m => group.modes.includes(m.id))
    }));
  }, []);

  return (
    <div className="w-56 flex-shrink-0 border-l border-slate-800 bg-slate-900/30 flex flex-col h-full overflow-hidden">
      {/* 头部 */}
      <div className="px-3 py-3 border-b border-slate-800/50">
        <div className="flex items-center gap-2">
          <LayoutGrid size={14} className="text-indigo-400" />
          <span className="text-xs font-bold text-white">模式切换</span>
        </div>
      </div>

      {/* 模式列表 */}
      <div className="flex-1 overflow-y-auto p-2 space-y-3 custom-scrollbar">
        {groupedModes.map((group) => (
          <div key={group.label} className="space-y-1">
            <div className="text-[9px] font-bold text-slate-500 uppercase tracking-wider px-2">
              {group.label}
            </div>
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
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs transition-all ${
                    isDisabled
                      ? 'opacity-40 cursor-not-allowed text-slate-500'
                      : isActive
                        ? `${colors.bg} text-white`
                        : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Icon size={14} />
                  <span className="truncate">{mode.label}</span>
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
};

export default InlineModeNavigation;
