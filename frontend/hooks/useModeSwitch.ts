
import { useCallback, Dispatch, SetStateAction } from 'react';
import { AppMode, ModelConfig } from '../types/types';

interface UseModeSwitchProps {
  visibleModels: ModelConfig[];
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
  visibleModels,
  currentModelId,
  setCurrentModelId,
  setAppMode
}: UseModeSwitchProps): UseModeSwitchReturn => {
  const handleModeSwitch = useCallback((mode: AppMode) => {
    setAppMode(mode);
    if (mode === 'image-gen') {
      // 优先选择专门的图像生成模型
      let imageModel = visibleModels.find(m => m.id.toLowerCase().includes('imagen'));
      if (!imageModel) {
        // 其次选择 Gemini 2.0+ 支持原生图像生成的模型
        imageModel = visibleModels.find(m => {
          const id = m.id.toLowerCase();
          return (id.includes('gemini-2') || id.includes('gemini-3')) &&
            (id.includes('flash') || id.includes('pro'));
        })
          || visibleModels.find(m => m.id === 'gemini-2.5-flash-image')
          || visibleModels.find(m => m.id.includes('image'))
          || visibleModels.find(m => m.capabilities.vision);
      }
      if (imageModel) setCurrentModelId(imageModel.id);
    } else if (IMAGE_EDIT_MODES.includes(mode) || mode === 'image-outpainting') {
      const imageModel = visibleModels.find(m => m.capabilities.vision && !m.id.includes('imagen'));
      if (imageModel) setCurrentModelId(imageModel.id);
    } else if (mode === 'video-gen') {
      const videoModel = visibleModels.find(m => m.id.includes('veo'));
      if (videoModel) setCurrentModelId(videoModel.id);
    } else if (mode === 'pdf-extract') {
      // PDF extraction works with most models that support function calling
      // Prefer reasoning-capable models, but allow any compatible model
      const pdfModel = visibleModels.find(m =>
        m.capabilities.reasoning && !m.id.includes('veo') && !m.id.includes('tts')
      ) || visibleModels.find(m =>
        !m.id.includes('veo') && !m.id.includes('tts') && !m.id.includes('wanx')
      );

      // Only switch if current model is incompatible (e.g. Veo, TTS, Image Gen)
      if (pdfModel && !visibleModels.find(m =>
        m.id === currentModelId && !m.id.includes('veo') && !m.id.includes('tts')
      )) {
        setCurrentModelId(pdfModel.id);
      }
    }
  }, [visibleModels, setCurrentModelId, currentModelId, setAppMode]);

  return { handleModeSwitch };
};
