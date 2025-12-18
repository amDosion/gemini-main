/**
 * 媒体生成模式处理器
 * 处理 video-gen 和 audio-gen 模式
 */
import { v4 as uuidv4 } from 'uuid';
import { Attachment } from '../../../types';
import { llmService } from '../../services/llmService';
import { HandlerContext, HandlerResult } from './types';
import { uploadToCloudStorageSync } from './attachmentUtils';

/**
 * 处理视频生成模式
 * 
 * @param text - 用户输入的提示词
 * @param attachments - 附件列表（可能包含参考图片）
 * @param context - 处理器上下文
 * @returns 生成结果（包含显示用和数据库用的附件）
 */
export const handleVideoGen = async (
  text: string,
  attachments: Attachment[],
  context: HandlerContext
): Promise<HandlerResult & { dbAttachments?: Attachment[] }> => {
  console.log('[mediaGenHandler] 开始视频生成:', {
    prompt: text.substring(0, 50) + (text.length > 50 ? '...' : ''),
    attachmentsCount: attachments.length
  });

  const result = await llmService.generateVideo(text, attachments);
  
  const attachmentId = uuidv4();
  const filename = `video-${Date.now()}.mp4`;
  let displayUrl = result.url;
  let cloudUrl = '';

  // 统一处理：下载并上传所有结果到云存储
  console.log('[mediaGenHandler] 下载并上传视频到云存储...');

  try {
    // 下载远程 URL
    const response = await fetch(result.url);
    const blob = await response.blob();
    displayUrl = URL.createObjectURL(blob); // 创建本地 Blob URL 用于显示
    const file = new File([blob], filename, { type: blob.type || 'video/mp4' });

    // 上传到云存储
    cloudUrl = await uploadToCloudStorageSync(file, filename);
  } catch (e) {
    console.error('[mediaGenHandler] 下载或上传视频失败:', e);
  }

  console.log('[mediaGenHandler] 视频生成完成:', {
    displayUrl: displayUrl.substring(0, 50) + '...',
    cloudUrl: cloudUrl || '(上传失败)'
  });

  // 显示用附件（本地 URL）
  const displayAttachment: Attachment = {
    id: attachmentId,
    mimeType: result.mimeType,
    name: filename,
    url: displayUrl,
    uploadStatus: cloudUrl ? 'completed' : 'pending'
  };

  // 数据库用附件（云存储 URL）
  const dbAttachment: Attachment = {
    id: attachmentId,
    mimeType: result.mimeType,
    name: filename,
    url: cloudUrl || '',
    uploadStatus: cloudUrl ? 'completed' : 'pending'
  };

  return {
    content: `Generated video: "${text}"`,
    attachments: [displayAttachment],
    dbAttachments: [dbAttachment]
  };
};

/**
 * 处理音频生成模式
 * 
 * @param text - 要转换为语音的文本
 * @param context - 处理器上下文
 * @returns 生成结果（包含显示用和数据库用的附件）
 */
export const handleAudioGen = async (
  text: string,
  context: HandlerContext
): Promise<HandlerResult & { dbAttachments?: Attachment[] }> => {
  console.log('[mediaGenHandler] 开始音频生成:', {
    textLength: text.length
  });

  const result = await llmService.generateSpeech(text);
  
  const attachmentId = uuidv4();
  const filename = `audio-${Date.now()}.wav`;
  let displayUrl = result.url;
  let cloudUrl = '';

  // 统一处理：下载并上传所有结果到云存储
  console.log('[mediaGenHandler] 下载并上传音频到云存储...');

  try {
    // 下载远程 URL
    const response = await fetch(result.url);
    const blob = await response.blob();
    displayUrl = URL.createObjectURL(blob); // 创建本地 Blob URL 用于显示
    const file = new File([blob], filename, { type: blob.type || 'audio/wav' });

    // 上传到云存储
    cloudUrl = await uploadToCloudStorageSync(file, filename);
  } catch (e) {
    console.error('[mediaGenHandler] 下载或上传音频失败:', e);
  }

  console.log('[mediaGenHandler] 音频生成完成:', {
    displayUrl: displayUrl.substring(0, 50) + '...',
    cloudUrl: cloudUrl || '(上传失败)'
  });

  // 显示用附件（本地 URL）
  const displayAttachment: Attachment = {
    id: attachmentId,
    mimeType: result.mimeType,
    name: filename,
    url: displayUrl,
    uploadStatus: cloudUrl ? 'completed' : 'pending'
  };

  // 数据库用附件（云存储 URL）
  const dbAttachment: Attachment = {
    id: attachmentId,
    mimeType: result.mimeType,
    name: filename,
    url: cloudUrl || '',
    uploadStatus: cloudUrl ? 'completed' : 'pending'
  };

  return {
    content: 'Generated speech.',
    attachments: [displayAttachment],
    dbAttachments: [dbAttachment]
  };
};
