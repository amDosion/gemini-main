
import { ImageGenerationResult } from "../interfaces";
import { Attachment, ChatOptions } from "../../../../types";
import { resolveDashUrl } from "./api";
import { ensureRemoteUrl } from "./image-utils";

/**
 * Implementation of DashScope Out-Painting (Expansion).
 * Supports modes: 'pixel' (offset), 'scale', and 'ratio'.
 */
export async function outPaintWanxImage(
    referenceImage: Attachment,
    options: ChatOptions,
    apiKey: string,
    baseUrl?: string
): Promise<ImageGenerationResult> {
    
    // 1. Ensure we have a valid remote URL (uploading if necessary)
    const imageUrl = await ensureRemoteUrl(referenceImage, apiKey, baseUrl);

    // 2. Prepare Parameters
    const opts = options.outPainting || {
        mode: 'scale',
        xScale: 2.0,
        yScale: 2.0,
        bestQuality: true,
        limitImageSize: true
    };

    const parameters: any = {
        best_quality: opts.bestQuality !== false,
        limit_image_size: opts.limitImageSize !== false,
        add_watermark: false
    };

    // Map UI modes to API parameters
    if (opts.mode === 'offset' || (opts.mode as string) === 'pixel') {
        // Pixel Offset Mode
        parameters.left_offset = opts.leftOffset || 0;
        parameters.right_offset = opts.rightOffset || 0;
        parameters.top_offset = opts.topOffset || 0;
        parameters.bottom_offset = opts.bottomOffset || 0;
        
        // Safety Fallback: if all offsets are 0, default to a right expansion to avoid errors
        if (!parameters.left_offset && !parameters.right_offset && !parameters.top_offset && !parameters.bottom_offset) {
             parameters.right_offset = 512;
        }
    } else if (opts.mode === 'ratio') {
        // Output Ratio Mode
        parameters.angle = opts.angle || 0;
        parameters.output_ratio = opts.outputRatio || "16:9"; 
    } else {
        // Scale Mode (Default)
        parameters.x_scale = opts.xScale || 2.0;
        parameters.y_scale = opts.yScale || 2.0;
    }

    const payload = {
        model: "image-out-painting",
        input: {
            image_url: imageUrl
        },
        parameters: parameters
    };

    console.log('[DashScope] Submitting Out-Painting Task:', JSON.stringify(payload));

    // 3. Submit Task (Async)
    const submitUrl = resolveDashUrl(baseUrl || '', 'out-painting');
    
    // ✅ Critical Headers for OSS Resolution and Async Processing
    // These headers are REQUIRED for the task to work correctly
    const headers = {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
        'X-DashScope-Async': 'enable',  // Enable async processing
        'X-DashScope-OssResourceResolve': 'enable'  // ✅ CRITICAL: Enable OSS URL resolution
    };

    console.log('[DashScope] Request headers:', headers);
    console.log('[DashScope] Submit URL:', submitUrl);

    const response = await fetch(submitUrl, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const errText = await response.text();
        let errorDetail = errText;
        try {
            const errJson = JSON.parse(errText);
            errorDetail = errJson.message || errText;
        } catch {}
        throw new Error(`DashScope Out-Painting Error (${response.status}): ${errorDetail}`);
    }

    const submitData = await response.json();
    const taskId = submitData.output?.task_id;
    if (!taskId) throw new Error("No task_id returned from DashScope.");

    // 4. Poll for Result
    const taskUrlBase = resolveDashUrl(baseUrl || '', 'task');
    const maxRetries = 100; // ~5 minutes (3s interval)
    
    for (let i = 0; i < maxRetries; i++) {
        await new Promise(r => setTimeout(r, 3000));
        
        const checkRes = await fetch(`${taskUrlBase}/${taskId}`, {
            headers: { 'Authorization': `Bearer ${apiKey}` }
        });
        
        if (!checkRes.ok) continue;
        
        const checkData = await checkRes.json();
        const status = checkData.output?.task_status;
        
        if (status === 'SUCCEEDED') {
            const resultUrl = checkData.output?.output_image_url || checkData.output?.url;
            if (!resultUrl) throw new Error("Task succeeded but no output image URL found.");
            
            return {
                url: resultUrl,
                mimeType: 'image/png'
            };
        } else if (status === 'FAILED') {
            const errMsg = checkData.output?.message || checkData.output?.code || 'Unknown error';
            throw new Error(`Out-Painting Task Failed: ${errMsg}`);
        }
        // If PENDING or RUNNING, continue polling
    }

    throw new Error("Out-Painting task timed out.");
}
