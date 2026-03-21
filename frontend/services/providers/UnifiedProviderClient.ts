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
 *   video-gen, audio-gen, pdf-extract, virtual-try-on, multi-agent
 * - 旧方法 (generateImage, editImage, etc.) 已标记为 @deprecated，内部委托给 executeMode
 */

import { 
  ILLMProvider, 
  StreamUpdate, 
  ImageGenerationResult, 
  VideoGenerationResult, 
  AudioGenerationResult 
} from './interfaces';
import { createParser, type EventSourceMessage, type ParseError } from 'eventsource-parser';
import { ModelConfig, Message, Attachment, ChatOptions } from '../../types/types';
import { withAuthorization } from '../authTokenStore';
import { fetchWithTimeout, parseHttpError, readJsonResponse } from '../http';

const MODE_OPTION_KEYS = new Set([
  'baseUrl',
  'temperature',
  'maxTokens',
  'topP',
  'topK',
  'enableSearch',
  'enableThinking',
  'enableCodeExecution',
  'enableBrowser',
  'enableGrounding',
  'voice',
  'size',
  'quality',
  'style',
  'seconds',
  'videoExtensionCount',
  'storyboardShotSeconds',
  'generateAudio',
  'personGeneration',
  'subtitleMode',
  'subtitleLanguage',
  'subtitleScript',
  'storyboardPrompt',
  'trackedFeature',
  'trackingOverlayText',
  'numberOfImages',
  'aspectRatio',
  'resolution',
  'imageAspectRatio',
  'imageResolution',
  'imageStyle',
  'editMode',
  'frontendSessionId',
  'sessionId',
  'messageId',
  'activeImageUrl',
  'negativePrompt',
  'guidanceScale',
  'maskDilation',
  'seed',
  'outputMimeType',
  'outputCompressionQuality',
  'enhancePrompt',
  'enhancePromptModel',
  'promptExtend',
  'addMagicSuffix',
  'outpaintMode',
  'xScale',
  'yScale',
  'leftOffset',
  'rightOffset',
  'topOffset',
  'bottomOffset',
  'outputRatio',
  'upscaleFactor',
  'layers',
  'canvasW',
  'canvasH',
  'maxTextBoxes',
  'locale',
  'layerDoc',
  'simplifyTolerance',
  'smoothIterations',
  'useBezier',
  'bezierSmoothness',
  'threshold',
  'blurRadius',
  'baseSteps',
  'maskMode',
]);

const MODE_EXTRA_KEYS = new Set([
  'workflow',
  'messages',
  'targetClothing',
  'templateType',
  'additionalInstructions',
  'pdfBytes',
  'pdfUrl',
  'n',
  'numImages',
  'numberOfImages',
  'negativePrompt',
  'promptExtend',
  'addMagicSuffix',
  'enhancePrompt',
  'enhancePromptModel',
  'maskDilation',
  'guidanceScale',
  'outputMimeType',
  'outputCompressionQuality',
  'xScale',
  'yScale',
  'leftOffset',
  'rightOffset',
  'topOffset',
  'bottomOffset',
  'outputRatio',
  'upscaleFactor',
  'angle',
  'watermark',
  'responseFormat',
  'voice',
  'baseSteps',
  'maskMode',
  'videoExtensionCount',
  'storyboardShotSeconds',
  'generateAudio',
  'personGeneration',
  'subtitleMode',
  'subtitleLanguage',
  'subtitleScript',
  'storyboardPrompt',
  'trackedFeature',
  'trackingOverlayText',
]);

function pruneUndefinedEntries(source: Record<string, any>): Record<string, any> {
  return Object.fromEntries(
    Object.entries(source).filter(([, value]) => value !== undefined && value !== null)
  );
}

