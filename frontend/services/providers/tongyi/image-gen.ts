
import { ImageGenerationResult } from "../interfaces";
import { ChatOptions } from "../../../types/types";
import { resolveDashUrl, submitAndPoll } from "./api";

// --- RESOLUTION MAPPING LOGIC ---
function getQwenResolution(aspectRatio: string): string {
    switch (aspectRatio) {
        case '16:9': return "1664*928";
        case '9:16': return "928*1664";
        case '4:3':  return "1472*1140";
        case '3:4':  return "1140*1472";
        case '1:1':  
        default:     return "1328*1328"; 
    }
}

function getWanxV1Resolution(aspectRatio: string, resolution: string): string {
    switch (aspectRatio) {
        case '16:9': return "1280*720";
        case '9:16': return "720*1280";
        case '4:3':  return "1024*768";
        case '3:4':  return "768*1024";
        case '1:1':  
        default:     return "1024*1024";
    }
}

// WanX V2 supports strict sizes like "1024*1024", "720*1280", "1280*720"
function getWanxV2Resolution(aspectRatio: string): string {
    switch (aspectRatio) {
        case '16:9': return "1280*720";
        case '9:16': return "720*1280";
        default:     return "1024*1024";
    }
}

// --- Text to Image (Main Entry) ---
export async function generateDashScopeImage(
    modelId: string,
    prompt: string,
    options: ChatOptions,
    apiKey: string,
    baseUrl?: string
): Promise<ImageGenerationResult[]> {
    
    // Detect Model Type
    const isQwen = modelId.includes('qwen');
    const isWanxV2 = modelId === 'wanx-v2';
    const isWanxV1 = !isQwen && !isWanxV2; // Fallback to Wanx V1

    const input: any = { prompt: prompt };
    const parameters: any = {};

    // --- Qwen-Image-Plus ---
    if (isQwen) {
        parameters.size = getQwenResolution(options.imageAspectRatio);
        parameters.n = Math.min(Math.max(options.numberOfImages || 1, 1), 4);
        parameters.prompt_extend = true;
        if (options.negativePrompt) input.negative_prompt = options.negativePrompt;
        parameters.watermark = false; 
    } 
    // --- Wanx V2 ---
    else if (isWanxV2) {
        parameters.size = getWanxV2Resolution(options.imageAspectRatio);
        parameters.n = Math.min(Math.max(options.numberOfImages || 1, 1), 4);
        if (options.seed && options.seed > -1) parameters.seed = options.seed;
        
        // Wanx V2 style_type support
        if (options.imageStyle && options.imageStyle !== 'None') {
             // Map UI styles to Wanx V2 specific strings if needed, 
             // or pass through if UI matches API (e.g. "Anime", "Photorealistic")
             parameters.style_type = options.imageStyle; 
        }
    }
    // --- Wanx V1 ---
    else {
        parameters.size = getWanxV1Resolution(options.imageAspectRatio, options.imageResolution);
        parameters.n = Math.min(Math.max(options.numberOfImages || 1, 1), 4);

        if (options.imageStyle && options.imageStyle !== 'None') {
            const styleMap: Record<string, string> = {
                'Photorealistic': '<photography>',
                'Anime': '<anime>',
                'Oil Painting': '<oil painting>',
                'Watercolor': '<watercolor>',
                'Digital Art': '<3d cartoon>'
            };
            parameters.style = styleMap[options.imageStyle] || '<auto>';
        } else {
            parameters.style = '<auto>';
        }
        
        if (options.negativePrompt) {
            input.negative_prompt = options.negativePrompt;
        }
    }

    const payload = {
        model: modelId,
        input: input,
        parameters: parameters
    };

    // Route dynamically based on model
    const url = resolveDashUrl(baseUrl || '', 'image-generation', modelId);
    
    const result = await submitAndPoll(url, payload, apiKey);
    
    return [result];
}
