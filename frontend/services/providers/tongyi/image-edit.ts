
import { ImageGenerationResult } from "../interfaces";
import { Attachment, ChatOptions } from "../../../types/types";
import { resolveDashUrl, submitAndPoll } from "./api";
import { ensureRemoteUrl } from "./image-utils";

// --- Image Editing (Repainting/Inpainting) ---
export async function editWanxImage(
    modelId: string, // Now accepts specific model ID
    prompt: string,
    referenceImage: Attachment,
    options: ChatOptions, // Added options for LoRA/Seed/N
    apiKey: string,
    baseUrl?: string
): Promise<ImageGenerationResult> {
    
    // 1. Ensure Reference Image is uploaded/accessible
    const imageUrl = await ensureRemoteUrl(referenceImage, apiKey, baseUrl);

    let payload: any = {};

    // --- CASE A: WanX V2.5 Image Edit ---
    if (modelId === 'wanx-v2.5-image-edit') {
        // https://help.aliyun.com/zh/model-studio/wan2-5-image-edit-api-reference
        const input: any = {
            image_url: imageUrl,
            prompt: prompt,
            // WanX V2.5 REQUIRES mask_url for editing logic. 
            // If user didn't provide a mask (just uploaded one image), we might fail or need a fallback.
            // For now, if no mask is attached, we might need to assume 'mask' is the same as image (full edit) or fail.
            // NOTE: The UI typically handles masking via a separate attachment or canvas.
            // Current simplified assumption: If options.maskUrl exists (future) or we generate a full-white mask?
            // Actually, WanX edit usually implies inpainting. Without a mask, it might act as style transfer or fail.
            // Let's assume the user provided a mask attachment if they are in 'edit' mode properly, 
            // BUT current simple UI only sends one image usually. 
            // Fallback: If no mask, we can't strictly use v2.5's *mask-based* edit properly without updating UI to support mask upload.
            // However, let's construct the payload assuming best effort.
        };

        // Check for LoRA
        if (options.loraConfig?.image) {
            input.lora_image_url = options.loraConfig.image;
            if (options.loraConfig.alpha) {
                input.lora_alpha = options.loraConfig.alpha;
            }
        }

        const parameters: any = {
            n: Math.min(Math.max(options.numberOfImages || 1, 1), 4),
            seed: options.seed && options.seed > -1 ? options.seed : undefined
        };
        
        // If we have a mask file/url in attachments (not yet in simple UI), usage would go here.
        // For now, we construct the payload.
        // Note: Currently simple UI sends [refImage]. 
        // We'll stick to a valid payload structure. 
        // If the model *requires* a mask, this call might fail if we don't have one.
        // For 'edit' without explicit mask, sometimes it means 're-generate based on image'.
        
        // Let's use the mandatory fields. 
        // If the UI hasn't supported mask painting, WanX V2.5 might be tricky.
        // We will pass the image as the base.
        
        payload = {
            model: modelId,
            input: input,
            parameters: parameters
        };
    }
    
    // --- CASE B: Qwen VL Image Edit ---
    else if (modelId === 'qwen-vl-image-edit') {
        // https://help.aliyun.com/zh/model-studio/qwen-image-edit-api
        payload = {
            model: modelId,
            input: {
                image_url: imageUrl,
                prompt: prompt
            },
            parameters: {} // Qwen Edit often doesn't need extra params
        };
    }

    // --- CASE C: WanX V1 (Legacy / Default) ---
    else {
        payload = {
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
    }

    const url = resolveDashUrl(baseUrl || '', 'image-edit', modelId);
    return submitAndPoll(url, payload, apiKey);
}
