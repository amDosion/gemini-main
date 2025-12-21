
import { GenerateContentResponse, FunctionDeclaration, Type } from "@google/genai";
import { ILLMProvider, StreamUpdate, ImageGenerationResult, VideoGenerationResult, AudioGenerationResult } from "../interfaces";
import { ModelConfig, Message, Attachment, ChatOptions } from "../../../types/types";
import { GoogleResponseParser } from "./parser";
import { getGoogleModels } from "./models";
import { createGoogleClient } from "./utils";
import { googleMediaStrategy } from "./media";
import { googleFileService } from "./fileService";

// 兼容性 UUID 生成函数（支持非安全上下文和旧版浏览器）
function generateUUID(): string {
  // 优先使用原生 crypto.randomUUID（安全上下文下可用）
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // 回退方案：使用 crypto.getRandomValues
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = crypto.getRandomValues(new Uint8Array(1))[0] % 16;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }
  // 最终回退：Math.random（不推荐，但保证可用）
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// Tool Definition for Browser
const browserToolDeclaration: FunctionDeclaration = {
  name: "browse_webpage",
  description: "Visits a website to capture its visual layout (screenshot) and text content. Use this when asked to 'go to', 'look at', 'visit', or 'browse' a specific URL.",
  parameters: {
    type: Type.OBJECT,
    properties: {
      url: { type: Type.STRING, description: "The full URL to visit (e.g., https://example.com)" },
    },
    required: ["url"]
  }
};

export class GoogleProvider implements ILLMProvider {
  public id = 'google';