function normalizeLegacyModeOptions(mode: string, options: Partial<ChatOptions>): Record<string, any> {
  const normalized = pruneUndefinedEntries({ ...(options || {}) });

  if (mode === 'image-outpainting' && normalized.outPainting && typeof normalized.outPainting === 'object') {
    const legacyOutPainting = normalized.outPainting as Record<string, any>;
    if (normalized.outpaintMode === undefined && legacyOutPainting.mode !== undefined) {
      normalized.outpaintMode = legacyOutPainting.mode;
    }
    if (normalized.xScale === undefined && legacyOutPainting.xScale !== undefined) {
      normalized.xScale = legacyOutPainting.xScale;
    }
    if (normalized.yScale === undefined && legacyOutPainting.yScale !== undefined) {
      normalized.yScale = legacyOutPainting.yScale;
    }
    if (normalized.leftOffset === undefined && legacyOutPainting.leftOffset !== undefined) {
      normalized.leftOffset = legacyOutPainting.leftOffset;
    }
    if (normalized.rightOffset === undefined && legacyOutPainting.rightOffset !== undefined) {
      normalized.rightOffset = legacyOutPainting.rightOffset;
    }
    if (normalized.topOffset === undefined && legacyOutPainting.topOffset !== undefined) {
      normalized.topOffset = legacyOutPainting.topOffset;
    }
    if (normalized.bottomOffset === undefined && legacyOutPainting.bottomOffset !== undefined) {
      normalized.bottomOffset = legacyOutPainting.bottomOffset;
    }
    if (normalized.outputRatio === undefined && legacyOutPainting.outputRatio !== undefined) {
      normalized.outputRatio = legacyOutPainting.outputRatio;
    }
    if (normalized.outputRatio === undefined && legacyOutPainting.aspectRatio !== undefined) {
      normalized.outputRatio = legacyOutPainting.aspectRatio;
    }
    if (normalized.upscaleFactor === undefined && legacyOutPainting.upscaleFactor !== undefined) {
      normalized.upscaleFactor = legacyOutPainting.upscaleFactor;
    }
  }

  delete normalized.outPainting;
  delete normalized.multiAgentConfig;
  delete normalized.liveAPIConfig;
  delete normalized.persona;
  delete normalized.deepResearchAgentId;
  delete normalized.enableAutoDeepResearch;
  delete normalized.enableUrlContext;
  delete normalized.enableEnhancedRetrieval;
  delete normalized.enableDeepResearch;
  delete normalized.enableRAG;
  delete normalized.googleCacheMode;
  delete normalized.useGoogleFilesApi;
  delete normalized.loraConfig;
  delete normalized.enableUpscale;
  delete normalized.addWatermark;
  delete normalized.prompt;
  delete normalized.modelId;
  delete normalized.language;
  delete normalized.platform;
  return normalized;
}

