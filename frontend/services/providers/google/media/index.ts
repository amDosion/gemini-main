/**
 * @deprecated 此文件已废弃，请使用 UnifiedProviderClient 代替
 * 
 * Google Media Strategy - 已统一到 UnifiedProviderClient
 * 
 * 新架构: 所有 Provider 统一使用 UnifiedProviderClient，通过后端统一路由处理
 * - 图片生成: UnifiedProviderClient('google').executeMode('image-gen', ...)
 * - 图片编辑: UnifiedProviderClient('google').executeMode('image-edit', ...)
 * - 视频生成: UnifiedProviderClient('google').executeMode('video-gen', ...)
 * - 音频生成: UnifiedProviderClient('google').executeMode('audio-gen', ...)
 * - 虚拟试穿: UnifiedProviderClient('google').executeMode('virtual-try-on', ...)
 * 
 * 迁移指南:
 * - 使用 UnifiedProviderClient 代替 googleMediaStrategy
 * - 所有功能都通过后端统一处理，无需前端直接调用 Google SDK
 */

import { ImageGenerationResult, VideoGenerationResult, AudioGenerationResult } from "../../interfaces";
import { Attachment, ChatOptions } from "../../../../types/types";
import { createGoogleClient } from "../utils"; // 保留用于向后兼容
import { generateTextToImage } from "./image-gen"; // 保留用于向后兼容
import { editImage } from "./image-edit"; // 保留用于向后兼容
import { generateVideo } from "./video"; // 保留用于向后兼容
import { generateSpeech } from "./audio"; // 保留用于向后兼容
import { virtualTryOn, segmentClothing, generateMaskAsync, editWithMask, getTryOnStatus } from "./virtual-tryon"; // 保留用于向后兼容
import type { SegmentationResult, TryOnOptions } from "./virtual-tryon";

/**
 * @deprecated 使用 UnifiedProviderClient('google') 代替
 */
export const googleMediaStrategy = {
    generateImage: async (
        modelId: string, 
        prompt: string, 
        referenceImages: Attachment[], 
        options: ChatOptions, 
        apiKey: string, 
        baseUrl: string
    ): Promise<ImageGenerationResult[]> => {
        const ai = createGoogleClient(apiKey, baseUrl);
        const isEdit = referenceImages && referenceImages.length > 0;
        
        if (isEdit) {
            // 传递 apiKey 和 baseUrl 以支持 Google Files API
            return editImage(ai, modelId, prompt, referenceImages, options, apiKey, baseUrl);
        } else {
            return generateTextToImage(ai, modelId, prompt, options);
        }
    },

    generateVideo: async (
        prompt: string, 
        referenceImages: Attachment[], 
        options: ChatOptions, 
        apiKey: string, 
        baseUrl: string
    ): Promise<VideoGenerationResult> => {
        const ai = createGoogleClient(apiKey, baseUrl);
        return generateVideo(ai, prompt, referenceImages, options, apiKey);
    },

    generateSpeech: async (
        text: string, 
        voiceName: string, 
        apiKey: string, 
        baseUrl: string
    ): Promise<AudioGenerationResult> => {
        const ai = createGoogleClient(apiKey, baseUrl);
        return generateSpeech(ai, text, voiceName);
    },

    /**
     * Virtual Try-On 服装虚拟试穿
     */
    virtualTryOn: async (
        referenceImage: Attachment,
        options: TryOnOptions,
        apiKey: string,
        baseUrl: string
    ): Promise<ImageGenerationResult> => {
        const ai = createGoogleClient(apiKey, baseUrl);
        return virtualTryOn(ai, referenceImage, options, apiKey);
    },

    /**
     * 服装分割
     */
    segmentClothing: async (
        image: Attachment,
        targetClothing: string,
        apiKey: string,
        baseUrl: string,
        modelId?: string
    ): Promise<SegmentationResult[]> => {
        const ai = createGoogleClient(apiKey, baseUrl);
        return segmentClothing(ai, image, targetClothing, modelId);
    },

    /**
     * 生成掩码
     */
    generateMask: generateMaskAsync,

    /**
     * 掩码编辑
     */
    editWithMask: editWithMask,

    /**
     * 获取 Try-On 服务状态
     */
    getTryOnStatus: getTryOnStatus
};

// 导出类型
export type { SegmentationResult, TryOnOptions };
