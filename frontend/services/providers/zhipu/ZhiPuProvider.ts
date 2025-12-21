
import { OpenAIProvider } from "../openai/OpenAIProvider";
import { ModelConfig, ChatOptions, Attachment } from "../../../types/types";
import { ImageGenerationResult } from "../interfaces";
import { getZhiPuModels } from "./models";

export class ZhiPuProvider extends OpenAIProvider {
    public id = 'zhipu';

    public async getAvailableModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
        return getZhiPuModels(apiKey, baseUrl);
    }

    // Override generateImage to use CogView-3 if selected or fallback to standard OpenAI format
    public async generateImage(
        modelId: string, 
        prompt: string, 
        referenceImages: Attachment[], 
        options: ChatOptions, 
        apiKey: string, 
        baseUrl: string
    ): Promise<ImageGenerationResult[]> {
        // If the model is specifically CogView, we might need specific payload structure
        // ZhiPu OpenAI compat usually handles standard DALL-E format mapping automatically.
        return super.generateImage("cogview-3-plus", prompt, referenceImages, options, apiKey, baseUrl);
    }
}
