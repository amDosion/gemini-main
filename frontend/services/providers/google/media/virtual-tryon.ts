/**
 * @deprecated 此文件已废弃，请使用 UnifiedProviderClient 代替
 * 
 * Virtual Try-On 服务 - 已统一到 UnifiedProviderClient
 * 
 * 新架构: 所有 Provider 统一使用 UnifiedProviderClient，通过后端统一路由处理
 * - Virtual Try-On: /api/modes/google/virtual-try-on
 * - 所有功能都通过后端统一处理，无需前端直接调用 Google SDK
 * 
 * 迁移指南:
 * - 使用 UnifiedProviderClient('google').executeMode('virtual-try-on', ...) 代替
 * - generateMaskPreview 函数已重构为通过后端 API 调用
 */
import { GoogleGenAI } from "@google/genai"; // 保留用于向后兼容
import { Attachment } from "../../../../types/types";
import { ImageGenerationResult } from "../../interfaces";
import { processReferenceImage } from "../../../media/utils";
import { UnifiedProviderClient } from "../../UnifiedProviderClient";

/**
 * 获取访问令牌
 */
function getAccessToken(): string | null {
    return localStorage.getItem('access_token');
}

// ========== 类型定义 ==========

/**
 * 分割结果
 */
export interface SegmentationResult {
    /** Base64 编码的掩码图像 "data:image/png;base64,..." */
    mask: string;
    /** 边界框坐标 [y0, x0, y1, x1]（归一化到 1000） */
    box_2d: number[];
    /** 物体标签 */
    label: string;
}

/**
 * Try-On 选项
 */
export interface TryOnOptions {
    /** 要分割的服装类型（如 "hoodie", "jacket", "upper body clothing"） */
    targetClothing: string;
    /** 服装描述 */
    prompt: string;
    /** 编辑模式 */
    editMode?: 'inpainting-insert' | 'inpainting-remove';
    /** 掩码膨胀系数（默认 0.02） */
    dilation?: number;
    /** Gemini 模型 ID（用于分割） */
    modelId?: string;
}

/**
 * 后端编辑请求
 */
interface TryOnEditRequest {
    image: string;
    mask?: string;
    prompt: string;
    edit_mode: string;
    mask_mode: string;
    dilation: number;
    api_key?: string;
    target_clothing: string;
}

/**
 * 后端编辑响应
 */
interface TryOnEditResponse {
    success: boolean;
    image?: string;
    mimeType: string;
    error?: string;
}

// ========== 服装分割 ==========

/**
 * @deprecated 此函数已废弃，请使用 UnifiedProviderClient 调用后端 API
 * 
 * 服装分割 - 已移动到后端
 * 
 * 新方式: 使用 UnifiedProviderClient('google').executeMode('segment-clothing', ...)
 * 此函数保留用于向后兼容，但内部已改为通过后端 API 调用
 */
