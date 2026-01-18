/**
 * Unified Provider Client
 * 
 * This client provides a unified interface to interact with all AI providers
 * through the backend API. It implements the ILLMProvider interface and routes
 * all requests to the unified backend endpoints:
 * - All modes (including chat): /api/modes/{provider}/{mode}
 * 
 * All requests use the new unified authentication (JWT Bearer token).
 * 
 * 统一模式处理:
 * - 所有模式都通过 executeMode(mode, ...) 方法统一处理
 * - 支持的模式: image-gen, image-chat-edit, image-mask-edit,
 *   image-inpainting, image-background-edit, image-recontext, image-outpainting,
 *   video-gen, audio-gen, pdf-extract, virtual-try-on, deep-research, multi-agent
 * - 旧方法 (generateImage, editImage, etc.) 已标记为 @deprecated，内部委托给 executeMode
 */

import { 
  ILLMProvider, 
  StreamUpdate, 
  ImageGenerationResult, 
  VideoGenerationResult, 
  AudioGenerationResult 
} from './interfaces';
import { ModelConfig, Message, Attachment, ChatOptions } from '../../types/types';

/**
 * 获取访问令牌
 */
function getAccessToken(): string | null {
    return localStorage.getItem('access_token');
}

export class UnifiedProviderClient implements ILLMProvider {
  public id: string;
  
  constructor(providerId: string) {
    this.id = providerId;
  }
  
