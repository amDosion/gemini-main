import { ModelConfig, AppMode } from '../types/types';

/**
 * 根据应用模式过滤模型列表
 * 
 * 这个函数统一了前端和后端的模型过滤逻辑，确保一致性。
 * 前端使用此函数进行客户端过滤，避免每次模式切换都调用 API。
 * 
 * @param models - 完整的模型列表
 * @param appMode - 应用模式
 * @returns 过滤后的模型列表
 */
export function filterModelsByAppMode(models: ModelConfig[], appMode: AppMode): ModelConfig[] {
    return models.filter(model => {
        const id = model.id.toLowerCase();
        const caps = model.capabilities;

        switch (appMode) {
            case 'video-gen':
                return id.includes('veo') || id.includes('sora') || id.includes('video') || id.includes('luma');
            
            case 'audio-gen':
                return id.includes('tts') || id.includes('audio') || id.includes('speech');
            
            case 'image-gen':
                if (id.includes('edit')) return false;
                const isSpecializedImageModel = id.includes('dall') || id.includes('wanx') || 
                                               id.includes('flux') || id.includes('midjourney') || 
                                               id.includes('-t2i') || id.includes('z-image') || 
                                               id.includes('imagen');
                const isGeminiWithImageGen = id.includes('gemini') && 
                                            (id.includes('image-generation') || id.includes('image-preview') || 
                                             id.includes('flash-image'));
                return isSpecializedImageModel || isGeminiWithImageGen;
            
            case 'image-chat-edit':
            case 'image-mask-edit':
            case 'image-inpainting':
            case 'image-background-edit':
            case 'image-recontext':
            case 'image-outpainting':
                if (!caps.vision || id.includes('veo')) return false;
                const isTextToImageOnly =
                    id.includes('wanx') || id.includes('-t2i') || id.includes('z-image-turbo') ||
                    id.includes('dall') || id.includes('flux') || id.includes('midjourney') ||
                    (id.startsWith('imagen-') && !id.includes('edit'));
                return !isTextToImageOnly;
            
            case 'virtual-try-on':
                return caps.vision && !id.includes('veo');
            
            case 'deep-research':
                return caps.search || caps.reasoning;
            
            case 'pdf-extract':
                const isPdfMediaModel = id.includes('veo') || id.includes('tts') || id.includes('wanx') || 
                                       id.includes('imagen') || id.includes('-t2i') || id.includes('z-image');
                const isPdfEmbeddingModel = id.includes('embedding') || id.includes('aqa');
                return !isPdfMediaModel && !isPdfEmbeddingModel;
            
            case 'chat':
            default:
                const isMediaModel = id.includes('veo') || id.includes('tts') || id.includes('wanx') || 
                                    id.includes('-t2i') || id.includes('z-image') || id.includes('imagen');
                const isEmbeddingModel = id.includes('embedding') || id.includes('aqa');
                return !isMediaModel && !isEmbeddingModel;
        }
    });
}
