
import { ImageGenerationResult } from "../../interfaces";
import { ChatOptions, Attachment } from "../../../../types/types";
import { GoogleGenAI } from "@google/genai";
import { processReferenceImage } from "../../../media/utils";
import { googleFileService } from "../fileService";

/**
 * 图片编辑函数
 * 
 * 使用 generateContent() 进行单次图片编辑。
 * 多轮编辑的连续性由前端 ImageEditView 的 CONTINUITY LOGIC 处理：
 * - 前端会自动将当前画布上的图片转换为 Base64 附件传递
 * - 每次调用都是独立的，不需要维护 chat 历史
 * 
 * 图片传递方式（按优先级）：
 * 1. 附件中的 file 字段（File 对象）- 最高效，直接上传到 Google Files API
 * 2. Google Files API (fileData) - 减少 33% 数据传输
 * 3. Base64 (inlineData) - 兼容性最好
 */
export async function editImage(
    ai: GoogleGenAI,
    modelId: string, 
    prompt: string, 
    referenceImages: Attachment[], 
    options: ChatOptions,
    apiKey?: string,
    baseUrl?: string
): Promise<ImageGenerationResult[]> {
    
    // 获取有效的 apiKey（优先使用传入的，其次使用环境变量）
    const effectiveApiKey = apiKey || process.env.API_KEY || '';
    const effectiveBaseUrl = baseUrl || '';
    
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
    
    // 调试日志：检查 apiKey 和 baseUrl
    console.log('[editImage] 参数检查:', {
        hasApiKey: !!effectiveApiKey,
        hasBaseUrl: !!effectiveBaseUrl,
        useGoogleFilesApi: options.useGoogleFilesApi,
        referenceImagesCount: referenceImages.length
    });
    
    // Process input images (Source of Truth for Editing)
    for (const refImg of referenceImages) {
        console.log('[editImage] 处理附件:', {
            id: refImg.id?.substring(0, 8),
            hasFile: !!refImg.file,
            hasGoogleFileUri: !!refImg.googleFileUri,
            hasBase64Data: !!(refImg as any).base64Data,
            urlType: refImg.url?.startsWith('data:') ? 'Base64' : 
                     refImg.url?.startsWith('http') ? 'HTTP' : 
                     refImg.url?.startsWith('blob:') ? 'Blob' : 'Other',
            mimeType: refImg.mimeType
        });
        
        // ============================================================
        // 优先级 1：使用附件中的 File 对象（最高效）
        // processUserAttachments 已经将云 URL 下载为 File 对象
        // ============================================================
        if (refImg.file && effectiveApiKey && options.useGoogleFilesApi !== false) {
            try {
                console.log('[editImage] ✅ 使用 File 对象上传到 Google Files API');
                const googleFileUri = await googleFileService.uploadFile(
                    refImg.file, 
                    effectiveApiKey, 
                    effectiveBaseUrl
                );
                
                console.log('[editImage] ✅ 上传成功:', googleFileUri.substring(0, 50));
                parts.push({ 
                    fileData: { 
                        mimeType: refImg.file.type || refImg.mimeType, 
                        fileUri: googleFileUri 
                    } 
                });
                continue;
            } catch (uploadError) {
                console.warn('[editImage] ⚠️ File 上传失败，回退到 Base64:', uploadError);
                // 继续尝试其他方式
            }
        }
        
        // ============================================================
        // 优先级 2：使用已有的 Google File URI
        // ============================================================
        if (refImg.googleFileUri && refImg.googleFileExpiry && Date.now() < refImg.googleFileExpiry) {
            console.log('[editImage] ✅ 使用已有的 Google File URI');
            parts.push({ 
                fileData: { 
                    mimeType: refImg.mimeType, 
                    fileUri: refImg.googleFileUri 
                } 
            });
            continue;
        }
        
        // ============================================================
        // 优先级 3：尝试使用 Google Files API 上传附件
        // ============================================================
        if (effectiveApiKey && options.useGoogleFilesApi !== false) {
            // ✅ 优化：如果附件已上传完成且有云 URL，跳过 Google Files API 上传
            if (refImg.uploadStatus === 'completed' && refImg.url?.startsWith('http')) {
                // 优先使用 tempUrl 中的 Base64 数据（避免重复下载）
                if (refImg.tempUrl?.startsWith('data:')) {
                    const match = refImg.tempUrl.match(/^data:(.*?);base64,(.*)$/);
                    if (match) {
                        console.log('[editImage] ✅ 跳过 Google Files API 上传，复用 tempUrl 的 Base64 数据');
                        parts.push({
                            inlineData: {
                                mimeType: match[1],
                                data: match[2]
                            }
                        });
                        continue;
                    }
                }
                // ✅ 修复：如果 tempUrl 无效但有 base64Data 字段，也使用它
                if ((refImg as any).base64Data) {
                    const base64Data = (refImg as any).base64Data as string;
                    const match = base64Data.match(/^data:(.*?);base64,(.*)$/);
                    if (match) {
                        console.log('[editImage] ✅ 跳过 Google Files API 上传，复用 base64Data 字段');
                        parts.push({
                            inlineData: {
                                mimeType: match[1],
                                data: match[2]
                            }
                        });
                        continue;
                    }
                }
                // 如果 tempUrl 和 base64Data 都无效，记录警告但继续尝试上传
                console.warn('[editImage] ⚠️ uploadStatus=completed 但 tempUrl 和 base64Data 都无效，继续尝试上传');
            }
            
            try {
                console.log('[editImage] 尝试上传到 Google Files API...');
                const { googleFileUri, mimeType } = await googleFileService.uploadAttachment(
                    refImg, 
                    effectiveApiKey, 
                    effectiveBaseUrl
                );
                
                console.log('[editImage] ✅ 使用 Google Files API:', googleFileUri.substring(0, 50));
                parts.push({ 
                    fileData: { 
                        mimeType, 
                        fileUri: googleFileUri 
                    } 
                });
                continue;
            } catch (uploadError) {
                console.warn('[editImage] ⚠️ Google Files API 上传失败，回退到 Base64:', uploadError);
                // 继续使用 Base64 方式
            }
        } else {
            console.log('[editImage] ⚠️ 跳过 Google Files API:', {
                reason: !effectiveApiKey ? 'apiKey 为空' : 'useGoogleFilesApi=false'
            });
        }

        // ============================================================
        // 优先级 4：回退到 Base64 方式（兼容性保证）
        // ============================================================
        const { mimeType, imageBytes, googleFileUri } = await processReferenceImage(refImg);
        
        // 如果 processReferenceImage 返回了 googleFileUri，优先使用
        if (googleFileUri) {
            parts.push({ fileData: { mimeType, fileUri: googleFileUri } });
        } else if (imageBytes) {
            // Base64 数据
            parts.push({ inlineData: { mimeType, data: imageBytes } });
        } else if (refImg.fileUri) {
            // 已上传到 Google 的文件
            parts.push({ fileData: { mimeType: refImg.mimeType, fileUri: refImg.fileUri } });
        } else if (refImg.url && !refImg.url.startsWith('blob:')) {
            // 远程 URL - 需要先下载转换为 Base64
            try {
                // 通过后端代理下载（解决 CORS）
                const proxyUrl = `/api/storage/download?url=${encodeURIComponent(refImg.url)}`;
                const response = await fetch(proxyUrl);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
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
                    console.log('[editImage] ✅ 通过后端代理下载成功');
                }
            } catch (e) {
                console.error('[editImage] Failed to fetch reference image:', refImg.url, e);
                // 如果 fetch 失败，尝试使用 img 标签 + canvas 方式获取图片数据
                try {
                    const base64 = await fetchImageViaCanvas(refImg.url);
                    const match = base64.match(/^data:(.*?);base64,(.*)$/);
                    if (match) {
                        parts.push({ 
                            inlineData: { 
                                mimeType: match[1], 
                                data: match[2] 
                            } 
                        });
                        console.log('[editImage] Successfully loaded image via canvas fallback');
                    }
                } catch (canvasError) {
                    console.error('[editImage] Canvas fallback also failed:', canvasError);
                }
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

    // 统计图片传递方式
    const fileDataCount = parts.filter(p => p.fileData).length;
    const inlineDataCount = parts.filter(p => p.inlineData).length;
    console.log(`[GoogleMedia] Editing image with model: ${targetModel}`);
    console.log(`[GoogleMedia] Parts count: ${parts.length} (fileData: ${fileDataCount}, inlineData: ${inlineDataCount})`);

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

/**
 * 通过 img 标签 + canvas 方式获取跨域图片的 Base64 数据
 * 这种方式可以绕过某些 CORS 限制（如果图片服务器允许跨域显示）
 */
function fetchImageViaCanvas(url: string): Promise<string> {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            try {
                const canvas = document.createElement('canvas');
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;
                const ctx = canvas.getContext('2d');
                if (!ctx) {
                    reject(new Error('Failed to get canvas context'));
                    return;
                }
                ctx.drawImage(img, 0, 0);
                const base64 = canvas.toDataURL('image/png');
                resolve(base64);
            } catch (e) {
                reject(e);
            }
        };
        img.onerror = () => reject(new Error('Failed to load image'));
        img.src = url;
    });
}
