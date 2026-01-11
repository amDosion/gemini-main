
import { AudioGenerationResult } from "../../interfaces";
import { GoogleGenAI, Modality } from "@google/genai";
import { pcmToWav } from "../../../media/utils";

export async function generateSpeech(
    ai: GoogleGenAI,
    text: string, 
    voiceName: string
): Promise<AudioGenerationResult> {
       const response = await ai.models.generateContent({
          model: "gemini-2.5-flash-preview-tts",
          contents: [{ parts: [{ text: text }] }],
          config: {
            responseModalities: [Modality.AUDIO],
            speechConfig: {
                voiceConfig: {
                  prebuiltVoiceConfig: { voiceName: voiceName || 'Puck' },
                },
            },
          },
       });

       const base64Audio = response.candidates?.[0]?.content?.parts?.[0]?.inlineData?.data;
       if (!base64Audio) throw new Error("No audio generated.");
       
       const binaryString = atob(base64Audio);
       const len = binaryString.length;
       const bytes = new Uint8Array(len);
       for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
       }
       
       const wavBlob = pcmToWav(bytes);
       const url = URL.createObjectURL(wavBlob);

       return {
           url: url,
           mimeType: 'audio/wav'
       };
}