  public async getAvailableModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
    return getGoogleModels(apiKey, baseUrl);
  }

  public async uploadFile(file: File, apiKey: string, baseUrl: string): Promise<string> {
    return googleFileService.uploadFile(file, apiKey, baseUrl);
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
    
    const ai = createGoogleClient(apiKey, baseUrl);
    
    const formattedHistory = history.map(msg => {
        const parts: any[] = [];
        let textContent = msg.content || "";

        if (msg.attachments && msg.attachments.length > 0) {
            msg.attachments.forEach(att => {
                if (att.mimeType === 'video/external' || att.mimeType === 'text/link') {
                    textContent += `\n\n[Attached Link: ${att.fileUri}]`;
                } else if (att.fileUri) {
                    parts.push({ fileData: { mimeType: att.mimeType, fileUri: att.fileUri } });
                } else if (att.url && att.url.startsWith('data:')) {
                    const match = att.url.match(/^data:(.*?);base64,(.*)$/);
                    if (match) parts.push({ inlineData: { mimeType: match[1], data: match[2] } });
                }
            });
        }
        
        if (textContent) parts.push({ text: textContent });
        
        return { role: msg.role, parts: parts };
    });

    const config: any = {
        systemInstruction: "You are a helpful AI assistant. Use Markdown for formatting.",
        tools: []
    };

    const isThinkingActive = options.enableThinking || modelId.includes('thinking') || modelId.includes('reasoning');

    // 1. Google Search
    if (options.enableSearch && !isThinkingActive) {
        config.tools.push({ googleSearch: {} });
    }
    
    // 2. URL Context (Grounding)
    if (options.enableUrlContext && !isThinkingActive) {
        config.tools.push({ urlContext: {} });
    }
    
    // 3. Code Execution
    if (options.enableCodeExecution && !isThinkingActive) {
        config.tools.push({ codeExecution: {} });
    }
    
    // 4. Browser Tool
    if (options.enableBrowser && !isThinkingActive) {
        config.tools.push({ functionDeclarations: [browserToolDeclaration] });
    }

    // 5. Thinking Config
    if (options.enableThinking) {
        config.thinkingConfig = { includeThoughts: true }; 
    }

    // 6. Implicit Caching (Cache Mode)
    // Note: Implicit caching relies on passing a `cacheMode` parameter (often 'exact' or 'semantic') 
    // to the generation config or request options depending on the API version. 
    // We inject it into the config here, assuming the SDK/API will read it.
    if (options.googleCacheMode && options.googleCacheMode !== 'none') {
        const modeMap: Record<string, string> = {
            'exact': 'CACHE_MODE_EXACT',
            'semantic': 'CACHE_MODE_SEMANTIC'
        };
        // @ts-ignore - Injecting experimental/implicit cache param
        config.cacheMode = modeMap[options.googleCacheMode] || 'CACHE_MODE_UNSPECIFIED';
    }
    
    if (config.tools.length === 0) delete config.tools;

    const chat = ai.chats.create({
        model: modelId,
        config: config,
        history: formattedHistory
    });

    const currentParts: any[] = [];
    let currentText = message;

    if (attachments && attachments.length > 0) {
        attachments.forEach(att => {
            if (att.mimeType === 'video/external' || att.mimeType === 'text/link') {
                 currentText += `\n\n[Attached Link: ${att.fileUri}]`;
            } else if (att.fileUri) {
                currentParts.push({ fileData: { mimeType: att.mimeType, fileUri: att.fileUri } });
            } else if (att.url && att.url.startsWith('data:')) {
                const match = att.url.match(/^data:(.*?);base64,(.*)$/);
                if (match) currentParts.push({ inlineData: { mimeType: match[1], data: match[2] } });
            }
        });
    }
    
    if (currentText) currentParts.push({ text: currentText });

    const parser = new GoogleResponseParser();
    
    let activeStream = await chat.sendMessageStream({ message: currentParts });
    
    // Process the stream loop for potential tool calls
    while (true) {
        let functionCall = null;

        for await (const chunk of activeStream) {
            const candidates = (chunk as GenerateContentResponse).candidates;
            if (candidates && candidates[0]?.content?.parts) {
                for (const part of candidates[0].content.parts) {
                    if (part.functionCall) {
                        functionCall = part.functionCall;
                    }
                }
            }
            yield* parser.parseChunk(chunk as GenerateContentResponse);
        }

        if (functionCall && functionCall.name === 'browse_webpage') {
            const url = (functionCall.args as any).url;
            
            // Generate Operation ID for tracking
            const operationId = generateUUID();
            
            // Yield ID to frontend immediately so indicator shows up
            yield { 
                text: `\n\n> 🌍 **Browsing**: ${url} ...\n\n`,
                browserOperationId: operationId
            };

            try {
                // 通过 Vite 代理访问后端（避免 CORS 问题）
                const response = await fetch('/api/browse', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    // Pass operation_id to backend for SSE connection
                    body: JSON.stringify({ url, operation_id: operationId })
                });

                if (!response.ok) throw new Error(`Backend Error: ${response.statusText}`);
                const data = await response.json();
                
                const toolResponseParts: any[] = [
                    {
                        functionResponse: {
                            name: 'browse_webpage',
                            response: { result: data.markdown, title: data.title }
                        }
                    }
                ];

                if (data.screenshot) {
                    toolResponseParts.push({
                        inlineData: { mimeType: 'image/jpeg', data: data.screenshot }
                    });
                    yield {
                        text: '',
                        attachments: [{
                            id: generateUUID(),
                            mimeType: 'image/jpeg',
                            name: `Screenshot - ${data.title || 'Page'}`,
                            url: `data:image/jpeg;base64,${data.screenshot}`
                        }]
                    };
                }

                activeStream = await chat.sendMessageStream({ message: toolResponseParts });
                continue;

            } catch (err: any) {
                yield { text: `\n> ❌ **Browse Failed**: ${err.message}\n` };
                activeStream = await chat.sendMessageStream({
                    message: [{
                        functionResponse: {
                            name: 'browse_webpage',
                            response: { error: err.message }
                        }
                    }]
                });
                continue;
            }
        }
        break;
    }

    yield* parser.finalize();
  }

  public async generateImage(modelId: string, prompt: string, referenceImages: Attachment[], options: ChatOptions, apiKey: string, baseUrl: string): Promise<ImageGenerationResult[]> {
      return googleMediaStrategy.generateImage(modelId, prompt, referenceImages, options, apiKey, baseUrl);
  }

  public async generateVideo(prompt: string, referenceImages: Attachment[], options: ChatOptions, apiKey: string, baseUrl: string): Promise<VideoGenerationResult> {
      return googleMediaStrategy.generateVideo(prompt, referenceImages, options, apiKey, baseUrl);
  }

  public async generateSpeech(text: string, voiceName: string, apiKey: string, baseUrl: string): Promise<AudioGenerationResult> {
      return googleMediaStrategy.generateSpeech(text, voiceName, apiKey, baseUrl);
  }
}