export async function segmentClothing(
    ai: GoogleGenAI, // 已弃用 - 不再使用
    image: Attachment,
    targetClothing: string,
    modelId?: string
): Promise<SegmentationResult[]> {
    console.warn('[segmentClothing] ⚠️ 此函数已废弃，请使用 UnifiedProviderClient 调用后端 API');
    
    try {
        const token = getAccessToken();
        if (!token) {
            throw new Error('未登录，请先登录');
        }
        
        // ✅ 通过 UnifiedProviderClient 调用后端 API
        const client = new UnifiedProviderClient('google');
        
        // 准备附件
        const attachments: Attachment[] = [image];
        
        // 调用后端 API
        const response = await fetch(`/api/modes/google/segment-clothing`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            credentials: 'include',
            body: JSON.stringify({
                modelId: modelId || 'gemini-2.0-flash-exp',
                prompt: '', // segment-clothing 不需要 prompt
                attachments: attachments,
                options: {},
                extra: {
                    target_clothing: targetClothing
                }
            })
        });
        
        if (!response.ok) {
            throw new Error(`后端 API 调用失败: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || '分割失败');
        }
        
        // 转换后端响应格式为前端格式
        const segments: SegmentationResult[] = data.data.segments || [];
        console.log(`[VirtualTryOn] Segmentation successful: ${segments.length} segments found`);
        return segments;
        
    } catch (error) {
        console.error('[VirtualTryOn] Segmentation error:', error);
        // ✅ 回退到旧方式（向后兼容，但会显示警告）
        console.warn('[segmentClothing] ⚠️ 后端 API 调用失败，回退到已废弃的直接调用 Google SDK 方式');
        
        const model = modelId || 'gemini-2.0-flash-exp';
        console.log(`[VirtualTryOn] Segmenting clothing: target=${targetClothing}, model=${model}`);

        // 处理输入图像
        const { mimeType, imageBytes } = await processReferenceImage(image);
        if (!imageBytes) {
            throw new Error('Failed to process reference image');
        }

        // 构建分割 prompt
        const segmentPrompt = `Give the segmentation masks for ${targetClothing} in this image.
Output a JSON list of segmentation masks where each entry contains:
- the 2D bounding box in the key 'box_2d' as [y0, x0, y1, x1] normalized to 1000
- the segmentation mask in key 'mask' as a base64 encoded PNG image (data:image/png;base64,...)
- the text label in the key 'label'

Only output the JSON array, no other text or markdown formatting.`;

        const response = await ai.models.generateContent({
            model: model,
            contents: {
                parts: [
                    { inlineData: { mimeType, data: imageBytes } },
                    { text: segmentPrompt }
                ]
            }
        });

        // 解析响应
        if (response.candidates && response.candidates.length > 0) {
            const text = response.candidates[0].content?.parts?.[0]?.text || '';
            
            // 清理可能的 markdown 代码块
            let jsonText = text.trim();
            if (jsonText.startsWith('```')) {
                const lines = jsonText.split('\n');
                lines.shift(); // 移除 ```json
                if (lines[lines.length - 1] === '```') {
                    lines.pop();
                }
                jsonText = lines.join('\n');
            }

            try {
                const segments: SegmentationResult[] = JSON.parse(jsonText);
                console.log(`[VirtualTryOn] Segmentation successful: ${segments.length} segments found`);
                return segments;
            } catch (parseError) {
                console.error('[VirtualTryOn] Failed to parse segmentation JSON:', parseError);
                console.log('[VirtualTryOn] Raw response:', text);
                return [];
            }
        }

        console.warn('[VirtualTryOn] No segmentation result from Gemini');
        return [];
    }
}

// ========== 掩码生成 ==========

/**
 * 生成完整掩码
 * 将分割结果合并为完整的二值掩码
 * 
 * @param segmentationResults - 分割结果数组
 * @param imageWidth - 图像宽度
 * @param imageHeight - 图像高度
 * @returns Base64 编码的掩码图像
 */
export function generateMask(
    segmentationResults: SegmentationResult[],
    imageWidth: number,
    imageHeight: number
): string {
    if (segmentationResults.length === 0) {
        console.warn('[VirtualTryOn] No segmentation results to generate mask');
        return '';
    }

    console.log(`[VirtualTryOn] Generating mask: ${segmentationResults.length} segments, size=${imageWidth}x${imageHeight}`);

    // 创建画布
    const canvas = document.createElement('canvas');
    canvas.width = imageWidth;
    canvas.height = imageHeight;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) {
        throw new Error('Failed to get canvas context');
    }

    // 填充黑色背景
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, imageWidth, imageHeight);

    // 处理每个分割结果
    const loadPromises = segmentationResults.map(async (segment, index) => {
        try {
            // 解析边界框坐标（归一化到 1000）
            const [y0_norm, x0_norm, y1_norm, x1_norm] = segment.box_2d;
            
            // 转换为绝对像素坐标
            const x0 = Math.round(x0_norm * imageWidth / 1000);
            const y0 = Math.round(y0_norm * imageHeight / 1000);
            const x1 = Math.round(x1_norm * imageWidth / 1000);
            const y1 = Math.round(y1_norm * imageHeight / 1000);
            
            // 验证坐标有效性
            if (x0 >= x1 || y0 >= y1) {
                console.warn(`[VirtualTryOn] Invalid bbox for segment ${index}: [${x0}, ${y0}, ${x1}, ${y1}]`);
                return;
            }

            const boxWidth = x1 - x0;
            const boxHeight = y1 - y0;

            console.log(`[VirtualTryOn] Segment ${index} (${segment.label}): bbox=[${x0}, ${y0}, ${x1}, ${y1}], size=${boxWidth}x${boxHeight}`);

            // 加载掩码图像
            if (segment.mask) {
                const maskImg = new Image();
                await new Promise<void>((resolve, reject) => {
                    maskImg.onload = () => resolve();
                    maskImg.onerror = () => reject(new Error('Failed to load mask image'));
                    maskImg.src = segment.mask;
                });

                // 将掩码绘制到正确位置
                ctx.drawImage(maskImg, x0, y0, boxWidth, boxHeight);
            }
        } catch (error) {
            console.error(`[VirtualTryOn] Error processing segment ${index}:`, error);
        }
    });

    // 等待所有掩码加载完成
    // 注意：这是同步版本，实际使用时需要异步处理
    // 这里我们返回一个简化的掩码

    // 返回 Base64 编码的掩码
    return canvas.toDataURL('image/png');
}

