
import { ILLMProvider, StreamUpdate, ImageGenerationResult, VideoGenerationResult, AudioGenerationResult } from "../interfaces";
import { ModelConfig, Message, Attachment, ChatOptions, Role } from "../../../types/types";
import { contextManager } from "../../ai_tools/ContextManager";

export class OpenAIProvider implements ILLMProvider {
  public id = 'openai';

  private getCleanUrl(baseUrl: string): string {
      let cleanUrl = baseUrl ? baseUrl.trim().replace(/\/$/, '') : '';
      if (!cleanUrl) cleanUrl = 'https://api.openai.com/v1';
      return cleanUrl;
  }

  public async getAvailableModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
    try {
      const cleanUrl = this.getCleanUrl(baseUrl);
      const response = await fetch(`${cleanUrl}/models`, {
        headers: { 'Authorization': `Bearer ${apiKey}` }
      });

      if (!response.ok) throw new Error(`API Error: ${response.status}`);
      const data = await response.json();
      const models = data.data || [];

      return models.map((m: any) => {
        const id = m.id;
        const lowerId = id.toLowerCase();
        
        const isVision = lowerId.includes('vision') || lowerId.includes('4o') || lowerId.includes('gemini') || lowerId.includes('vl');
        const isReasoning = lowerId.includes('reasoning') || lowerId.includes('thinking') || lowerId.includes('deepseek-r1') || lowerId.includes('o1') || lowerId.includes('o3');
        const isCoding = lowerId.includes('code') || lowerId.includes('coder') || true; 

        return {
          id: id,
          name: id,
          description: 'External Model',
          capabilities: {
            vision: isVision,
            search: false, 
            reasoning: isReasoning,
            coding: isCoding
          },
          baseModelId: id
        };
      }).sort((a: any, b: any) => a.id.localeCompare(b.id));

    } catch (e) {
      console.warn("Failed to fetch generic models", e);
      return [];
    }
  }

  public async uploadFile(file: File, apiKey: string, baseUrl: string): Promise<string> {
    throw new Error("File upload not supported in OpenAI Compatibility mode. Using inline data.");
  }

  public async *sendMessageStream(
    modelId: string,
    history: Message[],
    message: string,
    attachments: Attachment[],
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
  ): AsyncGenerator<StreamUpdate, void, unknown> {
    
    // 1. Prepare Raw Messages
    const messagesPayload: any[] = [];

    // System Prompt (Persona)
    if (options.persona) {
        messagesPayload.push({ role: "system", content: options.persona.systemPrompt });
    } else {
        messagesPayload.push({ role: "system", content: "You are a helpful AI assistant. Use Markdown for formatting." });
    }

    // History
    for (const msg of history) {
        if (msg.isError) continue;
        const role = msg.role === Role.USER ? "user" : "assistant";
        // Simple text content for context estimation
        messagesPayload.push({ role: role, content: msg.content }); 
    }

    // 2. Apply Context Optimization
    const optimizedMessages = contextManager.optimizeContext(messagesPayload, 128000);

    // 3. Append Current User Message (Never truncated)
    const userContent: any[] = [];
    if (message) userContent.push({ type: "text", text: message });

    for (const att of attachments) {
        if (att.mimeType.startsWith('image/') && att.url) {
            userContent.push({
                type: "image_url",
                image_url: { url: att.url } 
            });
        }
    }
    
    if (userContent.length === 1 && userContent[0].type === 'text') {
        optimizedMessages.push({ role: "user", content: userContent[0].text });
    } else {
        optimizedMessages.push({ role: "user", content: userContent });
    }

    const cleanUrl = this.getCleanUrl(baseUrl);
    
    const response = await fetch(`${cleanUrl}/chat/completions`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
            model: modelId,
            messages: optimizedMessages, // Use optimized list
            stream: true,
            temperature: 0.7, 
            max_tokens: options.enableThinking ? 8192 : 4096 
        })
    });

    if (!response.ok) {
        const err = await response.text();
        throw new Error(`API Error: ${response.status} - ${err}`);
    }
    if (!response.body) throw new Error("No response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let isThinking = false; 

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed.startsWith('data: ')) continue;
                const data = trimmed.slice(6);
                if (data === '[DONE]') continue;

                try {
                    const json = JSON.parse(data);
                    const delta = json.choices[0]?.delta;
                    if (!delta) continue;

                    const content = delta.content;
                    const reasoning = delta.reasoning_content;
                    
                    if (reasoning) {
                        if (!isThinking) {
                             yield { text: "<thinking>" };
                             isThinking = true;
                        }
                        yield { text: reasoning };
                    }
                    
                    if (content) {
                        if (isThinking) {
                             yield { text: "</thinking>\n" };
                             isThinking = false;
                        }
                        yield { text: content };
                    }
                } catch (e) {}
            }
        }
    } finally {
        if (isThinking) {
            yield { text: "</thinking>\n" };
        }
        reader.releaseLock();
    }
  }

  public async generateImage(
      modelId: string, 
      prompt: string, 
      referenceImages: Attachment[], 
      options: ChatOptions, 
      apiKey: string, 
      baseUrl: string
  ): Promise<ImageGenerationResult[]> {
      
      const cleanUrl = this.getCleanUrl(baseUrl);
      const referenceImage = referenceImages[0];
      const endpoint = referenceImage ? `${cleanUrl}/images/edits` : `${cleanUrl}/images/generations`;
      const isEdit = !!referenceImage;
      
      if (isEdit) throw new Error("Image Editing not fully supported for generic OpenAI endpoint yet.");

      let size = "1024x1024";
      if (options.imageAspectRatio === '16:9') size = "1792x1024"; 
      if (options.imageAspectRatio === '9:16') size = "1024x1792";
      
      const useModel = modelId.includes('dall') ? modelId : "dall-e-3";

      const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`
          },
          body: JSON.stringify({
              model: useModel,
              prompt: prompt,
              n: 1, 
              size: size,
              response_format: "b64_json",
              quality: "standard" 
          })
      });

      if (!response.ok) throw new Error(`OpenAI Image API Error: ${await response.text()}`);

      const data = await response.json();
      const b64 = data.data?.[0]?.b64_json;
      if (!b64) throw new Error("No image data returned");

      return [{
          url: `data:image/png;base64,${b64}`,
          mimeType: 'image/png'
      }];
  }

  public async generateVideo(prompt: string, referenceImages: Attachment[], options: ChatOptions, apiKey: string, baseUrl: string): Promise<VideoGenerationResult> {
      throw new Error("Video generation not supported in generic mode.");
  }

  public async generateSpeech(text: string, voiceName: string, apiKey: string, baseUrl: string): Promise<AudioGenerationResult> {
      throw new Error("TTS not supported in generic mode.");
  }
}
