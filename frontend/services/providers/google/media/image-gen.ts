
import { ImageGenerationResult } from "../../interfaces";
import { ChatOptions } from "../../../../../types";
import { GoogleGenAI } from "@google/genai";

export async function generateTextToImage(
    ai: GoogleGenAI,
    modelId: string, 
    prompt: string, 
    options: ChatOptions
): Promise<ImageGenerationResult[]> {
    
    const isImagen = modelId.toLowerCase().includes('imagen');

    if (isImagen) {
        // --- IMAGEN MODE ---
        const imagenConfig: any = {
            numberOfImages: Math.min(Math.max(options.numberOfImages || 1, 1), 4),
            aspectRatio: options.imageAspectRatio || '1:1', 
            outputMimeType: 'image/jpeg'
        };

        const validGenRatios = ["1:1", "3:4", "4:3", "9:16", "16:9"];
        if (!validGenRatios.includes(imagenConfig.aspectRatio)) {
            imagenConfig.aspectRatio = "1:1";
        }

        try {
            const response = await ai.models.generateImages({
                model: modelId, 
                prompt: prompt,
                config: imagenConfig
            });

            if (!response.generatedImages || response.generatedImages.length === 0) {
                throw new Error("No images generated.");
            }

            return response.generatedImages.map(img => {
                if (!img.image?.imageBytes) throw new Error("Image bytes missing");
                return {
                    url: `data:image/jpeg;base64,${img.image.imageBytes}`,
                    mimeType: 'image/jpeg'
                };
            });

        } catch (e: any) {
             console.error("Imagen Error", e);
             throw new Error(e.message || "Failed to generate image with Imagen.");
        }

    } else {
        // --- GEMINI GEN MODE ---
        let targetModel = modelId;
        if (!targetModel.includes('image') && !targetModel.includes('veo') && !targetModel.includes('vision') && !targetModel.includes('pro')) {
           targetModel = 'gemini-2.5-flash-image';
        }

        const validGenRatios = ["1:1", "3:4", "4:3", "9:16", "16:9"];
        const ratio = validGenRatios.includes(options.imageAspectRatio) 
            ? options.imageAspectRatio 
            : "1:1";

        const config = {
            imageConfig: { aspectRatio: ratio }
        };

        const parts = [{ text: prompt }];

        const generateSingle = async (): Promise<ImageGenerationResult | null> => {
            try {
                const response = await ai.models.generateContent({
                    model: targetModel,
                    contents: { parts },
                    config: config
                });

                if (response.candidates && response.candidates.length > 0) {
                  for (const part of response.candidates[0].content?.parts || []) {
                      if (part.inlineData) {
                          return {
                              url: `data:${part.inlineData.mimeType};base64,${part.inlineData.data}`,
                              mimeType: part.inlineData.mimeType || 'image/png'
                          };
                      }
                  }
                }
                return null;
            } catch (e: any) {
                console.warn(`Gemini Gen Error: ${e.message}`);
                return null;
            }
        };

        const count = Math.max(1, options.numberOfImages || 1);
        if (count > 1) {
            const promises = Array(count).fill(null).map(() => generateSingle());
            const results = await Promise.all(promises);
            const validResults = results.filter((r): r is ImageGenerationResult => r !== null);
            if (validResults.length === 0) throw new Error("Batch generation failed.");
            return validResults;
        } else {
            const res = await generateSingle();
            if (!res) throw new Error("Model returned no image.");
            return [res];
        }
    }
}