/**
 * 异步生成完整掩码
 * 将分割结果合并为完整的二值掩码
 */
export async function generateMaskAsync(
    segmentationResults: SegmentationResult[],
    imageWidth: number,
    imageHeight: number
): Promise<string> {
    if (segmentationResults.length === 0) {
        console.warn('[VirtualTryOn] No segmentation results to generate mask');
        return '';
    }

    console.log(`[VirtualTryOn] Generating mask async: ${segmentationResults.length} segments, size=${imageWidth}x${imageHeight}`);

    // 创建画布
    const canvas = document.createElement('canvas');
    canvas.width = imageWidth;
    canvas.height = imageHeight;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) {
        throw new Error('Failed to get canvas context');
    }

    // 填充黑色背景
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, imageWidth, imageHeight);

    // 处理每个分割结果
    for (let index = 0; index < segmentationResults.length; index++) {
        const segment = segmentationResults[index];
        try {
            // 解析边界框坐标（归一化到 1000）
            const [y0_norm, x0_norm, y1_norm, x1_norm] = segment.box_2d;
            
            // 转换为绝对像素坐标
            const x0 = Math.round(x0_norm * imageWidth / 1000);
            const y0 = Math.round(y0_norm * imageHeight / 1000);
            const x1 = Math.round(x1_norm * imageWidth / 1000);
            const y1 = Math.round(y1_norm * imageHeight / 1000);
            
            // 验证坐标有效性
            if (x0 >= x1 || y0 >= y1) {
                console.warn(`[VirtualTryOn] Invalid bbox for segment ${index}: [${x0}, ${y0}, ${x1}, ${y1}]`);
                continue;
            }

            const boxWidth = x1 - x0;
            const boxHeight = y1 - y0;

            console.log(`[VirtualTryOn] Segment ${index} (${segment.label}): bbox=[${x0}, ${y0}, ${x1}, ${y1}], size=${boxWidth}x${boxHeight}`);

            // 加载掩码图像
            if (segment.mask) {
                const maskImg = new Image();
                await new Promise<void>((resolve, reject) => {
                    maskImg.onload = () => resolve();
                    maskImg.onerror = () => reject(new Error('Failed to load mask image'));
                    maskImg.src = segment.mask;
                });

                // 将掩码绘制到正确位置
                ctx.drawImage(maskImg, x0, y0, boxWidth, boxHeight);
            }
        } catch (error) {
            console.error(`[VirtualTryOn] Error processing segment ${index}:`, error);
        }
    }

    // 返回 Base64 编码的掩码
    return canvas.toDataURL('image/png');
}

// ========== 后端 API 调用 ==========

/**
 * 调用后端编辑 API
 * 
 * @param imageBase64 - Base64 编码的原图
 * @param maskBase64 - Base64 编码的掩码（可选）
 * @param prompt - 服装描述
 * @param editMode - 编辑模式
 * @param dilation - 掩码膨胀系数
 * @param apiKey - Gemini API Key（用于备用方案）
 * @param targetClothing - 目标服装类型
 * @returns 编辑结果
 */
