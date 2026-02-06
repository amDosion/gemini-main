import { ModelConfig, AppMode } from '../types/types';

/**
 * Vertex AI 专用模型分类
 *
 * 基于 Google 官方 SDK 文档定义的模型分类规则：
 * - 图像生成 (image-gen): imagen-*-generate-*, gemini-*-image-*
 * - 图像编辑 (image-edit): imagen-3.0-capability-001, imagen-4.0-ingredients-preview
 * - 图像放大 (image-upscale): imagen-4.0-upscale-preview
 * - 图像分割 (image-segmentation): image-segmentation-001
 * - 虚拟试衣 (virtual-try-on): virtual-try-on-*, virtual-try-on-preview-*
 * - 产品重构 (product-recontext): imagen-product-recontext-*
 */

// Imagen 图像生成模型（纯文生图，不支持编辑）
const IMAGEN_GENERATE_MODELS = [
    'imagen-3.0-generate-001',
    'imagen-3.0-generate-002',
    'imagen-3.0-fast-generate-001',
    'imagen-4.0-generate-preview',
    'imagen-4.0-ultra-generate-preview',
    'imagen-4.0-generate-001',           // ✅ 新增
    'imagen-4.0-ultra-generate-001',     // ✅ 新增
    'imagen-4.0-fast-generate-001',      // ✅ 新增
];

// Imagen 图像编辑模型（支持 mask 编辑、背景替换等）
const IMAGEN_EDIT_MODELS = [
    'imagen-3.0-capability-001',      // 主要编辑模型
    'imagen-4.0-ingredients-preview', // 高级编辑模型
];

// 图像放大模型
const IMAGE_UPSCALE_MODELS = [
    'imagen-4.0-upscale-preview',
];

// 图像分割模型
const IMAGE_SEGMENTATION_MODELS = [
    'image-segmentation-001',
];

// 虚拟试衣模型
const VIRTUAL_TRY_ON_MODELS = [
    'virtual-try-on-001',
    'virtual-try-on-preview-08-04',
];

// 产品重构模型
const PRODUCT_RECONTEXT_MODELS = [
    'imagen-product-recontext-preview-06-30',
];

/**
 * 检查模型是否匹配静态模型列表（支持前缀匹配）
 */
