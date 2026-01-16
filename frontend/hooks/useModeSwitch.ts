
import { useCallback, Dispatch, SetStateAction } from 'react';
import { AppMode, ModelConfig } from '../types/types';
import { filterModelsByAppMode } from '../utils/modelFilter';

interface UseModeSwitchProps {
  availableModels: ModelConfig[];
  hiddenModelIds: string[];
  currentModelId: string | null;
  setCurrentModelId: (id: string) => void;
  setAppMode: Dispatch<SetStateAction<AppMode>>;
}

interface UseModeSwitchReturn {
  handleModeSwitch: (mode: AppMode) => void;
}

// 图片编辑模式列表
const IMAGE_EDIT_MODES: AppMode[] = [
  'image-chat-edit',
  'image-mask-edit',
  'image-inpainting',
  'image-background-edit',
  'image-recontext'
];

/**
 * 模式切换 Hook
 * 根据模式自动选择合适的模型
 */
export const useModeSwitch = ({
  availableModels,
  hiddenModelIds,
  currentModelId,
  setCurrentModelId,
  setAppMode
}: UseModeSwitchProps): UseModeSwitchReturn => {
  const handleModeSwitch = useCallback((mode: AppMode) => {
    // ✅ 根据新的 mode 过滤模型（不依赖旧的 visibleModels）
    const modeFiltered = filterModelsByAppMode(availableModels, mode);
    const visible = modeFiltered.filter(m => !hiddenModelIds.includes(m.id));
    
    setAppMode(mode);
    if (mode === 'image-gen') {
      // 优先选择专门的图像生成模型
      let imageModel = visible.find(m => m.id.toLowerCase().includes('imagen'));
      if (!imageModel) {
        // 其次选择 Gemini 2.0+ 支持原生图像生成的模型
        imageModel = visible.find(m => {
          const id = m.id.toLowerCase();
          return (id.includes('gemini-2') || id.includes('gemini-3')) &&
            (id.includes('flash') || id.includes('pro'));
        })
          || visible.find(m => m.id === 'gemini-2.5-flash-image')
          || visible.find(m => m.id.includes('image'))
          || visible.find(m => m.capabilities.vision);
      }
      if (imageModel) {
        setCurrentModelId(imageModel.id);
      }
    } else if (IMAGE_EDIT_MODES.includes(mode) || mode === 'image-outpainting') {
      const imageModel = visible.find(m => m.capabilities.vision && !m.id.includes('imagen'));
      if (imageModel) {
        setCurrentModelId(imageModel.id);
      }
    } else if (mode === 'video-gen') {
      const videoModel = visible.find(m => m.id.includes('veo'));
      if (videoModel) {
        setCurrentModelId(videoModel.id);
      }
    } else if (mode === 'pdf-extract') {
      // PDF extraction works with most models that support function calling
      // Prefer reasoning-capable models, but allow any compatible model
      const pdfModel = visible.find(m =>
        m.capabilities.reasoning && !m.id.includes('veo') && !m.id.includes('tts')
      ) || visible.find(m =>
        !m.id.includes('veo') && !m.id.includes('tts') && !m.id.includes('wanx')
      );

      // Only switch if current model is incompatible (e.g. Veo, TTS, Image Gen)
      if (pdfModel && !visible.find(m =>
        m.id === currentModelId && !m.id.includes('veo') && !m.id.includes('tts')
      )) {
        setCurrentModelId(pdfModel.id);
      }
    } else if (mode === 'audio-gen') {
      // 优先选择专门的音频生成模型
      const audioModel = visible.find(m => {
        const id = m.id.toLowerCase();
        return id.includes('tts') || id.includes('audio') || id.includes('speech');
      });
      if (audioModel) {
        setCurrentModelId(audioModel.id);
      }
    } else if (mode === 'virtual-try-on') {
      // 选择有 vision 能力且不包含 'veo' 的模型
      const tryOnModel = visible.find(m => m.capabilities.vision && !m.id.includes('veo'));
      if (tryOnModel) {
        setCurrentModelId(tryOnModel.id);
      }
    } else if (mode === 'deep-research') {
      // 优先选择有 search 能力的模型，其次选择有 reasoning 能力的模型
      const researchModel = visible.find(m => m.capabilities.search) ||
                           visible.find(m => m.capabilities.reasoning) ||
                           visible.find(m => {
                             const name = (m.name || m.id || '').toLowerCase();
                             return name.includes('deep-research') || name.includes('deep research') || name.includes('deepresearch');
                           });
      if (researchModel) {
        setCurrentModelId(researchModel.id);
      }
    } else if (mode === 'multi-agent') {
      // Multi-Agent 模式使用工作流编排，可以选择支持 function calling 的模型
      // 优先选择有 reasoning 能力的模型
      const multiAgentModel = visible.find(m => m.capabilities.reasoning) ||
                             visible.find(m => m.capabilities.search);
      if (multiAgentModel) {
        setCurrentModelId(multiAgentModel.id);
      }
    } else if (mode === 'chat') {
      // Chat 模式：优先选择通用对话模型
      // 如果当前模型在 chat 模式下可用，保留选择
      const isCurrentModelVisible = currentModelId && visible.find(m => m.id === currentModelId);
      if (!isCurrentModelVisible && visible.length > 0) {
        // 优先选择 flash 或 pro 模型
        const chatModel = visible.find(m => {
          const id = m.id.toLowerCase();
          return id.includes('flash') || id.includes('pro');
        }) || visible[0];
        if (chatModel) {
          setCurrentModelId(chatModel.id);
        }
      }
    }
  }, [availableModels, hiddenModelIds, setCurrentModelId, currentModelId, setAppMode]);

  return { handleModeSwitch };
};