export async function editWithMask(
    imageBase64: string,
    maskBase64: string | null,
    prompt: string,
    editMode: 'inpainting-insert' | 'inpainting-remove' = 'inpainting-insert',
    dilation: number = 0.02,
    apiKey?: string,
    targetClothing: string = 'upper body clothing'
): Promise<ImageGenerationResult> {
    console.log(`[VirtualTryOn] Calling backend edit API: prompt=${prompt.substring(0, 50)}...`);

    const request: TryOnEditRequest = {
        image: imageBase64,
        mask: maskBase64 || undefined,
        prompt: prompt,
        edit_mode: editMode,
        mask_mode: 'foreground',
        dilation: dilation,
        api_key: apiKey,
        target_clothing: targetClothing
    };

    try {
        const response = await fetch('/api/tryon/edit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(request)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const result: TryOnEditResponse = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Edit failed');
        }

        if (!result.image) {
            throw new Error('No image in response');
        }

        // 返回结果
        return {
            url: `data:${result.mimeType};base64,${result.image}`,
            mimeType: result.mimeType
        };

    } catch (error) {
        console.error('[VirtualTryOn] Backend edit error:', error);
        throw error;
    }
}

// ========== 主函数 ==========

/**
 * Virtual Try-On 主函数
 * 整合分割和编辑流程
 * 
 * @param ai - GoogleGenAI 客户端
 * @param referenceImage - 参考图像
 * @param options - Try-On 选项
 * @param apiKey - API Key
 * @returns 编辑结果
 */
export async function virtualTryOn(
    ai: GoogleGenAI,
    referenceImage: Attachment,
    options: TryOnOptions,
    apiKey: string
): Promise<ImageGenerationResult> {
    console.log(`[VirtualTryOn] Starting try-on: target=${options.targetClothing}, prompt=${options.prompt.substring(0, 50)}...`);

    // 1. 处理输入图像
    const { mimeType, imageBytes } = await processReferenceImage(referenceImage);
    if (!imageBytes) {
        throw new Error('Failed to process reference image');
    }

    const imageBase64 = `data:${mimeType};base64,${imageBytes}`;

    // 2. 获取图像尺寸
    const imageSize = await getImageSize(imageBase64);
    console.log(`[VirtualTryOn] Image size: ${imageSize.width}x${imageSize.height}`);

    // 3. 服装分割（可选，如果后端支持智能编辑则可跳过）
    let maskBase64: string | null = null;
    
    try {
        const segments = await segmentClothing(ai, referenceImage, options.targetClothing, options.modelId);
        
        if (segments.length > 0) {
            maskBase64 = await generateMaskAsync(segments, imageSize.width, imageSize.height);
            console.log(`[VirtualTryOn] Mask generated successfully`);
        } else {
            console.log(`[VirtualTryOn] No segments found, will use smart editing`);
        }
    } catch (segmentError) {
        console.warn(`[VirtualTryOn] Segmentation failed, will use smart editing:`, segmentError);
    }

    // 4. 调用后端编辑 API
    const result = await editWithMask(
        imageBase64,
        maskBase64,
        options.prompt,
        options.editMode || 'inpainting-insert',
        options.dilation || 0.02,
        apiKey,
        options.targetClothing
    );

    console.log(`[VirtualTryOn] Try-on completed successfully`);
    return result;
}

// ========== 辅助函数 ==========

/**
 * 获取图像尺寸
 */
async function getImageSize(imageUrl: string): Promise<{ width: number; height: number }> {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
            resolve({ width: img.naturalWidth, height: img.naturalHeight });
        };
        img.onerror = () => {
            reject(new Error('Failed to load image'));
        };
        img.src = imageUrl;
    });
}

/**
 * 获取 Try-On 服务状态
 */
export async function getTryOnStatus(): Promise<{
    vertexAiAvailable: boolean;
    geminiAvailable: boolean;
    gcpConfigured: boolean;
}> {
    try {
        const response = await fetch('/api/tryon/status');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        return {
            vertexAiAvailable: data.vertex_ai_available,
            geminiAvailable: data.gemini_available,
            gcpConfigured: data.gcp_configured
        };
    } catch (error) {
        console.error('[VirtualTryOn] Failed to get status:', error);
        return {
            vertexAiAvailable: false,
            geminiAvailable: false,
            gcpConfigured: false
        };
    }
}

