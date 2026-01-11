/**
 * Unified Provider Client
 * 
 * This client provides a unified interface to interact with all AI providers
 * through the backend API. It implements the ILLMProvider interface and routes
 * all requests to the appropriate backend endpoints.
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
          credentials: 'include',  // 发送认证 Cookie（向后兼容）
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
        // Call backend API
        console.debug('[UnifiedProviderClient] Sending request:', {
          url: `/api/chat/${this.id}`,
          modelId,
          messageLength: message.length,
          historyLength: history.length,
          attachmentsCount: attachments.length
        });
        
        const response = await fetch(`/api/chat/${this.id}`, {
          method: 'POST',
          headers,
          credentials: 'include',  // 发送认证 Cookie（向后兼容）
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
   * Generate images
   */
  async generateImage(
    modelId: string,
    prompt: string,
    referenceImages: Attachment[],
    options: ChatOptions,
    baseUrl: string
  ): Promise<ImageGenerationResult[]> {
    try {
      const requestBody = {
        modelId,
        prompt,
        referenceImages,
        options: {
          ...options,
          baseUrl: baseUrl || options.baseUrl
        }
        // ✅ API Key 由后端管理，不在前端传递（安全性）
      };
      
      // ✅ 构建请求头，添加 Authorization header
      const headers: HeadersInit = {
        'Content-Type': 'application/json'
      };
      const token = getAccessToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      const response = await fetch(`/api/generate/${this.id}/image`, {
        method: 'POST',
        headers,
        credentials: 'include',  // 发送认证 Cookie（向后兼容）
        body: JSON.stringify(requestBody)
      });
      
      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Image generation failed: ${error}`);
      }
      
      const data = await response.json();
      return data.images || [];
    } catch (error) {
      console.error(`[UnifiedProviderClient] Image generation error for ${this.id}:`, error);
      throw error;
    }
  }
  
  /**
   * Edit images (Google Imagen edit_image API)
   * 
   * Security: API Key is managed by backend, not passed from frontend
   * Authentication: Uses session cookies + JWT token
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
   * @returns Promise<ImageGenerationResult[]> - Array of edited images
   */
  async editImage(
    modelId: string,
    prompt: string,
    referenceImages: Record<string, any>,
    options: ChatOptions,
    baseUrl: string
  ): Promise<ImageGenerationResult[]> {
    try {
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
      
      const requestBody = {
        modelId,
        prompt,
        referenceImages,
        options: {
          ...options,
          baseUrl: baseUrl || options.baseUrl
        }
        // ✅ API Key 由后端管理，不在前端传递（安全性）
      };
      
      // ✅ 构建请求头，添加 Authorization header
      const headers: HeadersInit = {
        'Content-Type': 'application/json'
      };
      const token = getAccessToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      console.debug('[UnifiedProviderClient] Sending image edit request:', {
        url: `/api/generate/${this.id}/image/edit`,
        modelId,
        promptLength: prompt.length,
        referenceImageTypes: Object.keys(referenceImages)
      });
      
      const response = await fetch(`/api/generate/${this.id}/image/edit`, {
        method: 'POST',
        headers,
        credentials: 'include',  // 发送认证 Cookie（向后兼容）
        body: JSON.stringify(requestBody)
      });
      
      if (!response.ok) {
        // ✅ 详细的错误处理
        const contentType = response.headers.get('content-type');
        let errorMessage = `Image editing failed (${response.status})`;
        
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
        
        // ✅ 根据 HTTP 状态码提供友好的错误信息
        switch (response.status) {
          case 400:
            throw new Error(`Invalid request: ${errorMessage}`);
          case 401:
            throw new Error('Authentication required. Please log in again.');
          case 404:
            throw new Error(`Provider "${this.id}" not found or does not support image editing.`);
          case 422:
            throw new Error(`Content policy violation: ${errorMessage}`);
          case 429:
            throw new Error('Rate limit exceeded. Please try again later.');
          case 500:
          case 502:
          case 503:
          case 504:
            throw new Error(`Server error: ${errorMessage}. Please try again later.`);
          default:
            throw new Error(errorMessage);
        }
      }
      
      const data = await response.json();
      console.debug('[UnifiedProviderClient] Image edit response received:', {
        imagesCount: data.images?.length || 0
      });
      
      return data.images || [];
    } catch (error) {
      console.error(`[UnifiedProviderClient] Image editing error for ${this.id}:`, error);
      throw error;
    }
  }
  
  /**
   * Generate video
   */
  async generateVideo(
    prompt: string,
    referenceImages: Attachment[],
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
  ): Promise<VideoGenerationResult> {
    try {
      const requestBody = {
        prompt,
        referenceImages,
        options: {
          ...options,
          baseUrl: baseUrl || options.baseUrl
        },
        apiKey
      };
      
      // ✅ 构建请求头，添加 Authorization header
      const headers: HeadersInit = {
        'Content-Type': 'application/json'
      };
      const token = getAccessToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      const response = await fetch(`/api/generate/${this.id}/video`, {
        method: 'POST',
        headers,
        credentials: 'include',  // 发送认证 Cookie（向后兼容）
        body: JSON.stringify(requestBody)
      });
      
      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Video generation failed: ${error}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error(`[UnifiedProviderClient] Video generation error for ${this.id}:`, error);
      throw error;
    }
  }
  
  /**
   * Generate speech
   */
  async generateSpeech(
    text: string,
    voiceName: string,
    apiKey: string,
    baseUrl: string
  ): Promise<AudioGenerationResult> {
    try {
      const requestBody = {
        text,
        voiceName,
        apiKey,
        baseUrl
      };
      
      // ✅ 构建请求头，添加 Authorization header
      const headers: HeadersInit = {
        'Content-Type': 'application/json'
      };
      const token = getAccessToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      const response = await fetch(`/api/generate/${this.id}/speech`, {
        method: 'POST',
        headers,
        credentials: 'include',  // 发送认证 Cookie（向后兼容）
        body: JSON.stringify(requestBody)
      });
      
      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Speech generation failed: ${error}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error(`[UnifiedProviderClient] Speech generation error for ${this.id}:`, error);
      throw error;
    }
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
        credentials: 'include',  // 发送认证 Cookie（向后兼容）
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
