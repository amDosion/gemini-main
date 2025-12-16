
import { ImageGenerationResult } from "../../interfaces";
import { ChatOptions, Attachment } from "../../../../../types";
import { GoogleGenAI } from "@google/genai";
import { processReferenceImage } from "../../../media/utils";

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
            parts.push({ inlineData: { mimeType, data: imageBytes } });
        } else if (refImg.fileUri) {
             parts.push({ fileData: { mimeType: refImg.mimeType, fileUri: refImg.fileUri } });
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
