
import { VideoGenerationResult } from "../../interfaces";
import { ChatOptions, Attachment } from "../../../../types/types";
import { GoogleGenAI } from "@google/genai";
import { processReferenceImage } from "../../../media/utils";

export async function generateVideo(
    ai: GoogleGenAI,
    prompt: string, 
    referenceImages: Attachment[], 
    options: ChatOptions,
    apiKey: string
): Promise<VideoGenerationResult> {
      
      let ar = '16:9';
      if (options.imageAspectRatio === '9:16') ar = '9:16';
      
      let res = '720p';
      if (options.imageResolution === '2K' || options.imageResolution === '4K') {
          res = '1080p';
      }

      const config: any = {
          numberOfVideos: 1,
          resolution: res, 
          aspectRatio: ar
      };

      if (options.negativePrompt) {
          config.negativePrompt = options.negativePrompt;
      }

      try {
          let operation;
          const hasReferences = referenceImages && referenceImages.length > 0;
          let modelId = 'veo-3.1-fast-generate-preview'; 

          if (referenceImages.length > 2) {
              modelId = 'veo-3.1-generate-preview';
          }

          if (!hasReferences) {
              operation = await ai.models.generateVideos({
                  model: modelId,
                  prompt: prompt,
                  config: config
              });
          } else {
              const processedImages = await Promise.all(referenceImages.map(img => processReferenceImage(img)));

              if (referenceImages.length === 1) {
                  operation = await ai.models.generateVideos({
                      model: modelId,
                      prompt: prompt, 
                      image: { mimeType: processedImages[0].mimeType, imageBytes: processedImages[0].imageBytes },
                      config: config
                  });
              } else if (referenceImages.length === 2) {
                  config.lastFrame = { mimeType: processedImages[1].mimeType, imageBytes: processedImages[1].imageBytes };
                  operation = await ai.models.generateVideos({
                      model: modelId,
                      prompt: prompt,
                      image: { mimeType: processedImages[0].mimeType, imageBytes: processedImages[0].imageBytes }, 
                      config: config
                  });
              } else {
                  const refPayload = processedImages.map(img => ({
                      image: { mimeType: img.mimeType, imageBytes: img.imageBytes },
                      referenceType: 'asset' 
                  }));
                  config.referenceImages = refPayload;
                  operation = await ai.models.generateVideos({
                      model: modelId,
                      prompt: prompt,
                      config: config
                  });
              }
          }

          while (!operation.done) {
              await new Promise(resolve => setTimeout(resolve, 5000));
              operation = await ai.operations.getVideosOperation({ operation: operation });
          }

          // @ts-ignore
          if (operation.error) {
              // @ts-ignore
              const errMsg = operation.error.message || operation.error.code || 'Unknown error';
              throw new Error(`Veo failed: ${errMsg}`);
          }

          const videoUri = operation.response?.generatedVideos?.[0]?.video?.uri;
          if (!videoUri) throw new Error("No video URI returned.");

          const videoRes = await fetch(`${videoUri}&key=${apiKey}`);
          if (!videoRes.ok) throw new Error("Failed to download video.");
          
          const videoBlob = await videoRes.blob();
          const localUrl = URL.createObjectURL(videoBlob);

          return {
              url: localUrl,
              mimeType: 'video/mp4'
          };

      } catch (e: any) {
           console.error("Veo Error", e);
           throw new Error(e.message || "Failed to generate video");
      }
}
