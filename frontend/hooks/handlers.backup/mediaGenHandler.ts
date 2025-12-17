/**
 * 媒体生成模式处理器
 * 处理 video-gen 和 audio-gen 模式
 */
import { v4 as uuidv4 } from 'uuid';
import { Attachment, AppMode } from '../../../types';
import { llmService } from '../../services/llmService';
import { HandlerContext, HandlerResult } from './types';

/**
 * 处理视频生成模式
 */
export const handleVideoGen = async (
  text: string,
  attachments: Attachment[],
  context: HandlerContext
): Promise<HandlerResult> => {
  const result = await llmService.generateVideo(text, attachments);
  
  return {
    content: `Generated video: "${text}"`,
    attachments: [{ 
      id: uuidv4(), 
      mimeType: result.mimeType, 
      name: 'Video.mp4', 
      url: result.url 
    }]
  };
};

/**
 * 处理音频生成模式
 */
export const handleAudioGen = async (
  text: string,
  context: HandlerContext
): Promise<HandlerResult> => {
  const result = await llmService.generateSpeech(text);
  
  return {
    content: 'Generated speech.',
    attachments: [{ 
      id: uuidv4(), 
      mimeType: result.mimeType, 
      name: 'Audio.wav', 
      url: result.url 
    }]
  };
};
