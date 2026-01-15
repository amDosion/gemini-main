
import { ImageGenerationResult } from "../interfaces";
import { Attachment, ChatOptions } from "../../../types/types";
import { resolveDashUrl, uploadDashScopeFile, submitAndPoll } from "./api";

// --- Helper: Process Reference Image ---
async function ensureRemoteUrl(attachment: Attachment, apiKey: string, baseUrl?: string): Promise<string> {
    let imageUrl = attachment.url;
    if (!imageUrl && !attachment.file) throw new Error("Reference image required.");

    if (imageUrl?.startsWith('blob:') || imageUrl?.startsWith('data:') || attachment.file) {
        let fileToUpload = attachment.file;
        if (!fileToUpload && imageUrl) {
             const res = await fetch(imageUrl);
             const blob = await res.blob();
             fileToUpload = new File([blob], "temp_image.png", { type: blob.type });
        }
        if (fileToUpload) {
            imageUrl = await uploadDashScopeFile(fileToUpload, apiKey, baseUrl);
        }
    }
    if (!imageUrl) throw new Error("Failed to process image for DashScope.");
    return imageUrl;
}

// --- RESOLUTION MAPPING LOGIC ---
function getQwenResolution(aspectRatio: string): string {
    // Qwen-Image-Plus strictly supports only these 5 resolutions
    switch (aspectRatio) {
        case '16:9': return "1664*928";
        case '9:16': return "928*1664";
        case '4:3':  return "1472*1140";
        case '3:4':  return "1140*1472";
        case '1:1':  
        default:     return "1328*1328"; // Default per docs
    }
}

function getWanxResolution(aspectRatio: string, resolution: string): string {
    // Wanx V2 allows flexible [512-1440]. Wanx V1 is fixed 1024*1024.
    // We assume V2 usage for better quality if model ID isn't explicitly V1.
    
    // Simple presets for Wanx based on ratio
    switch (aspectRatio) {
        case '16:9': return "1280*720";
        case '9:16': return "720*1280";
        case '4:3':  return "1024*768";
        case '3:4':  return "768*1024";
        case '1:1':  
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
    
    const isQwen = modelId.includes('qwen');
    const isWanx = modelId.includes('wan'); // Matches wanx-v1, wan2.1, etc.

    // 1. Prepare Parameters based on Model Type
    const input: any = { prompt: prompt };
    const parameters: any = {};

    // --- Qwen-Image-Plus Specifics ---
    if (isQwen) {
        // Doc: parameters.size (Fixed 5 types)
        parameters.size = getQwenResolution(options.imageAspectRatio);
        
        // Doc: parameters.n (1-4)
        parameters.n = Math.min(Math.max(options.numberOfImages || 1, 1), 4);
        
        // Doc: parameters.prompt_extend (Boolean) - Default true for better quality
        parameters.prompt_extend = true;

        // Doc: input.negative_prompt
        if (options.negativePrompt) {
            input.negative_prompt = options.negativePrompt;
        }
        
        // Watermark check (if supported)
        parameters.watermark = false; 
    } 
    // --- Wanx Specifics ---
    else if (isWanx) {
        // Doc: parameters.size (Flexible)
        parameters.size = getWanxResolution(options.imageAspectRatio, options.imageResolution);
        
        // Doc: parameters.n (1-4)
        parameters.n = Math.min(Math.max(options.numberOfImages || 1, 1), 4);

        // Doc: parameters.style (Specific format like '<anime>')
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
        
        // Wanx sometimes puts negative prompt in parameters, sometimes input. 
        // V2 puts it in input.negative_prompt usually.
        if (options.negativePrompt) {
            input.negative_prompt = options.negativePrompt;
        }
    }

    const payload = {
        model: modelId,
        input: input,
        parameters: parameters
    };

    console.log(`[DashScope] Generating with ${modelId}`, payload);

    const url = resolveDashUrl(baseUrl || '', 'image-generation');
    
    // Result handling is shared because the Async Task format is consistent across DashScope
    const result = await submitAndPoll(url, payload, apiKey);
    
    return [result];
}

// --- Image Editing (Repainting) ---
export async function editWanxImage(
    prompt: string,
    referenceImage: Attachment,
    apiKey: string,
    baseUrl?: string
): Promise<ImageGenerationResult> {
    
    const imageUrl = await ensureRemoteUrl(referenceImage, apiKey, baseUrl);

    // Using Wanx V1 for reliable editing currently
    const payload = {
        model: "wanx-v1",
        input: {
            image_url: imageUrl, 
            prompt: prompt
        },
        parameters: {
            style: "<auto>",
            size: "1024*1024", 
            n: 1
        }
    };

    const url = resolveDashUrl(baseUrl || '', 'image-edit');
    return submitAndPoll(url, payload, apiKey);
}

// --- Outpainting ---
export async function outPaintWanxImage(
    referenceImage: Attachment,
    options: ChatOptions,
    apiKey: string,
    baseUrl?: string
): Promise<ImageGenerationResult> {
    
    const imageUrl = await ensureRemoteUrl(referenceImage, apiKey, baseUrl);

    const outPaintingOpts = options.outPainting || {
        mode: 'scale',
        xScale: 2.0,
        yScale: 2.0,
        leftOffset: 0,
        rightOffset: 0,
        topOffset: 0,
        bottomOffset: 0,
        bestQuality: true,
        limitImageSize: true // Default to true per docs
    };

    const parameters: any = {
        // Ensure boolean types
        best_quality: !!outPaintingOpts.bestQuality,
        limit_image_size: outPaintingOpts.limitImageSize !== false // Default true
    };

    if (outPaintingOpts.mode === 'offset') {
        if (outPaintingOpts.leftOffset) parameters.left_offset = outPaintingOpts.leftOffset;
        if (outPaintingOpts.rightOffset) parameters.right_offset = outPaintingOpts.rightOffset;
        if (outPaintingOpts.topOffset) parameters.top_offset = outPaintingOpts.topOffset;
        if (outPaintingOpts.bottomOffset) parameters.bottom_offset = outPaintingOpts.bottomOffset;
        
        // Fallback default if all offsets are 0
        if (!parameters.left_offset && !parameters.right_offset && !parameters.top_offset && !parameters.bottom_offset) {
             parameters.right_offset = 512;
        }
    } else {
        parameters.x_scale = outPaintingOpts.xScale || 2.0;
        parameters.y_scale = outPaintingOpts.yScale || 2.0;
    }

    const payload = {
        model: "image-out-painting",
        input: {
            image_url: imageUrl
        },
        parameters: parameters
    };

    const url = resolveDashUrl(baseUrl || '', 'out-painting');
    return submitAndPoll(url, payload, apiKey);
}
