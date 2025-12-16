
import { ImageGenerationResult } from "../../interfaces";
import { ChatOptions, Attachment } from "../../../../../types";
import { GoogleGenAI } from "@google/genai";
import { processReferenceImage } from "../../../media/utils";

/**
 * 图片编辑函数
 * 
 * 使用 generateContent() 进行单次图片编辑。
 * 多轮编辑的连续性由前端 ImageEditView 的 CONTINUITY LOGIC 处理：
 * - 前端会自动将当前画布上的图片转换为 Base64 附件传递
 * - 每次调用都是独立的，不需要维护 chat 历史
 */
export async function editImage(
    ai: GoogleGenAI,
    modelId: string, 
    prompt: string, 
    referenceImages: Attachment[], 
    options: ChatOptions
): Promise<ImageGenerationResult[]> {
    
    let targetModel = modelId;

    // Strict Model Routing for Edit Mode
    // If a user is on a generic text model (like flash/pro), force switch to a vision/image model
    // to ensure the 'generateContent' call with images succeeds.
    if (targetModel === 'gemini-3-pro-preview') {
        targetModel = 'gemini-3-pro-image-preview';
    } else if (
        !targetModel.includes('image') && 
        !targetModel.includes('veo') && 
        !targetModel.includes('vision') && 
        !targetModel.includes('pro-image')
    ) {
       // Fallback for purely text models that might be selected in UI
       targetModel = 'gemini-2.5-flash-image';
    }

    const config: any = {
        imageConfig: {
            aspectRatio: options.imageAspectRatio || '1:1'
        },
        // Ensure we explicitly ask for Image output, though it's usually inferred.
        // Some newer models perform better with explicit modalities.
        responseModalities: ['TEXT', 'IMAGE'] 
    };
    
    if (options.imageResolution) {
        config.imageConfig.imageSize = options.imageResolution;
    }

    // Inject Search Tool if enabled (e.g. "Edit this to show current weather in Tokyo")
    if (options.enableSearch) {
        config.tools = [{ googleSearch: {} }];
    }

    const parts: any[] = [];
    
    // Process input images (Source of Truth for Editing)
    for (const refImg of referenceImages) {
        const { mimeType, imageBytes } = await processReferenceImage(refImg);
        if (imageBytes) {
            // 方式 1: Base64 数据或 File 对象转换后的数据
            parts.push({ inlineData: { mimeType, data: imageBytes } });
        } else if (refImg.fileUri) {
            // 方式 2: 已上传到 Google 的文件
            parts.push({ fileData: { mimeType: refImg.mimeType, fileUri: refImg.fileUri } });
        } else if (refImg.url && !refImg.url.startsWith('blob:')) {
            // 方式 3: 远程 URL - 需要先下载转换为 Base64
            try {
                const response = await fetch(refImg.url);
                const blob = await response.blob();
                const base64 = await blobToBase64(blob);
                const match = base64.match(/^data:(.*?);base64,(.*)$/);
                if (match) {
                    parts.push({ 
                        inlineData: { 
                            mimeType: match[1], 
                            data: match[2] 
                        } 
                    });
                }
            } catch (e) {
                console.warn('[editImage] Failed to fetch reference image:', refImg.url, e);
            }
        }
    }

    // Construct precise prompt for Virtual Try-On if target provided
    let finalPrompt = prompt.trim();
    if (options.virtualTryOnTarget) {
        const target = options.virtualTryOnTarget;
        finalPrompt = `Perform a virtual try-on editing task. Identify the ${target} in the image. Replace strictly the ${target} with: ${prompt}. Maintain the rest of the image exactly as is.`;
    }

    parts.push({ text: finalPrompt });

    console.log(`[GoogleMedia] Editing image with model: ${targetModel}`);
    console.log(`[GoogleMedia] Parts count: ${parts.length} (images: ${parts.filter(p => p.inlineData || p.fileData).length})`);

    try {
        const response = await ai.models.generateContent({
            model: targetModel,
            contents: { parts },
            config: config
        });

        if (response.candidates && response.candidates.length > 0) {
          for (const part of response.candidates[0].content?.parts || []) {
              if (part.inlineData) {
                  return [{
                      url: `data:${part.inlineData.mimeType};base64,${part.inlineData.data}`,
                      mimeType: part.inlineData.mimeType || 'image/png'
                  }];
              }
          }
        }
        throw new Error("Model returned no edited image. Ensure the prompt describes a visual change.");
    } catch (e: any) {
        console.warn(`Gemini Edit Error: ${e.message}`);
        throw e;
    }
}

/**
 * 将 Blob 转换为 Base64 Data URL
 */
function blobToBase64(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}