function pickAllowedEntries(
  source: Record<string, any>,
  allowedKeys: Set<string>
): { kept: Record<string, any>; droppedKeys: string[] } {
  const kept: Record<string, any> = {};
  const droppedKeys: string[] = [];

  for (const [key, value] of Object.entries(source)) {
    if (value === undefined || value === null) {
      continue;
    }
    if (allowedKeys.has(key)) {
      kept[key] = value;
    } else {
      droppedKeys.push(key);
    }
  }

  return { kept, droppedKeys: droppedKeys.sort() };
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
  async getAvailableModels(apiKey?: string, baseUrl?: string, useCache: boolean = true): Promise<ModelConfig[]> {
    try {
      // Build query parameters
      // ✅ Query 参数使用 camelCase（中间件自动转换为 snake_case）
      const params = new URLSearchParams();
      if (apiKey) {
        params.append('apiKey', apiKey);  // ✅ 传递 API Key 给后端
      }
      if (baseUrl) {
        params.append('baseUrl', baseUrl);
      }
      // ✅ 添加 useCache 参数，验证连接时应该使用 false 强制刷新
      params.append('useCache', String(useCache));

      // Call backend API with timeout protection
      const queryString = params.toString();
      const url = queryString ? `/api/models/${this.id}?${queryString}` : `/api/models/${this.id}`;
      const response = await fetchWithTimeout(url, {
        withAuth: true,
        timeoutMs: 30000,
        timeoutMessage: `Request to ${this.id} API timed out after 30 seconds. Please check your network connection and try again.`,
      });

      if (!response.ok) {
        const parsedError = await parseHttpError(response, 'Failed to get models');
        throw new Error(`Failed to get models: ${parsedError.message}`);
      }

      const data = await readJsonResponse<any>(response);

      // Backend now returns complete ModelConfig objects
      // Use them directly, with fallback for missing capabilities
      return data.models.map((model: Record<string, unknown>) => ({
        id: String(model.id),
        name: String(model.name || model.id),
        description: String(model.description || `${this.id} model: ${model.id}`),
        capabilities: (model.capabilities || { vision: false, search: false, reasoning: false, coding: false }) as Record<string, boolean>,
        contextWindow: Number(model.contextWindow) || this.getDefaultContextWindow(String(model.id))
      }));
    } catch (error) {
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
    baseUrl: string,
    abortSignal?: AbortSignal
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
      const requestBody: Record<string, unknown> = {
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
          personaId: safeOptions.personaId,
          mcpServerKey: safeOptions.mcpServerKey,
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
      const headers = withAuthorization({
        'Content-Type': 'application/json'
      });
      
      // ✅ 不在前端硬编码流式超时：
      // 流式生命周期由上层 abortSignal（用户停止）与后端/SDK 网络策略控制。
      const controller = new AbortController();

      const upstreamAbortListener = () => {
        controller.abort((abortSignal as any)?.reason ?? 'Stream aborted by user');
      };
      if (abortSignal) {
        if (abortSignal.aborted) {
          controller.abort((abortSignal as any)?.reason ?? 'Stream aborted by user');
        } else {
          abortSignal.addEventListener('abort', upstreamAbortListener, { once: true });
        }
      }
      
      try {
        // Call backend API - ✅ 统一使用 /api/modes/{provider}/chat
        
        const response = await fetch(`/api/modes/${this.id}/chat`, {
          method: 'POST',
          headers,
          body: JSON.stringify(requestBody),
          signal: controller.signal
        });
        
        if (!response.ok) {
          const error = await response.text();
          throw new Error(`Chat failed: ${error}`);
        }
        
        // 检查响应类型
        const contentType = response.headers.get('content-type');
        
        // Read SSE stream
        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No response body');
        }
        
        const decoder = new TextDecoder();
        let chunkCount = 0;
        let totalTextLength = 0;
        const pendingUpdates: StreamUpdate[] = [];
        let streamError: Error | null = null;

        const parser = createParser({
          onEvent: (event: EventSourceMessage) => {
            const dataStr = event.data?.trim();
            if (!dataStr || dataStr === '[DONE]') {
              return;
            }

            try {
              const chunk = JSON.parse(dataStr);
              chunkCount++;

              if (chunkCount <= 3 || chunk.chunkType === 'done' || chunk.chunkType === 'error') {
              }

              if (chunk.chunkType === 'error') {
                streamError = new Error(chunk.error || 'Unknown error');
                return;
              }

              if (chunk.chunkType === 'tool_call') {
                const callId = chunk.callId || `tool_call_${chunkCount}`;
                pendingUpdates.push({
                  text: '',
                  browserOperationId: chunk.browserOperationId,
                  toolCall: {
                    id: callId,
                    type: chunk.toolType || 'function_call',
                    name: chunk.toolName,
                    arguments: chunk.toolArgs || {}
                  }
                });
                return;
              }

              if (chunk.chunkType === 'tool_result') {
                const hasScreenshot = chunk.screenshotUrl || chunk.screenshot;
                pendingUpdates.push({
                  text: '',
                  browserOperationId: chunk.browserOperationId,
                  toolResult: {
                    name: chunk.toolName,
                    callId: chunk.callId || '',
                    result: chunk.toolResult || '',
                    error: chunk.toolError,
                    screenshot: chunk.screenshot,
                    screenshotUrl: chunk.screenshotUrl
                  }
                });
                return;
              }

              if (chunk.chunkType === 'reasoning') {
                const thoughtText = chunk.text || '';
                if (thoughtText) {
                  pendingUpdates.push({
                    text: '',
                    chunkType: 'reasoning',
                    thoughts: [{ type: 'text', content: thoughtText }],
                  });
                }
                return;
              }

              const shouldYield = chunk.chunkType === 'done' ||
                                  chunk.chunkType === 'content' ||
                                  chunk.text !== undefined;
              if (!shouldYield) {
                return;
              }

              const text = chunk.text || '';
              totalTextLength += text.length;
              pendingUpdates.push({
                text,
                chunkType: chunk.chunkType,
                attachments: chunk.attachments,
                groundingMetadata: chunk.groundingMetadata,
                urlContextMetadata: chunk.urlContextMetadata,
                browserOperationId: chunk.browserOperationId
              });
            } catch (error) {
              streamError = error instanceof Error ? error : new Error(String(error));
            }
          },
          onError: (error: ParseError) => {
            // For malformed lines, keep stream resilient and continue parsing following events.
          }
        });

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }
          parser.feed(decoder.decode(value, { stream: true }));
          if (streamError) {
            throw streamError;
          }

          while (pendingUpdates.length > 0) {
            const nextUpdate = pendingUpdates.shift();
            if (nextUpdate) {
              yield nextUpdate;
            }
          }
        }

        const rest = decoder.decode();
        if (rest) {
          parser.feed(rest);
          if (streamError) {
            throw streamError;
          }
          while (pendingUpdates.length > 0) {
            const nextUpdate = pendingUpdates.shift();
            if (nextUpdate) {
              yield nextUpdate;
            }
          }
        }
      } catch (error: unknown) {
        if (error instanceof Error && error.name === 'AbortError') {
          if (abortSignal?.aborted || controller.signal.aborted) {
            return;
          }
          throw new Error(
            `Connection to ${this.id} API was interrupted while streaming. Please check your network and try again.`
          );
        }
        throw error;
      } finally {
        if (abortSignal) {
          abortSignal.removeEventListener('abort', upstreamAbortListener);
        }
      }
    } catch (error) {
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
      const normalizedOptions = normalizeLegacyModeOptions(mode, options);
      const normalizedExtra = pruneUndefinedEntries({ ...(extra || {}) });
      const { kept: sanitizedOptions, droppedKeys: droppedOptionKeys } = pickAllowedEntries(normalizedOptions, MODE_OPTION_KEYS);
      const { kept: sanitizedExtra, droppedKeys: droppedExtraKeys } = pickAllowedEntries(normalizedExtra, MODE_EXTRA_KEYS);
      const requestBody = {
        modelId,
        prompt,
        attachments,
        options: sanitizedOptions,
        extra: sanitizedExtra
      };
      
      // ✅ 详细日志：记录发送给后端的参数（特别是 image-gen 模式）
      if (mode === 'image-gen') {
        if (droppedOptionKeys.length > 0 || droppedExtraKeys.length > 0) {
        }
      }
      
      // ✅ 构建请求头，添加 Authorization header
      const headers = withAuthorization({
        'Content-Type': 'application/json'
      });
      
      // ✅ 统一路由: /api/modes/{provider}/{mode}
      const url = `/api/modes/${this.id}/${mode}`;
      if (mode === 'image-gen') {
      }
      
      const response = await fetchWithTimeout(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(requestBody),
        timeoutMs: 0,
      });
      
      if (!response.ok) {
        const parsedError = await parseHttpError(response, `Mode execution failed (${response.status})`);
        throw new Error(parsedError.message);
      }
      
      const data = await readJsonResponse<any>(response);
      // ✅ 新架构统一响应格式: { success: true, data: {...} }
      if (!data.success || data.data === undefined) {
        throw new Error(`Invalid response format: ${JSON.stringify(data)}`);
      }
      
      // ✅ 处理图片生成、编辑、试衣结果（后端已处理，返回标准化格式）
      // 对于 image-gen、image-edit、virtual-try-on 模式，后端返回 { images: [...] }
      const isImageMode = mode === 'image-gen' || 
                          mode.startsWith('image-') || 
                          mode === 'virtual-try-on';
      if (isImageMode && data.data.images) {
        // 将后端格式转换为 ImageGenerationResult[]
        // ✅ 修复：复制后端返回的所有元数据字段，确保前端能获取完整信息
        return data.data.images.map((img: Record<string, unknown>) => ({
          url: img.url,  // 显示URL（可能是 /api/temp-images/{attachment_id} 或 HTTP URL）
          mimeType: img.mimeType || 'image/png',
          filename: img.filename,
          attachmentId: img.attachmentId,
          uploadStatus: img.uploadStatus,
          taskId: img.taskId,
          thoughts: img.thoughts,  // ✅ 修复断点2：传递 thinking 数据
          text: img.text,          // ✅ 修复断点2：传递文本响应
          enhancedPrompt: img.enhancedPrompt,  // ✅ 传递增强后的提示词（如果存在）
          // ✅ 新增：传递完整的附件元数据（后端 CaseConversionMiddleware 会自动转换 snake_case → camelCase）
          messageId: img.messageId,      // 关联的消息 ID
          sessionId: img.sessionId,      // 关联的会话 ID
          userId: img.userId,            // 用户 ID
          size: img.size,                // 文件大小（字节）
          cloudUrl: img.cloudUrl,        // 云存储 URL（如果已上传）
          createdAt: img.createdAt       // 创建时间戳（毫秒）
        } as ImageGenerationResult));
      }
      
      return data.data;
    } catch (error) {
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
    referenceImages: Record<string, Attachment | Attachment[]>,  // ✅ 支持多图：raw 可以是数组
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
    // 重要：保留原始附件的所有字段（特别是 id、uploadStatus、uploadTaskId）
    const attachments: Attachment[] = [];

    // 辅助函数：处理单个附件值
    const processAttachmentValue = (value: unknown, key: string): Attachment | null => {
      if (!value) return null;

      // 如果 value 已经是 Attachment 对象，直接使用（保留所有字段）
      if (typeof value === 'object' && 'id' in value && 'mimeType' in value) {
        return value as Attachment;
      }

      // 构建新的 Attachment 对象（用于字符串类型的值）
      const attachment: Attachment = {
        id: `ref-${key}-${Date.now()}`,
        name: key === 'mask' ? 'mask.png' : 'reference.png',
        mimeType: typeof value === 'object' && (value as Record<string, unknown>).mimeType ? String((value as Record<string, unknown>).mimeType) : 'image/png'
      };

      // 根据值的类型设置 url
      if (typeof value === 'string') {
        attachment.url = value;
      } else if (typeof value === 'object') {
        // ✅ 复制所有可能的字段
        const valObj = value as Record<string, unknown>;
        if (valObj.url) attachment.url = String(valObj.url);
        if (valObj.tempUrl) attachment.tempUrl = String(valObj.tempUrl);
        if (valObj.mimeType) attachment.mimeType = String(valObj.mimeType);
        if (valObj.id) attachment.id = String(valObj.id);  // ✅ 保留原始 id
        if (valObj.uploadStatus) attachment.uploadStatus = String(valObj.uploadStatus) as "completed" | "failed" | "pending" | "uploading";  // ✅ 保留上传状态
        if (valObj.uploadTaskId) attachment.uploadTaskId = String(valObj.uploadTaskId);  // ✅ 保留任务 ID
        if (valObj.name) attachment.name = String(valObj.name);  // ✅ 保留文件名
      }

      return attachment;
    };

    for (const [key, value] of Object.entries(referenceImages)) {
      if (value) {
        // ✅ 支持多图：如果值是数组，遍历处理每个附件
        if (Array.isArray(value)) {
          for (const item of value) {
            const processed = processAttachmentValue(item, key);
            if (processed) {
              attachments.push(processed);
            }
          }
        } else {
          // 单个值
          const processed = processAttachmentValue(value, key);
          if (processed) {
            attachments.push(processed);
          }
        }
      }
    }

    attachments.forEach((att, idx) => {
      const urlPreview = att.url ? (att.url.length > 50 ? att.url.substring(0, 50) + '...' : att.url) : 'N/A';
    });
    
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
    modelId: string,
    prompt: string,
    referenceImages: Attachment[],
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
  ): Promise<VideoGenerationResult> {
    // ✅ 委托给统一模式处理方法
    return await this.executeMode(
      'video-gen',
      modelId,
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
    modelId: string,
    text: string,
    voiceName: string,
    apiKey: string,
    baseUrl: string
  ): Promise<AudioGenerationResult> {
    // ✅ 委托给统一模式处理方法
    return await this.executeMode(
      'audio-gen',
      modelId,
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
      const headers = withAuthorization();
      
      const response = await fetchWithTimeout(`/api/upload/${this.id}`, {
        method: 'POST',
        headers,
        body: formData,
        timeoutMs: 120000,
      });
      
      if (!response.ok) {
        const parsedError = await parseHttpError(response, 'File upload failed');
        throw new Error(`File upload failed: ${parsedError.message}`);
      }
      
      const data = await readJsonResponse<any>(response);
      return data.fileId || data.url;
    } catch (error) {
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