  /**
   * Get available models for this provider
   *
   * Backend API Key priority:
   * 1. apiKey parameter (passed via query string) - for verification/testing
   * 2. Database ConfigProfile - for normal operation
   *
   * Backend returns complete ModelConfig objects with capabilities.
   */
  async getAvailableModels(apiKey?: string, baseUrl?: string): Promise<ModelConfig[]> {
    try {
      // Build query parameters
      const params = new URLSearchParams();
      if (apiKey) {
        params.append('apiKey', apiKey);  // ✅ 传递 API Key 给后端
      }
      if (baseUrl) {
        params.append('baseUrl', baseUrl);
      }

      // Call backend API with timeout protection
      const queryString = params.toString();
      const url = queryString ? `/api/models/${this.id}?${queryString}` : `/api/models/${this.id}`;
      
      // ✅ 添加 30 秒超时保护
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);
      
      // ✅ 构建请求头，添加 Authorization header
      const headers: HeadersInit = {};
      const token = getAccessToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      try {
        const response = await fetch(url, {
          headers,
          credentials: 'include',  // 发送认证 Cookie
          signal: controller.signal
        });
        
        clearTimeout(timeoutId);

        if (!response.ok) {
          const error = await response.text();
          throw new Error(`Failed to get models: ${error}`);
        }

        const data = await response.json();

        // Backend now returns complete ModelConfig objects
        // Use them directly, with fallback for missing capabilities
        return data.models.map((model: any) => ({
          id: model.id,
          name: model.name || model.id,
          description: model.description || `${this.id} model: ${model.id}`,
          capabilities: model.capabilities || { vision: false, search: false, reasoning: false, coding: false },
          contextWindow: model.context_window || this.getDefaultContextWindow(model.id)
        }));
      } catch (error: any) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
          throw new Error(`Request to ${this.id} API timed out after 30 seconds. Please check your network connection and try again.`);
        }
        throw error;
      }
    } catch (error) {
      console.error(`[UnifiedProviderClient] Error getting models for ${this.id}:`, error);
      throw error;
    }
  }
  
  /**
   * Send a message and stream the response
   */
  async *sendMessageStream(
    modelId: string,
    history: Message[],
    message: string,
    attachments: Attachment[],
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
  ): AsyncGenerator<StreamUpdate, void, unknown> {
    try {
      // ✅ 输入验证
      if (!modelId || typeof modelId !== 'string') {
        throw new Error('Invalid modelId: must be a non-empty string');
      }
      if (!Array.isArray(history)) {
        throw new Error('Invalid history: must be an array');
      }
      if (typeof message !== 'string') {
        throw new Error('Invalid message: must be a string');
      }
      if (!Array.isArray(attachments)) {
        throw new Error('Invalid attachments: must be an array');
      }
      
      // ✅ 安全访问 options（提供默认值）
      const safeOptions: ChatOptions = options || {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        imageAspectRatio: '1:1',
        imageResolution: '1024x1024'
      };
      
      // Build request body
      // ✅ 不传递 apiKey，让后端从数据库获取（基于用户认证）
      // 只有在明确需要测试/覆盖时才传递 apiKey
      const requestBody: any = {
        modelId,
        messages: history,
        message,
        attachments,
        options: {
          temperature: safeOptions.temperature,
          maxTokens: safeOptions.maxTokens,
          topP: safeOptions.topP,
          topK: safeOptions.topK,
          enableSearch: safeOptions.enableSearch,
          enableThinking: safeOptions.enableThinking,
          enableBrowser: safeOptions.enableBrowser,
          enableCodeExecution: safeOptions.enableCodeExecution,
          enableGrounding: safeOptions.enableGrounding,
          baseUrl: baseUrl || safeOptions.baseUrl
        },
        stream: true
      };
      
      // ✅ 只有在明确需要测试/覆盖时才传递 apiKey（例如：验证连接时）
      // 正常使用时，后端会从数据库获取 API key（基于用户 ID）
      // if (apiKey && /* 测试场景 */) {
      //   requestBody.apiKey = apiKey;
      // }
      
      // ✅ 构建请求头，添加 Authorization header
      const headers: HeadersInit = {
        'Content-Type': 'application/json'
      };
      const token = getAccessToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      // ✅ 添加 60 秒超时保护
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        controller.abort();
        console.error('[UnifiedProviderClient] Request timed out after 60 seconds');
      }, 60000);
      
      try {
        // Call backend API - ✅ 统一使用 /api/modes/{provider}/chat
        console.debug('[UnifiedProviderClient] Sending request:', {
          url: `/api/modes/${this.id}/chat`,
          modelId,
          messageLength: message.length,
          historyLength: history.length,
          attachmentsCount: attachments.length
        });
        
        const response = await fetch(`/api/modes/${this.id}/chat`, {
          method: 'POST',
          headers,
          credentials: 'include',  // 发送认证 Cookie
          body: JSON.stringify(requestBody),
          signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
          const error = await response.text();
          console.error('[UnifiedProviderClient] Request failed:', {
            status: response.status,
            statusText: response.statusText,
            error
          });
          throw new Error(`Chat failed: ${error}`);
        }
        
        // 检查响应类型
        const contentType = response.headers.get('content-type');
        console.debug('[UnifiedProviderClient] Response received:', {
          status: response.status,
          contentType,
          hasBody: !!response.body
        });
        
        // Read SSE stream
        const reader = response.body?.getReader();
        if (!reader) {
          console.error('[UnifiedProviderClient] No response body reader available');
          throw new Error('No response body');
        }
        
        const decoder = new TextDecoder();
        let buffer = '';
        let chunkCount = 0;
        let totalTextLength = 0;
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            console.debug('[UnifiedProviderClient] Stream ended. Total chunks:', chunkCount, 'Total text length:', totalTextLength);
            break;
          }
          
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          
          for (const line of lines) {
            // 跳过空行和注释行
            if (!line.trim() || line.startsWith(':')) {
              continue;
            }
            
            if (line.startsWith('data: ')) {
              try {
                const dataStr = line.slice(6).trim();
                if (!dataStr) continue; // 跳过空的 data 行
                
                const chunk = JSON.parse(dataStr);
                chunkCount++;
                
                // 调试日志（仅在前几个 chunk 或重要事件时记录）
                if (chunkCount <= 3 || chunk.chunk_type === 'done' || chunk.chunk_type === 'error') {
                  console.debug('[UnifiedProviderClient] Chunk #' + chunkCount + ':', {
                    chunk_type: chunk.chunk_type,
                    has_text: !!chunk.text,
                    text_length: chunk.text?.length || 0,
                    text_preview: chunk.text?.substring(0, 50) || ''
                  });
                }
                
                // Convert backend format to frontend format
                if (chunk.chunk_type === 'error') {
                  console.error('[UnifiedProviderClient] Error chunk received:', chunk.error);
                  throw new Error(chunk.error || 'Unknown error');
                }

                // Handle tool_call chunks (Browser function calling)
                if (chunk.chunk_type === 'tool_call') {
                  console.debug('[UnifiedProviderClient] Tool call:', chunk.tool_name, chunk.tool_args);
                  yield {
                    text: '',
                    toolCall: {
                      name: chunk.tool_name,
                      args: chunk.tool_args || {}
                    }
                  } as StreamUpdate;
                  continue;
                }

                // Handle tool_result chunks (Browser function result)
                if (chunk.chunk_type === 'tool_result') {
                  const hasScreenshot = chunk.screenshot_url || chunk.screenshot;
                  console.debug('[UnifiedProviderClient] Tool result:', chunk.tool_name, hasScreenshot ? '(with screenshot)' : '');
                  yield {
                    text: '',
                    toolResult: {
                      name: chunk.tool_name,
                      result: chunk.tool_result || '',
                      screenshot: chunk.screenshot,
                      screenshotUrl: chunk.screenshot_url
                    }
                  } as StreamUpdate;
                  continue;
                }

                // Yield content chunks - 修复：确保所有有效的 chunk 都被 yield
                // 包括 text 为空字符串的情况（可能是中间状态）
                const shouldYield = chunk.chunk_type === 'done' ||
                                  chunk.chunk_type === 'content' ||
                                  chunk.text !== undefined;

                if (shouldYield) {
                  const text = chunk.text || '';
                  totalTextLength += text.length;

                  yield {
                    text,
                    attachments: chunk.attachments,
                    groundingMetadata: chunk.groundingMetadata,
                    urlContextMetadata: chunk.urlContextMetadata,
                    browserOperationId: chunk.browserOperationId
                  } as StreamUpdate;
                }
              } catch (parseError: any) {
                console.error('[UnifiedProviderClient] Error parsing chunk:', {
                  error: parseError.message,
                  line: line.substring(0, 100), // 只记录前100个字符
                  chunkCount
                });
                // ✅ 如果是 JSON 解析错误，继续处理下一个 chunk
                // 如果是其他错误（如 chunk.chunk_type === 'error'），则抛出
                if (parseError.message && 
                    !parseError.message.includes('Unexpected token') && 
                    !parseError.message.includes('JSON') &&
                    !parseError.message.includes('Unexpected end')) {
                  throw parseError;
                }
              }
            }
          }
        }
      } catch (error: any) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
          throw new Error(`Request to ${this.id} API timed out after 60 seconds. Please check your network connection and try again.`);
        }
        throw error;
      }
    } catch (error) {
      console.error(`[UnifiedProviderClient] Stream error for ${this.id}:`, error);
      throw error;
    }
  }
  
  /**
   * 统一模式处理方法
   * 
   * 处理所有模式请求，统一调用 /api/modes/{provider}/{mode}
   * 
   * @param mode - 模式名称 (image-gen, image-chat-edit, image-mask-edit, image-inpainting, image-background-edit, image-recontext, pdf-extract, etc.)
   * @param modelId - 模型 ID
   * @param prompt - 提示词
   * @param attachments - 附件列表（用于图片、PDF等）
   * @param options - 选项（包括 baseUrl 等）
   * @param extra - 额外参数（用于特定模式）
   * @returns Promise<any> - 响应数据
   */
  async executeMode(
    mode: string,
    modelId: string,
    prompt: string,
    attachments: Attachment[] = [],
    options: Partial<ChatOptions> = {},
    extra: Record<string, any> = {}
  ): Promise<any> {
    try {
      const requestBody = {
        modelId,
        prompt,
        attachments,
        options: {
          ...options
        },
        extra
      };
      
      // ✅ 详细日志：记录发送给后端的参数（特别是 image-gen 模式）
      if (mode === 'image-gen') {
        console.log('========== [UnifiedProviderClient] image-gen 模式请求参数 ==========');
        console.log('[image-gen] Provider:', this.id);
        console.log('[image-gen] Model ID:', modelId);
        console.log('[image-gen] Prompt:', prompt.substring(0, 100) + (prompt.length > 100 ? '...' : ''));
        console.log('[image-gen] 用户选择的参数 (options):', {
          numberOfImages: options.numberOfImages,
          imageAspectRatio: options.imageAspectRatio,
          imageResolution: options.imageResolution,
          imageStyle: options.imageStyle,
          negativePrompt: options.negativePrompt,
          seed: options.seed,
          // guidanceScale removed - not officially documented by Google Imagen
          outputMimeType: options.outputMimeType,
          outputCompressionQuality: options.outputCompressionQuality,
          enhancePrompt: options.enhancePrompt,
          enableSearch: options.enableSearch,
          enableThinking: options.enableThinking,
          enableCodeExecution: options.enableCodeExecution,
          enableUrlContext: options.enableUrlContext,
          enableBrowser: options.enableBrowser,
          enableResearch: options.enableResearch,
          googleCacheMode: options.googleCacheMode,
          baseUrl: options.baseUrl,
        });
        console.log('[image-gen] 完整请求体 (requestBody):', JSON.stringify(requestBody, null, 2));
        console.log('[image-gen] 附件数量:', attachments.length);
        console.log('========== [UnifiedProviderClient] image-gen 请求参数结束 ==========');
      }
      
      // ✅ 构建请求头，添加 Authorization header
      const headers: HeadersInit = {
        'Content-Type': 'application/json'
      };
      const token = getAccessToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      // ✅ 统一路由: /api/modes/{provider}/{mode}
      const url = `/api/modes/${this.id}/${mode}`;
      if (mode === 'image-gen') {
        console.log('[image-gen] 请求 URL:', url);
      }
      
      const response = await fetch(url, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify(requestBody)
      });
      
      if (!response.ok) {
        const contentType = response.headers.get('content-type');
        let errorMessage = `Mode execution failed (${response.status})`;
        
        try {
          if (contentType?.includes('application/json')) {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorData.error || errorMessage;
          } else {
            errorMessage = await response.text() || errorMessage;
          }
        } catch (parseError) {
          console.error('[UnifiedProviderClient] Error parsing error response:', parseError);
        }
        
        throw new Error(errorMessage);
      }
      
      const data = await response.json();
      // ✅ 新架构统一响应格式: { success: true, data: {...} }
      if (!data.success || data.data === undefined) {
        throw new Error(`Invalid response format: ${JSON.stringify(data)}`);
      }
      
      return data.data;
    } catch (error) {
      console.error(`[UnifiedProviderClient] Mode execution error for ${this.id}/${mode}:`, error);
      throw error;
    }
  }

  /**
   * Generate images
   * 
   * @deprecated 使用 executeMode('image-gen', ...) 代替
   */
  async generateImage(
    modelId: string,
    prompt: string,
    referenceImages: Attachment[],
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
  ): Promise<ImageGenerationResult[]> {
    // ✅ 委托给统一模式处理方法
    const data = await this.executeMode(
      'image-gen',
      modelId,
      prompt,
      referenceImages,
      { ...options, baseUrl: baseUrl || options.baseUrl }
    );
    return Array.isArray(data) ? data : [];
  }
  
  /**
   * Edit images (Google Imagen edit_image API)
   * 
   * @deprecated 使用 executeMode('image-chat-edit', ...) 代替
   * 
   * @param modelId - Model ID (e.g., "imagen-3.0-capability-001")
   * @param prompt - Edit prompt describing the desired changes
   * @param referenceImages - Dictionary of reference images:
   *   - raw: Base image to edit (required)
   *   - mask: Mask for inpainting (optional)
   *   - control: Control image (optional)
   *   - style: Style reference (optional)
   *   - subject: Subject reference (optional)
   *   - content: Content reference (optional)
   * @param options - Chat options (includes edit_mode, aspect_ratio, etc.)
   * @param baseUrl - Base URL for API endpoint
   * @param mode - 编辑模式 (image-chat-edit, image-mask-edit, image-inpainting, image-background-edit, image-recontext)
   * @returns Promise<ImageGenerationResult[]> - Array of edited images
   */
  async editImage(
    modelId: string,
    prompt: string,
    referenceImages: Record<string, any>,
    options: ChatOptions,
    baseUrl: string,
    mode?: string
  ): Promise<ImageGenerationResult[]> {
    // ✅ 输入验证
    if (!modelId || typeof modelId !== 'string') {
      throw new Error('Invalid modelId: must be a non-empty string');
    }
    if (!prompt || typeof prompt !== 'string') {
      throw new Error('Invalid prompt: must be a non-empty string');
    }
    if (!referenceImages || typeof referenceImages !== 'object') {
      throw new Error('Invalid referenceImages: must be an object');
    }
    if (!referenceImages.raw) {
      throw new Error('Invalid referenceImages: must include "raw" base image');
    }
    
    // ✅ 将 referenceImages 对象转换为 attachments 数组
    const attachments: Attachment[] = [];
    for (const [key, value] of Object.entries(referenceImages)) {
      if (value) {
        // 构建 Attachment 对象（Attachment 接口不包含 role 字段）
        const attachment: Attachment = {
          id: `ref-${key}-${Date.now()}`,
          name: key === 'mask' ? 'mask.png' : 'reference.png',
          mimeType: typeof value === 'object' && value.mimeType ? value.mimeType : 'image/png'
        };
        
        // 根据值的类型设置 url 或 base64Data
        if (typeof value === 'string') {
          if (value.startsWith('data:')) {
            attachment.url = value;
          } else if (value.startsWith('http')) {
            attachment.url = value;
          } else {
            attachment.url = value; // 可能是 base64 字符串
          }
        } else if (typeof value === 'object') {
          if (value.url) attachment.url = value.url;
          if (value.tempUrl) attachment.tempUrl = value.tempUrl;
          if (value.mimeType) attachment.mimeType = value.mimeType;
        }
        
        attachments.push(attachment);
      }
    }
    
    // ✅ 使用统一模式处理方法
    const editMode = mode || 'image-chat-edit';
    const data = await this.executeMode(
      editMode,
      modelId,
      prompt,
      attachments,
      { ...options, baseUrl: baseUrl || options.baseUrl }
    );
    
    return Array.isArray(data) ? data : [];
  }
  
  /**
   * Generate video
   * 
   * @deprecated 使用 executeMode('video-gen', ...) 代替
   */
  async generateVideo(
    prompt: string,
    referenceImages: Attachment[],
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
  ): Promise<VideoGenerationResult> {
    // ✅ 委托给统一模式处理方法
    return await this.executeMode(
      'video-gen',
      '', // modelId 对于 video-gen 可能不需要，但保持接口一致性
      prompt,
      referenceImages,
      { ...options, baseUrl: baseUrl || options.baseUrl }
    );
  }
  
  /**
   * Generate speech
   * 
   * @deprecated 使用 executeMode('audio-gen', ...) 代替
   */
  async generateSpeech(
    text: string,
    voiceName: string,
    apiKey: string,
    baseUrl: string
  ): Promise<AudioGenerationResult> {
    // ✅ 委托给统一模式处理方法
    return await this.executeMode(
      'audio-gen',
      '', // modelId 对于 audio-gen 可能不需要
      text,
      [],
      { 
        baseUrl,
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        imageAspectRatio: '1:1',
        imageResolution: '1024x1024'
      },
      { voice: voiceName }
    );
  }
  
  /**
   * Out-paint image (image expansion)
   * 
   * @deprecated 使用 executeMode('image-outpainting', ...) 代替
   */
  async outPaintImage(
    referenceImage: Attachment,
    options: ChatOptions,
    _apiKey: string, // 已弃用 - 后端从数据库获取
    baseUrl?: string
  ): Promise<ImageGenerationResult> {
    // ✅ 委托给统一模式处理方法
    const data = await this.executeMode(
      'image-outpainting',
      '', // modelId 对于 image-outpainting 可能不需要
      '', // prompt 对于 outpainting 可能不需要
      [referenceImage],
      { ...options, baseUrl: baseUrl || options.baseUrl },
      options.outPainting || {}
    );
    
    // 返回单个结果（outpainting 通常返回单张图片）
    if (Array.isArray(data) && data.length > 0) {
      return data[0];
    }
    return data as ImageGenerationResult;
  }
  
  /**
   * Upload file
   */
  async uploadFile(file: File, apiKey: string, baseUrl: string): Promise<string> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (apiKey) {
        formData.append('apiKey', apiKey);
      }
      if (baseUrl) {
        formData.append('baseUrl', baseUrl);
      }
      
      // ✅ 构建请求头，添加 Authorization header
      const headers: HeadersInit = {};
      const token = getAccessToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      const response = await fetch(`/api/upload/${this.id}`, {
        method: 'POST',
        headers,
        credentials: 'include',  // 发送认证 Cookie
        body: formData
      });
      
      if (!response.ok) {
        const error = await response.text();
        throw new Error(`File upload failed: ${error}`);
      }
      
      const data = await response.json();
      return data.fileId || data.url;
    } catch (error) {
      console.error(`[UnifiedProviderClient] File upload error for ${this.id}:`, error);
      throw error;
    }
  }
  
  // ==================== Helper Methods ====================
  
  /**
   * Get default context window for a model
   * Used as fallback when backend doesn't provide context_window
   */
  private getDefaultContextWindow(modelId: string): number {
    // Default context windows for common models
    const contextWindows: Record<string, number> = {
      'gpt-4': 8192,
      'gpt-4-32k': 32768,
      'gpt-4-turbo': 128000,
      'gpt-4o': 128000,
      'gpt-3.5-turbo': 16385,
      'gemini-pro': 32768,
      'gemini-1.5-pro': 1000000,
      'gemini-1.5-flash': 1000000,
      'claude-3-opus': 200000,
      'claude-3-sonnet': 200000,
      'claude-3-haiku': 200000
    };
    
    // Try exact match
    if (contextWindows[modelId]) {
      return contextWindows[modelId];
    }
    
    // Try partial match
    for (const [key, value] of Object.entries(contextWindows)) {
      if (modelId.includes(key)) {
        return value;
      }
    }
    
    // Default
    return 4096;
  }
}
