
import { ImageGenerationResult, VideoGenerationResult, AudioGenerationResult } from "../../interfaces";
import { Attachment, ChatOptions } from "../../../../../types";
import { createGoogleClient } from "../utils";
import { generateTextToImage } from "./image-gen";
import { editImage } from "./image-edit";
import { generateVideo } from "./video";
import { generateSpeech } from "./audio";

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
            return editImage(ai, modelId, prompt, referenceImages, options);
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
    }
};
