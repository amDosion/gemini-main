import { useMemo } from 'react';
import { Message, AppMode } from '../types/types';

/**
 * 视图消息过滤 Hook
 * 根据当前应用模式过滤消息。
 * 向后兼容：消息未设置 mode 时视为属于 'chat'。
 */
export const useViewMessages = (messages: Message[], appMode: AppMode): Message[] => {
  return useMemo(() => messages.filter((m) => (m.mode || 'chat') === appMode), [messages, appMode]);
};
