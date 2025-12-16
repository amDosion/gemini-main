
import { useState, useCallback } from 'react';
import { Message, Role, LoadingState, ChatOptions, Attachment, AppMode, ModelConfig } from '../../types';
import { v4 as uuidv4 } from 'uuid';
import { llmService } from '../services/llmService';
import { addCitations } from '../utils/groundingUtils';
import { PdfExtractionService } from '../services/pdfExtractionService';
import { storageUpload } from '../services/storage/storageUpload';

export const useChat = (
  currentSessionId: string | null,
  updateSessionMessages: (id: string, msgs: Message[]) => void,
  apiKey?: string
) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingState, setLoadingState] = useState<LoadingState>('idle');

  const stopGeneration = useCallback(() => {
      llmService.cancelCurrentStream();
      setLoadingState('idle');
  }, []);

  /**
   * 将 Base64 Data URL 转换为 File 对象
   */
  const base64ToFile = async (base64: string, filename: string): Promise<File> => {
    const response = await fetch(base64);
    const blob = await response.blob();
    return new File([blob], filename, { type: blob.type });
  };

  /**
   * 异步上传图片到云存储（不阻塞前端）
   * 
   * ✅ 优化后的上传逻辑：
   * - 支持 File 对象、Base64 Data URL 两种方式
   * - 提交到后端队列处理，不阻塞前端
   * - 后端上传完成后自动更新数据库
   * - 前端继续显示 Blob URL / Base64，重载网页后从数据库加载永久 URL
   */
  const uploadToCloudStorage = async (
    imageSource: string | File,
    messageId: string,
    attachmentId: string,
    sessionId: string,
    filename?: string
  ) => {
    try {
      const isFile = imageSource instanceof File;
      const isBase64 = typeof imageSource === 'string' && imageSource.startsWith('data:');
      
      console.log('[useChat] 提交异步上传任务:', 
        isFile ? `File: ${(imageSource as File).name}` : 
        isBase64 ? 'Base64 Data URL' : 
        'Unknown'
      );

      let file: File;

      if (isFile) {
        file = imageSource as File;
      } else if (isBase64) {
        // Base64 转换为 File
        file = await base64ToFile(imageSource as string, filename || `image-${Date.now()}.png`);
        console.log('[useChat] Base64 已转换为 File:', file.name, file.type, file.size);
      } else {
        throw new Error(`不支持的图片来源格式`);
      }

      // ✅ 提交到后端异步上传队列（不等待完成）
      const result = await storageUpload.uploadFileAsync(file, {
        sessionId,
        messageId,
        attachmentId
      });
      
      console.log('[useChat] 异步上传任务已提交:', result.taskId);
      // 不等待上传完成，后端会自动更新数据库

    } catch (error) {
      console.error('[useChat] 提交上传任务失败:', error);
      // 上传失败时不更新状态，保持原有显示
    }
  };

  const sendMessage = async (
    text: string,
    options: ChatOptions,
    attachments: Attachment[],
    mode: AppMode,
    currentModel: ModelConfig,
    protocol: 'google' | 'openai'
  ) => {
    if (!currentSessionId) return;

    // 1. Initialize Service Context
    const contextHistory = messages.filter(m => m.mode === mode || (!m.mode && mode === 'chat'));
    llmService.startNewChat(contextHistory, currentModel, options);

    // 2. Upload Handling (Google Specific)
    let processedAttachments: Attachment[] = [...attachments];
    if (protocol === 'google' && mode === 'chat') {
      const filesToUpload = attachments.filter(a => a.file);
      if (filesToUpload.length > 0) {
        setLoadingState('uploading');
        try {
          const uploaded = await Promise.all(filesToUpload.map(async (att) => {
            if (att.file) {
              const uri = await llmService.uploadFile(att.file);
              return { ...att, fileUri: uri, file: undefined };
            }
            return att;
          }));
          processedAttachments = attachments.map(att => {
            const uploadedAtt = uploaded.find(u => u.id === att.id);
            return uploadedAtt || att;
          });
        } catch (error) {
          console.error("Upload failed", error);
          // Don't stop execution here, try to proceed or let the main error handler catch downstream issues
          // But actually, if upload fails, generation usually fails.
          // Let's rethrow to be caught by main block for consistent UI error
          throw error;
        }
      }
    }

    // 3. Optimistic User Message
    const userMessage: Message = {
      id: uuidv4(),
      role: Role.USER,
      content: text,
      attachments: processedAttachments,
      timestamp: Date.now(),
      mode: mode, 
    };

    // ✅ 优化：保存到数据库时，清理临时 URL 和 File 对象
    // 避免重载网页后显示无效的 Blob URL 或过大的 Base64
    const cleanAttachmentsForDb = (atts: Attachment[]): Attachment[] => {
      return atts.map(att => {
        const cleaned = { ...att };
        // 如果 url 是 Blob URL，设置为空字符串（等待上传完成后更新）
        if (cleaned.url && cleaned.url.startsWith('blob:')) {
          cleaned.url = '';
          cleaned.uploadStatus = 'pending';
        }
        // 如果 url 是 Base64 Data URL，也设置为空字符串（避免数据库存储过大）
        if (cleaned.url && cleaned.url.startsWith('data:')) {
          cleaned.url = '';
          cleaned.uploadStatus = 'pending';
        }
        // 清除 File 对象（不能序列化）
        delete cleaned.file;
        // 清除 tempUrl（临时 URL 不需要持久化）
        delete cleaned.tempUrl;
        // ✅ 清除 base64Data（仅用于 Google API 调用，不需要持久化到数据库）
        delete (cleaned as any).base64Data;
        return cleaned;
      });
    };

    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    
    // 保存到数据库时使用清理后的附件
    const messagesForDb = updatedMessages.map(msg => ({
      ...msg,
      attachments: msg.attachments ? cleanAttachmentsForDb(msg.attachments) : []
    }));
    updateSessionMessages(currentSessionId, messagesForDb);
    setLoadingState(mode === 'chat' ? 'streaming' : 'loading');

    // 4. Model Placeholder
    const modelMessageId = uuidv4();
    const initialModelMessage: Message = {
      id: modelMessageId,
      role: Role.MODEL,
      content: '',
      attachments: [],
      timestamp: Date.now(),
      mode: mode, 
    };

    setMessages(prev => [...prev, initialModelMessage]);

    // 5. Execution Pipeline
    try {
      if (mode === 'chat') {
        const stream = llmService.sendMessageStream(text, processedAttachments);
        let accumulatedText = '';
        const accumulatedAttachments: Attachment[] = [];
        let lastGroundingMetadata: any = undefined;
        let lastUrlContextMetadata: any = undefined; // Track URL Context Metadata
        let lastBrowserOperationId: string | undefined = undefined; // Track Browser Operation ID

        for await (const chunk of stream) {
          if (chunk.text) accumulatedText += chunk.text;
          if (chunk.attachments && chunk.attachments.length > 0) accumulatedAttachments.push(...chunk.attachments);
          if (chunk.groundingMetadata) lastGroundingMetadata = chunk.groundingMetadata;
          if (chunk.urlContextMetadata) lastUrlContextMetadata = chunk.urlContextMetadata; // Capture URL metadata
          if (chunk.browserOperationId) lastBrowserOperationId = chunk.browserOperationId; // Capture Browser ID

          setMessages(prev =>
            prev.map(msg =>
              msg.id === modelMessageId
                ? {
                  ...msg,
                  content: accumulatedText,
                  attachments: [...accumulatedAttachments],
                  groundingMetadata: lastGroundingMetadata,
                  urlContextMetadata: lastUrlContextMetadata,
                  browserOperationId: lastBrowserOperationId // Update message state
                }
                : msg
            )
          );
        }

        let finalText = accumulatedText;
        if (lastGroundingMetadata) finalText = addCitations(finalText, lastGroundingMetadata);

        const finalMessages = [...updatedMessages, {
          ...initialModelMessage,
          content: finalText,
          attachments: accumulatedAttachments,
          groundingMetadata: lastGroundingMetadata,
          urlContextMetadata: lastUrlContextMetadata,
          browserOperationId: lastBrowserOperationId
        }];
        updateSessionMessages(currentSessionId, finalMessages);

      } else {
        // Specialized Modes (Gen/Edit) - No changes needed here for browser tool
        let finalContent = "";
        let resultArray: Attachment[] = [];

        // ... [Specialized mode logic remains same as original] ...
        if (mode === 'image-gen' || mode === 'image-edit') {
          const results = await llmService.generateImage(text, processedAttachments);
          
          // ✅ 构建结果数组，添加上传状态标记
          resultArray = results.map((res, index) => {
            const attachmentId = uuidv4();
            return {
              id: attachmentId,
              mimeType: res.mimeType,
              name: mode === 'image-edit' 
                ? `edited-${Date.now()}-${index + 1}.png` 
                : `generated-${Date.now()}-${index + 1}.png`,
              url: res.url,           // Base64 Data URL 用于立即显示
              tempUrl: res.url,       // 保留临时 URL
              uploadStatus: 'pending' as const  // ✅ 标记待上传
            };
          });
          
          finalContent = mode === 'image-edit' 
            ? `Edited image with: "${text}"` 
            : `Generated images for: "${text}"`;
          
          // ✅ 异步上传原图到云存储（如果有 File 对象）
          for (const att of processedAttachments) {
            if (att.file) {
              console.log('[useChat] 上传原图到云存储:', att.name);
              uploadToCloudStorage(
                att.file,
                userMessage.id,
                att.id,
                currentSessionId,
                att.name
              );
            }
          }
          
          // ✅ 异步上传结果图到云存储（不阻塞 UI 显示）
          for (const att of resultArray) {
            console.log('[useChat] 上传结果图到云存储:', att.name);
            uploadToCloudStorage(
              att.url,
              modelMessageId,
              att.id,
              currentSessionId,
              att.name
            );
          }
        }
        else if (mode === 'image-outpainting') {
          // 获取原图信息
          const originalAttachment = processedAttachments[0];
          const originalAttachmentId = originalAttachment.id;
          
          // 调用扩图 API
          const result = await llmService.outPaintImage(originalAttachment);
          
          // ✅ 优化：下载结果图创建 Blob（用于立即显示 + 上传）
          // 只下载一次，避免后端重复下载
          const imageBlob = await fetch(result.url).then(r => r.blob());
          const blobUrl = URL.createObjectURL(imageBlob);
          const resultFilename = `expanded-${Date.now()}.png`;
          const resultFile = new File([imageBlob], resultFilename, { type: 'image/png' });
          
          const resultAttachmentId = uuidv4();
          resultArray = [{ 
            id: resultAttachmentId,
            mimeType: result.mimeType,
            name: resultFilename,
            url: blobUrl,      // ✅ 改为 Blob URL（用于显示）
            tempUrl: blobUrl,  // Blob URL
            uploadStatus: 'pending'
          }];
          finalContent = `扩展后的图片`;
          
          // 异步上传原图到云存储（使用 File 对象直接上传）
          if (originalAttachment.file) {
            console.log('[useChat] 上传原图到云存储（File 对象）...');
            uploadToCloudStorage(
              originalAttachment.file, 
              userMessage.id, 
              originalAttachmentId, 
              currentSessionId,
              originalAttachment.name
            );
          }
          
          // ✅ 优化：异步上传结果图到云存储（传 File 对象，不传 URL）
          // 避免后端重复下载
          console.log('[useChat] 上传结果图到云存储（File 对象）...');
          uploadToCloudStorage(
            resultFile,  // ✅ 直接传 File 对象
            modelMessageId, 
            resultAttachmentId, 
            currentSessionId,
            resultFilename
          );
        }
        else if (mode === 'video-gen') {
          const result = await llmService.generateVideo(text, processedAttachments);
          resultArray = [{ id: uuidv4(), mimeType: result.mimeType, name: 'Video.mp4', url: result.url }];
          finalContent = `Generated video: "${text}"`;
        }
        else if (mode === 'audio-gen') {
          const result = await llmService.generateSpeech(text);
          resultArray = [{ id: uuidv4(), mimeType: result.mimeType, name: 'Audio.wav', url: result.url }];
          finalContent = `Generated speech.`;
        }
        else if (mode === 'pdf-extract') {
          // PDF Structured Data Extraction
          const pdfFile = processedAttachments.find(att => att.file && att.mimeType === 'application/pdf')?.file;

          if (!pdfFile) {
            throw new Error('No PDF file provided for extraction');
          }

          const templateType = options.pdfExtractTemplate || 'invoice';

          // Use the API key from the hook parameter
          if (!apiKey) {
            throw new Error('API key is required for PDF extraction. Please configure it in Settings.');
          }

          if (!currentModel || !currentModel.id) {
            throw new Error('Model is required for PDF extraction. Please select a model.');
          }

          // Pass the selected model ID
          // Use baseModelId if available (for aliased models), otherwise use id
          const modelIdToUse = currentModel.baseModelId || currentModel.id;
          
          console.log('[PDF Extract] Using model:', modelIdToUse, 'from currentModel:', currentModel);

          const extractionResult = await PdfExtractionService.extractFromPdf(
            pdfFile,
            templateType,
            apiKey,
            text, // Use the prompt text as additional instructions
            modelIdToUse
          );

          // Format the result as JSON string for display
          finalContent = JSON.stringify(extractionResult, null, 2);
          resultArray = [];
        }

        const finalModelMessage = { ...initialModelMessage, content: finalContent, attachments: resultArray };
        setMessages(prev => prev.map(msg => msg.id === modelMessageId ? finalModelMessage : msg));
        
        // ✅ 优化：保存到数据库时，清理 Blob URL
        const finalModelMessageForDb = {
          ...finalModelMessage,
          attachments: cleanAttachmentsForDb(resultArray)
        };
        const allMessagesForDb = [...messagesForDb, finalModelMessageForDb];
        updateSessionMessages(currentSessionId, allMessagesForDb);
      }

    } catch (error: any) {
      if (error.message === 'Stream aborted by user') {
          console.log('Generation stopped by user');
          setMessages(prev => prev.map(msg => msg.id === modelMessageId ? { ...msg, content: msg.content + " [Stopped]" } : msg));
      } else {
          console.error("Action error", error);
          
          // Enhanced Error Parsing
          let extractedMessage = error.message || "Could not process request.";
          let extractedCode = error.status || error.code;
          let extractedStatus = "";

          // Check for structured { error: { code, message, status } }
          if (error.error) {
              extractedMessage = error.error.message || extractedMessage;
              extractedCode = error.error.code || extractedCode;
              extractedStatus = error.error.status || "";
          }

          const strError = JSON.stringify(error);
          
          // Robust check for Quota/429
          const isQuotaError = 
              extractedCode === 429 || 
              extractedStatus === 'RESOURCE_EXHAUSTED' ||
              (typeof extractedMessage === 'string' && (extractedMessage.includes("429") || extractedMessage.includes("RESOURCE_EXHAUSTED") || extractedMessage.includes("quota"))) ||
              strError.includes("RESOURCE_EXHAUSTED") ||
              strError.includes("429");

          // Robust check for 400/Invalid Argument
          const isBadRequest = 
              extractedCode === 400 || 
              extractedStatus === 'INVALID_ARGUMENT' ||
              (typeof extractedMessage === 'string' && (extractedMessage.includes("400") || extractedMessage.includes("INVALID_ARGUMENT"))) ||
              strError.includes("INVALID_ARGUMENT");

          let finalErrorMessage = extractedMessage;

          if (isQuotaError) {
              finalErrorMessage = "⚠️ **Quota Exceeded (429)**\n\nYou have reached the API rate limit for this model. This is common with free or low-tier keys.\n\n**Suggestions:**\n1. Wait a minute and try again.\n2. Switch to a lighter model like `gemini-2.5-flash`.\n3. Check your API key quota in Google AI Studio.";
          } 
          else if (isBadRequest) {
              finalErrorMessage = "⚠️ **Invalid Request (400)**\n\nThe model rejected the request. This might be due to safety filters, unsupported file types, or prompt complexity.";
              if (extractedMessage && extractedMessage !== "Request contains an invalid argument." && typeof extractedMessage === 'string') {
                  finalErrorMessage += `\n\n*Details: ${extractedMessage}*`;
              }
          }
          else if (typeof finalErrorMessage === 'string' && (finalErrorMessage.includes("503") || finalErrorMessage.includes("500") || finalErrorMessage.includes("Overloaded"))) {
              finalErrorMessage = "⚠️ **Service Overloaded (503)**\n\nThe AI provider is currently experiencing high traffic. Please try again in a few moments.";
          }

          setMessages(prev => prev.map(msg => msg.id === modelMessageId ? { ...msg, content: finalErrorMessage, isError: true } : msg));
      }
    } finally {
      setLoadingState('idle');
    }
  };

  return {
    messages,
    setMessages,
    loadingState,
    setLoadingState,
    sendMessage,
    stopGeneration
  };
};