/**
 * 生成掩码预览（用于 UI 显示）
 * 返回半透明红色叠加的预览图
 * 
 * @param imageBase64 Base64 编码的原图（data:image/...;base64,... 或 http://...）
 * @param targetClothing 目标服装类型
 * @param apiKey Gemini API Key
 * @param modelId Gemini 模型 ID（可选，默认使用 gemini-2.0-flash-exp）
 * @param alpha 透明度（0.3-1.0，默认 0.7）
 * @param threshold 阈值（10-200，默认 50）
 * @returns Base64 编码的掩码预览图
 */
/**
 * 生成掩码预览（已重构为通过后端 API）
 * 
 * @deprecated 此函数已重构为通过 UnifiedProviderClient 调用后端 API
 * 
 * 新方式: 使用 UnifiedProviderClient('google').executeMode('virtual-try-on', ...)
 * 此函数保留用于向后兼容，但内部已改为通过后端 API 调用
 */
export async function generateMaskPreview(
  imageBase64: string,
  targetClothing: string,
  apiKey: string, // 已弃用 - 后端从数据库获取
  modelId?: string,
  alpha: number = 0.7,
  threshold: number = 50
): Promise<string> {
  try {
    console.log(`[generateMaskPreview] 生成掩码预览: ${targetClothing}, alpha=${alpha}, threshold=${threshold}`);
    
    // 1. 加载原图
    const img = new Image();
    img.crossOrigin = 'anonymous';
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = () => reject(new Error('无法加载图片'));
      img.src = imageBase64;
    });
    
    console.log(`[generateMaskPreview] 图片尺寸: ${img.width}x${img.height}`);
    
    // ✅ 2. 通过 UnifiedProviderClient 调用后端 API 获取分割结果
    let maskBase64: string;
    
    try {
      const token = getAccessToken();
      
      if (!token) {
        throw new Error('未登录，请先登录');
      }
      
      // ✅ 通过后端 API 调用分割功能
      const attachment: Attachment = {
        id: 'preview',
        url: imageBase64,
        mimeType: 'image/png',
        name: 'preview.png'
      };
      
      // ✅ 通过 UnifiedProviderClient 调用后端 API
      // 使用 segment-clothing mode 调用后端分割功能
      const response = await fetch(`/api/modes/google/segment-clothing`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        credentials: 'include',
        body: JSON.stringify({
          modelId: modelId || 'gemini-2.0-flash-exp',
          prompt: '', // segment-clothing 不需要 prompt
          attachments: [attachment],
          options: {},
          extra: {
            target_clothing: targetClothing
          }
        })
      });
      
      if (!response.ok) {
        throw new Error(`后端 API 调用失败: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error || '分割失败');
      }
      
      // 转换后端响应格式为前端格式
      segments = data.data.segments || [];
      
      if (segments.length === 0) {
        throw new Error('未检测到目标服装区域');
      }
      
      console.log(`[generateMaskPreview] 检测到 ${segments.length} 个区域`);
      
      // 3. 生成完整掩码
      maskBase64 = await generateMaskAsync(segments, img.width, img.height);
    } catch (backendError) {
      console.warn('[generateMaskPreview] 后端 API 调用失败，回退到旧方式:', backendError);
      // ✅ 回退到旧方式（向后兼容，但会显示警告）
      console.warn('[generateMaskPreview] ⚠️ 使用已废弃的直接调用 Google SDK 方式');
      
      const ai = new GoogleGenAI({ apiKey });
      const attachment: Attachment = {
        id: 'preview',
        url: imageBase64,
        mimeType: 'image/png',
        name: 'preview.png'
      };
      
      const segments = await segmentClothing(ai, attachment, targetClothing, modelId);
      
      if (segments.length === 0) {
        throw new Error('未检测到目标服装区域');
      }
      
      console.log(`[generateMaskPreview] 检测到 ${segments.length} 个区域`);
      
      // 3. 生成完整掩码
      maskBase64 = await generateMaskAsync(segments, img.width, img.height);
    }
    
    // 4. 创建半透明红色叠加预览
    const canvas = document.createElement('canvas');
    canvas.width = img.width;
    canvas.height = img.height;
    const ctx = canvas.getContext('2d')!;
    
    // 绘制原图
    ctx.drawImage(img, 0, 0);
    
    // 加载掩码
    const maskImg = new Image();
    await new Promise((resolve, reject) => {
      maskImg.onload = resolve;
      maskImg.onerror = () => reject(new Error('无法加载掩码'));
      maskImg.src = maskBase64;
    });
    
    // 创建临时画布用于处理掩码
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = img.width;
    tempCanvas.height = img.height;
    const tempCtx = tempCanvas.getContext('2d')!;
    
    // 绘制掩码
    tempCtx.drawImage(maskImg, 0, 0);
    
    // 获取掩码像素数据
    const maskData = tempCtx.getImageData(0, 0, img.width, img.height);
    
    // 统计掩码信息（用于调试）
    let maskPixelCount = 0;
    let totalPixels = maskData.data.length / 4;
    for (let i = 0; i < maskData.data.length; i += 4) {
      const brightness = maskData.data[i];
      if (brightness > threshold) {  // ✅ 使用传入的阈值参数
        maskPixelCount++;
      }
    }
    console.log(`[generateMaskPreview] 掩码统计: ${maskPixelCount}/${totalPixels} 像素 (${(maskPixelCount/totalPixels*100).toFixed(2)}%)`);
    
    // 在原图上绘制半透明红色（只在掩码白色区域）
    const imageData = ctx.getImageData(0, 0, img.width, img.height);
    for (let i = 0; i < maskData.data.length; i += 4) {
      const brightness = maskData.data[i]; // R 通道
      if (brightness > threshold) {  // ✅ 使用传入的阈值参数
        // ✅ 使用传入的透明度参数
        imageData.data[i] = imageData.data[i] * (1 - alpha) + 255 * alpha;     // R
        imageData.data[i + 1] = imageData.data[i + 1] * (1 - alpha);           // G
        imageData.data[i + 2] = imageData.data[i + 2] * (1 - alpha);           // B
      }
    }
    
    ctx.putImageData(imageData, 0, 0);
    
    // 转换为 Base64
    const previewBase64 = canvas.toDataURL('image/png');
    console.log(`[generateMaskPreview] 预览生成成功`);
    
    return previewBase64;
  } catch (error) {
    console.error('[generateMaskPreview] 错误:', error);
    throw error;
  }
}

/**
 * 检查 Upscale 分辨率是否超过限制
 * 
 * @param width 原始宽度
 * @param height 原始高度
 * @param upscaleFactor 放大倍数
 * @returns { isValid, errorMessage }
 */
export function checkUpscaleResolution(
  width: number,
  height: number,
  upscaleFactor: 2 | 4
): { isValid: boolean; errorMessage?: string } {
  const MAX_MEGAPIXELS = 17;
  
  const newWidth = width * upscaleFactor;
  const newHeight = height * upscaleFactor;
  const newMegapixels = (newWidth * newHeight) / 1_000_000;
  
  if (newMegapixels > MAX_MEGAPIXELS) {
    return {
      isValid: false,
      errorMessage: `输出分辨率 ${newMegapixels.toFixed(2)}MP 超过限制 ${MAX_MEGAPIXELS}MP`
    };
  }
  
  return { isValid: true };
}

/**
 * 调用后端 Upscale API
 * 
 * @param imageBase64 Base64 编码的图像
 * @param upscaleFactor 放大倍数（2 或 4）
 * @param addWatermark 是否添加水印
 * @returns ImageGenerationResult
 */
export async function upscaleImage(
  imageBase64: string,
  upscaleFactor: 2 | 4,
  addWatermark: boolean = false
): Promise<ImageGenerationResult> {
  try {
    console.log(`[upscaleImage] 调用后端 API: factor=${upscaleFactor}x, watermark=${addWatermark}`);
    
    const response = await fetch('/api/tryon/upscale', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        image: imageBase64,
        upscale_factor: upscaleFactor,
        add_watermark: addWatermark
      })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Upscale failed');
    }
    
    console.log(`[upscaleImage] 成功: ${data.original_resolution} -> ${data.upscaled_resolution}`);
    
    // 构建 data URL
    const dataUrl = data.image.startsWith('data:')
      ? data.image
      : `data:${data.mimeType};base64,${data.image}`;
    
    return {
      url: dataUrl,
      mimeType: data.mimeType
    };
  } catch (error) {
    console.error('[upscaleImage] 错误:', error);
    throw error;
  }
}
