
import { ImageGenerationResult, VideoGenerationResult, AudioGenerationResult } from "../../interfaces";
import { Attachment, ChatOptions } from "../../../../types/types";
import { createGoogleClient } from "../utils";
import { generateTextToImage } from "./image-gen";
import { editImage } from "./image-edit";
import { generateVideo } from "./video";
import { generateSpeech } from "./audio";
import { virtualTryOn, segmentClothing, generateMaskAsync, editWithMask, getTryOnStatus } from "./virtual-tryon";
import type { SegmentationResult, TryOnOptions } from "./virtual-tryon";

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
