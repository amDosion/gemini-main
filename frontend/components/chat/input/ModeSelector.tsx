
import React, { useMemo } from 'react';
import { MessageSquare, Wand2, Crop, Expand, PlaySquare, Mic, FileText, Shirt, Search } from 'lucide-react';
import { AppMode, ModelConfig } from '../../../types/types';

interface ModeSelectorProps {
  mode: AppMode;
  setMode: (mode: AppMode) => void;
  currentModel?: ModelConfig;
  visibleModels?: ModelConfig[];  // 新增：所有可见模型列表，用于判断模式可用性
}

export const ModeSelector: React.FC<ModeSelectorProps> = ({ mode, setMode, currentModel, visibleModels = [] }) => {
  // 基于 visibleModels 计算每个模式是否有兼容的模型
  const modeAvailability = useMemo(() => {
    const models = visibleModels.length > 0 ? visibleModels : (currentModel ? [currentModel] : []);
    
    // 检查是否有文生图模型
    // 1. 专门的图像生成模型（通过 ID 关键词识别）
    // 2. Gemini 2.0+ 模型支持原生图像生成（gemini-2.0-flash-exp 等）
    const hasImageGenModels = models.some(m => {
      const id = m.id.toLowerCase();
      // 专门的图像生成模型
      const isImageGenModel = id.includes('dall') || id.includes('wanx') || id.includes('flux') || 
             id.includes('midjourney') || id.includes('-t2i') || id.includes('z-image') || 
             id.includes('imagen');
      // Gemini 2.0+ 支持原生图像生成
      const isGeminiImageCapable = (id.includes('gemini-2') || id.includes('gemini-3')) && 
             (id.includes('flash') || id.includes('pro'));
      return isImageGenModel || isGeminiImageCapable;
    });
    
    // 检查是否有视觉理解模型（用于图像编辑等）
    const hasVisionModels = models.some(m => {
      const id = m.id.toLowerCase();
      return m.capabilities.vision && !id.includes('veo');
    });
    
    // 检查是否有深度研究模型
    const hasDeepResearchModels = models.some(m => {
      const name = (m.name || m.id || '').toLowerCase();
      return name.includes('deep-research') || name.includes('deep research') || name.includes('deepresearch');
    });
    
    // 检查是否有视频生成模型
    const hasVideoModels = models.some(m => {
      const id = m.id.toLowerCase();
      return id.includes('veo') || id.includes('sora') || id.includes('video') || id.includes('luma');
    });
    
    // 检查是否有音频生成模型
    const hasAudioModels = models.some(m => {
      const id = m.id.toLowerCase();
      return id.includes('tts') || id.includes('audio') || id.includes('speech');
    });
    
    // 检查是否有 PDF 提取兼容模型
    const hasPdfModels = models.some(m => {
      const id = m.id.toLowerCase();
      return !id.includes('veo') && !id.includes('tts') && !id.includes('wanx') && 
             !id.includes('imagen') && !id.includes('-t2i') && !id.includes('z-image');
    });
    
    return {
      chat: true,  // Chat 模式始终可用
      'deep-research': hasDeepResearchModels,
      'image-gen': hasImageGenModels,
      'image-edit': hasVisionModels || hasImageGenModels,  // 编辑模式需要视觉或图像模型
      'virtual-try-on': hasVisionModels,
      'image-outpainting': true,  // Outpainting 使用特定 API，始终可用
      'video-gen': hasVideoModels,
      'audio-gen': hasAudioModels || true,  // 音频通常有默认支持
      'pdf-extract': hasPdfModels
    };
  }, [visibleModels, currentModel]);

  const modes = [
    { id: 'chat', label: 'Chat', icon: MessageSquare, disabled: !modeAvailability.chat, color: 'bg-indigo-600' },
    { id: 'deep-research', label: 'Research', icon: Search, disabled: !modeAvailability['deep-research'], color: 'bg-blue-600' },
    { id: 'image-gen', label: 'Gen', icon: Wand2, disabled: !modeAvailability['image-gen'], color: 'bg-emerald-600' },
    { id: 'image-edit', label: 'Edit', icon: Crop, disabled: !modeAvailability['image-edit'], color: 'bg-pink-600' },
    { id: 'virtual-try-on', label: 'Try-On', icon: Shirt, disabled: !modeAvailability['virtual-try-on'], color: 'bg-rose-600' },
    { id: 'image-outpainting', label: 'Expand', icon: Expand, disabled: !modeAvailability['image-outpainting'], color: 'bg-orange-600' },
    { id: 'video-gen', label: 'Video', icon: PlaySquare, disabled: !modeAvailability['video-gen'], color: 'bg-indigo-500' },
    { id: 'audio-gen', label: 'Audio', icon: Mic, disabled: !modeAvailability['audio-gen'], color: 'bg-cyan-600' },
    { id: 'pdf-extract', label: 'PDF', icon: FileText, disabled: !modeAvailability['pdf-extract'], color: 'bg-purple-600' },
  ];

  return (
    <div className="flex items-center gap-1 bg-slate-900/60 p-1 rounded-full border border-slate-700/50 backdrop-blur-md overflow-x-auto max-w-full custom-scrollbar shadow-sm">
      {modes.map((m) => (
        <button
          key={m.id}
          onClick={() => setMode(m.id as AppMode)}
          disabled={m.disabled}
          className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-all flex items-center gap-1.5 whitespace-nowrap ${m.disabled
            ? 'opacity-40 cursor-not-allowed text-slate-500'
            : mode === m.id
              ? `${m.color} text-white shadow-md ring-1 ring-white/10`
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
        >
          <m.icon size={13} strokeWidth={2.5} /> {m.label}
        </button>
      ))}
    </div>
  );
};
