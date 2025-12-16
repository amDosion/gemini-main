
import { useState, useCallback } from 'react';
import { Message, Role, LoadingState, ChatOptions, Attachment, AppMode, ModelConfig } from '../../types';
import { v4 as uuidv4 } from 'uuid';
import { llmService } from '../services/llmService';
import { addCitations } from '../utils/groundingUtils';
import { PdfExtractionService } from '../services/pdfExtractionService';
import { uploadToCloudStorageSync, isCloudStorageUrl } from './handlers/attachmentUtils';

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

    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    updateSessionMessages(currentSessionId, updatedMessages);
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

        for await (const chunk of stream) {
          if (chunk.text) accumulatedText += chunk.text;
          if (chunk.attachments && chunk.attachments.length > 0) accumulatedAttachments.push(...chunk.attachments);
          if (chunk.groundingMetadata) lastGroundingMetadata = chunk.groundingMetadata;
          if (chunk.urlContextMetadata) lastUrlContextMetadata = chunk.urlContextMetadata; // Capture URL metadata

          setMessages(prev =>
            prev.map(msg =>
              msg.id === modelMessageId
                ? {
                  ...msg,
                  content: accumulatedText,
                  attachments: [...accumulatedAttachments],
                  groundingMetadata: lastGroundingMetadata,
                  urlContextMetadata: lastUrlContextMetadata // Update message state
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
          urlContextMetadata: lastUrlContextMetadata
        }];
        updateSessionMessages(currentSessionId, finalMessages);

      } else {
        // Specialized Modes (Gen/Edit)
        let finalContent = "";
        let resultArray: Attachment[] = [];

        // ========== image-gen / image-edit 模式 ==========
        if (mode === 'image-gen' || mode === 'image-edit') {
          // 调用 API 生成/编辑图片
          const results = await llmService.generateImage(text, processedAttachments);
          
          // 用于前端显示的附件（保持原始 URL，显示快）
          const displayAttachments: Attachment[] = [];
          // 用于数据库保存的附件（云存储 URL）
          const dbAttachments: Attachment[] = [];
          
          // 处理结果图
          for (let index = 0; index < results.length; index++) {
            const res = results[index];
            const resultAttachmentId = uuidv4();
            const resultFilename = mode === 'image-edit' 
              ? `edited-${Date.now()}-${index + 1}.png` 
              : `generated-${Date.now()}-${index + 1}.png`;
            
            let displayUrl = res.url; // 前端显示用原始 URL
            let cloudUrl = '';
            
            // 上传结果图到云存储
            if (res.url.startsWith('data:') || res.url.startsWith('blob:')) {
              console.log(`[useChat] ${mode} 结果图上传到云存储...`);
              cloudUrl = await uploadToCloudStorageSync(res.url, resultFilename);
            } else if (res.url.startsWith('http://') || res.url.startsWith('https://')) {
              // 远程 URL（如 DashScope 临时 URL）→ 下载后上传
              console.log(`[useChat] ${mode} 结果图是远程 URL，下载后上传`);
              try {
                const response = await fetch(res.url);
                const blob = await response.blob();
                displayUrl = URL.createObjectURL(blob); // 创建本地 Blob URL 用于显示
                const file = new File([blob], resultFilename, { type: blob.type || 'image/png' });
                cloudUrl = await uploadToCloudStorageSync(file, resultFilename);
              } catch (e) {
                console.error(`[useChat] 下载远程结果图失败:`, e);
              }
            }
            
            // 前端显示用原始/本地 URL
            displayAttachments.push({
              id: resultAttachmentId,
              mimeType: res.mimeType,
              name: resultFilename,
              url: displayUrl,
              uploadStatus: cloudUrl ? 'completed' : 'pending'
            });
            
            // 数据库保存用云存储 URL
            dbAttachments.push({
              id: resultAttachmentId,
              mimeType: res.mimeType,
              name: resultFilename,
              url: cloudUrl || '', // 上传失败则为空
              uploadStatus: cloudUrl ? 'completed' : 'pending'
            });
            
            console.log(`[useChat] ${mode} 结果图 - 显示URL:`, displayUrl.substring(0, 50));
            console.log(`[useChat] ${mode} 结果图 - 云存储URL:`, cloudUrl);
          }
          
          // 处理原图上传（仅 image-edit 模式）
          const dbUserAttachments: Attachment[] = [];
          if (mode === 'image-edit' && processedAttachments.length > 0) {
            for (const att of processedAttachments) {
              const attUrl = att.url || '';
              const isAttCloudUrl = isCloudStorageUrl(attUrl);
              
              if (isAttCloudUrl) {
                console.log('[useChat] image-edit 原图已是云存储 URL，跳过上传');
                dbUserAttachments.push({ ...att, uploadStatus: 'completed' });
                continue;
              }
              
              // 上传原图
              let uploadSource: string | File | null = att.file || attUrl;
              let cloudUrl = '';
              if (uploadSource) {
                console.log('[useChat] 上传原图到云存储');
                cloudUrl = await uploadToCloudStorageSync(uploadSource, att.name || `original-${Date.now()}.png`);
              }
              
              dbUserAttachments.push({
                ...att,
                url: cloudUrl || '',
                uploadStatus: cloudUrl ? 'completed' : 'pending'
              });
              console.log('[useChat] 原图云存储URL:', cloudUrl);
            }
          }
          
          // 前端显示用原始附件
          resultArray = displayAttachments;
          
          // 保存用户消息的数据库版本附件
          (userMessage as any)._dbAttachments = dbUserAttachments.length > 0 ? dbUserAttachments : processedAttachments;
          // 保存模型消息的数据库版本附件
          (initialModelMessage as any)._dbAttachments = dbAttachments;
          
          finalContent = mode === 'image-edit' ? `Edited image with: "${text}"` : `Generated images for: "${text}"`;
        }
        else if (mode === 'image-outpainting') {
          // 获取原图信息
          const originalAttachment = processedAttachments[0];
          const originalUrl = originalAttachment.url || '';
          const isOriginalCloudUrl = isCloudStorageUrl(originalUrl);
          
          console.log('[useChat] image-outpainting 原图 URL:', originalUrl.substring(0, 60));
          console.log('[useChat] 原图是否已是云存储 URL:', isOriginalCloudUrl);
          
          // 调用扩图 API（先调用，不阻塞）
          const result = await llmService.outPaintImage(originalAttachment);
          
          // 下载结果图创建 Blob URL（用于前端显示）
          const resultFilename = `expanded-${Date.now()}.png`;
          const imageBlob = await fetch(result.url).then(r => r.blob());
          const displayBlobUrl = URL.createObjectURL(imageBlob);
          
          const resultAttachmentId = uuidv4();
          
          // 前端显示用本地 Blob URL
          resultArray = [{ 
            id: resultAttachmentId,
            mimeType: result.mimeType,
            name: resultFilename,
            url: displayBlobUrl,
            uploadStatus: 'pending'
          }];
          
          console.log('[useChat] 结果图显示 URL:', displayBlobUrl.substring(0, 50));
          
          // 同步上传原图到云存储（仅当原图不是云存储 URL 时）
          let originalCloudUrl = isOriginalCloudUrl ? originalUrl : '';
          if (!isOriginalCloudUrl) {
            const uploadSource = originalAttachment.file || originalUrl;
            if (uploadSource) {
              console.log('[useChat] 上传原图到云存储...');
              originalCloudUrl = await uploadToCloudStorageSync(
                uploadSource, 
                originalAttachment.name || `original-${Date.now()}.png`
              );
              console.log('[useChat] 原图云存储 URL:', originalCloudUrl);
            }
          }
          
          // 同步上传结果图到云存储
          console.log('[useChat] 上传结果图到云存储...');
          const resultFile = new File([imageBlob], resultFilename, { type: 'image/png' });
          const resultCloudUrl = await uploadToCloudStorageSync(resultFile, resultFilename);
          console.log('[useChat] 结果图云存储 URL:', resultCloudUrl);
          
          // 设置数据库保存用的附件（云存储 URL）
          (userMessage as any)._dbAttachments = [{
            ...originalAttachment,
            url: originalCloudUrl || '',
            uploadStatus: originalCloudUrl ? 'completed' : 'pending'
          }];
          (initialModelMessage as any)._dbAttachments = [{
            id: resultAttachmentId,
            mimeType: result.mimeType,
            name: resultFilename,
            url: resultCloudUrl || '',
            uploadStatus: resultCloudUrl ? 'completed' : 'pending'
          }];
          
          finalContent = `Expanded image canvas.`;
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

          const extractionResult = await PdfExtractionService.extractFromPdf(
            pdfFile,
            templateType,
            apiKey,
            text // Use the prompt text as additional instructions
          );

          // Format the result as JSON string for display
          finalContent = JSON.stringify(extractionResult, null, 2);
          resultArray = [];
        }

        // ========== 分离前端显示和数据库保存 ==========
        
        // 前端显示用的消息（使用本地 URL，显示快）
        const displayModelMessage = { ...initialModelMessage, content: finalContent, attachments: resultArray };
        
        // 更新前端 UI（使用本地 URL）
        setMessages(prev => prev.map(msg => msg.id === modelMessageId ? displayModelMessage : msg));
        
        // 数据库保存用的消息（使用云存储 URL）
        // 检查是否有 _dbAttachments（image-gen/image-edit 模式会设置）
        const dbUserAttachments = (userMessage as any)._dbAttachments || userMessage.attachments;
        const dbModelAttachments = (initialModelMessage as any)._dbAttachments || resultArray;
        
        const dbUserMessage: Message = {
          ...userMessage,
          attachments: dbUserAttachments
        };
        const dbModelMessage: Message = {
          ...initialModelMessage,
          content: finalContent,
          attachments: dbModelAttachments
        };
        
        // 清理临时字段
        delete (dbUserMessage as any)._dbAttachments;
        delete (dbModelMessage as any)._dbAttachments;
        
        // 保存到数据库（使用云存储 URL）
        const dbMessages = [...messages.filter(m => m.id !== userMessage.id), dbUserMessage, dbModelMessage];
        updateSessionMessages(currentSessionId, dbMessages);
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