function matchesModelList(modelId: string, modelList: string[]): boolean {
    const lowerId = modelId.toLowerCase();
    return modelList.some(m => {
        const lowerM = m.toLowerCase();
        // 精确匹配或前缀匹配（处理版本号后缀）
        return lowerId === lowerM || lowerId.startsWith(lowerM.replace(/-\d+$/, ''));
    });
}

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
                // 排除编辑模型
                if (matchesModelList(model.id, IMAGEN_EDIT_MODELS)) return false;
                // 排除放大模型
                if (matchesModelList(model.id, IMAGE_UPSCALE_MODELS)) return false;
                // 排除分割模型
                if (matchesModelList(model.id, IMAGE_SEGMENTATION_MODELS)) return false;
                // 排除虚拟试衣模型
                if (matchesModelList(model.id, VIRTUAL_TRY_ON_MODELS)) return false;
                // 排除产品重构模型
                if (matchesModelList(model.id, PRODUCT_RECONTEXT_MODELS)) return false;
                // 排除通用编辑关键词
                if (id.includes('edit')) return false;

                // 包含 Imagen 生成模型
                if (matchesModelList(model.id, IMAGEN_GENERATE_MODELS)) return true;
                // 包含通用图像生成模型
                const isSpecializedImageModel = id.includes('dall') || id.includes('wanx') ||
                                               id.includes('flux') || id.includes('midjourney') ||
                                               id.includes('-t2i') || id.includes('z-image') ||
                                               (id.includes('imagen') && id.includes('generate'));
                // ✅ 支持 Gemini Image 模型
                const isGeminiImageModel = id.includes('gemini') && id.includes('image');
                // ✅ 支持 Nano-Banana 系列
                const isNanoBananaModel = id.includes('nano-banana');
                return isSpecializedImageModel || isGeminiImageModel || isNanoBananaModel;

            case 'image-upscale':
                // 图像放大模式：只包含放大模型
                return matchesModelList(model.id, IMAGE_UPSCALE_MODELS) || id.includes('upscale');

            case 'image-segmentation':
                // 图像分割模式：只包含分割模型
                return matchesModelList(model.id, IMAGE_SEGMENTATION_MODELS) || id.includes('segmentation');

            case 'product-recontext':
                // 产品重构模式
                return matchesModelList(model.id, PRODUCT_RECONTEXT_MODELS) || id.includes('recontext');

            case 'image-chat-edit':
            case 'image-mask-edit':
            case 'image-inpainting':
            case 'image-background-edit':
            case 'image-recontext':
                // 图像编辑模式：支持 Imagen 编辑模型 + Gemini 视觉模型
                // ✅ 明确包含 Imagen 编辑专用模型
                if (matchesModelList(model.id, IMAGEN_EDIT_MODELS)) return true;

                // ✅ 明确包含图像分割模型（自动 mask 功能需要）
                if (matchesModelList(model.id, IMAGE_SEGMENTATION_MODELS)) return true;

                // ✅ 明确包含虚拟试衣模型
                if (matchesModelList(model.id, VIRTUAL_TRY_ON_MODELS)) return true;

                // ✅ 明确包含产品重构模型（背景编辑需要）
                if (appMode === 'image-background-edit' || appMode === 'image-recontext') {
                    if (matchesModelList(model.id, PRODUCT_RECONTEXT_MODELS)) return true;
                }

                // 排除视频模型
                if (id.includes('veo')) return false;
                // 需要视觉能力
                if (!caps.vision) return false;
                // 排除纯文生图模型
                const isTextToImageOnly =
                    id.includes('wanx') || id.includes('-t2i') || id.includes('z-image-turbo') ||
                    id.includes('dall') || id.includes('flux') || id.includes('midjourney') ||
                    matchesModelList(model.id, IMAGEN_GENERATE_MODELS) ||
                    matchesModelList(model.id, IMAGE_UPSCALE_MODELS);
                return !isTextToImageOnly;

            case 'image-outpainting':
                // 图像扩展模式：支持编辑模型（扩图）+ 放大模型（upscale 子模式）
                // ✅ 包含编辑模型（用于 ratio, scale, offset 子模式）
                if (matchesModelList(model.id, IMAGEN_EDIT_MODELS)) return true;

                // ✅ 包含放大模型（用于 upscale 子模式）
                if (matchesModelList(model.id, IMAGE_UPSCALE_MODELS)) return true;

                // ✅ 包含图像分割模型
                if (matchesModelList(model.id, IMAGE_SEGMENTATION_MODELS)) return true;

                // 排除视频模型
                if (id.includes('veo')) return false;
                // 需要视觉能力
                if (!caps.vision) return false;
                // 排除纯文生图模型
                const isOutpaintTextToImageOnly =
                    id.includes('wanx') || id.includes('-t2i') || id.includes('z-image-turbo') ||
                    id.includes('dall') || id.includes('flux') || id.includes('midjourney') ||
                    matchesModelList(model.id, IMAGEN_GENERATE_MODELS);
                return !isOutpaintTextToImageOnly;

            case 'virtual-try-on':
                // 虚拟试衣模式：优先虚拟试衣专用模型
                if (matchesModelList(model.id, VIRTUAL_TRY_ON_MODELS)) return true;
                if (id.includes('try-on') || id.includes('tryon')) return true;
                // 回退到有视觉能力的模型（排除视频/放大等）
                return caps.vision && !id.includes('veo') &&
                       !matchesModelList(model.id, IMAGE_UPSCALE_MODELS) &&
                       !matchesModelList(model.id, IMAGE_SEGMENTATION_MODELS);

            case 'deep-research':
                return caps.search || caps.reasoning;

            case 'pdf-extract':
                const isPdfMediaModel = id.includes('veo') || id.includes('tts') || id.includes('wanx') ||
                                       id.includes('imagen') || id.includes('-t2i') || id.includes('z-image') ||
                                       id.includes('segmentation') || id.includes('upscale') || id.includes('try-on');
                const isPdfEmbeddingModel = id.includes('embedding') || id.includes('aqa');
                return !isPdfMediaModel && !isPdfEmbeddingModel;

            case 'chat':
            default:
                // 聊天模式：排除所有专用媒体模型
                const isMediaModel = id.includes('veo') || id.includes('tts') || id.includes('wanx') ||
                                    id.includes('-t2i') || id.includes('z-image') || id.includes('imagen') ||
                                    id.includes('segmentation') || id.includes('upscale') || id.includes('try-on') ||
                                    id.includes('recontext');
                const isEmbeddingModel = id.includes('embedding') || id.includes('aqa');
                return !isMediaModel && !isEmbeddingModel;
        }
    });
}
