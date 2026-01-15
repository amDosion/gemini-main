
import { useMemo } from 'react';
import { Message, AppMode } from '../types/types';

/**
 * 视图消息过滤 Hook
 * 根据当前应用模式过滤消息
 */
export const useViewMessages = (messages: Message[], appMode: AppMode): Message[] => {
  return useMemo(() => {
    return messages.filter(m => {
      // 向后兼容：如果没有设置 mode，假设属于 'chat'
      const messageMode = m.mode || 'chat';
      return messageMode === appMode;
    });
  }, [messages, appMode]);
};
